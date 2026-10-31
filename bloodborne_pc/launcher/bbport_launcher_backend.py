"""UI-independent settings, launch and file operations for the Windows launcher.

The Qt Quick view talks to this object through a small set of slots. The game still
uses the same settings.json, bbport.ini, mods.json and run.py as the original UI.
"""
import ctypes
import json
import re
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
import zipfile

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

import bbport_coop as coop
import bbport_rig as rig
import bbport_launcher_win as core
import bbport_startup
import bbport_character as character
import bbport_save_backups as save_backups
from bbport_pkg_setup import PackageSetupError, install_game
from bbport_readiness import check_readiness, valid_trophy_key


def choice_rows(options):
    return [{'value': str(value), 'text': label[0]} for value, label in options]


def row(key, label, kind='text', options=None, hint='', enabled=True):
    return {'key': key, 'label': label, 'kind': kind, 'options': choice_rows(options or []),
            'hint': hint, 'enabled': enabled, 'disabled': not enabled}


# What the graphics rows do, and which ones cost GPU time (the presets change those).
EFFECT_HINTS = {
    'effect_chromatic_aberration': 'Colour fringes at the screen edges. Look only.',
    'effect_dof': 'Blurs the background in cutscenes and close-ups. Look only.',
    'effect_motion_blur': 'Blur while turning the camera. Look only.',
    'effect_ssao': 'Soft shadows in corners and creases. Costs GPU time.',
    'effect_game_aa': "The game's own edge smoothing, under the upscaler. Look only.",
    'effect_dynamic_shadows': 'Shadows cast by lamps, torches and other moving lights. Costs GPU time.',
    'effect_ssr': 'Reflections on wet streets; not in the original game. About 2 ms of GPU at 4K (RTX 4080 SUPER).',
}

FIELDS = {
    'Graphics': [
        row('upscaler', 'Upscaler', 'choice', core.UPSCALERS,
            'Renders below the output size and rebuilds a sharp image. DLSS needs an NVIDIA RTX card; FSR 3.1 works on any.'),
        row('preset', 'Upscaling preset', 'choice', core.PRESETS,
            'How far below the output the game renders: higher factors are faster and softer.'),
        row('dlss_model', 'DLSS model', 'choice', core.DLSS_MODELS, 'DLSS only. ' + core.DLSS_MODEL_HELP),
        row('output_res', 'Output resolution', 'choice', core.OUTPUTS, "The final image size, usually your display's."),
        row('present_upscale', 'Upscale to the display', 'choice', core.PRESENT_UPSCALES,
            "Only used when the output resolution is below your display's (for example 1440p on a 4K "
            'screen). FSR 1 EASU is sharper than the old bilinear stretch for about 0.2 ms of GPU.'),
        row('present_rcas', 'Extra sharpening after upscale', 'choice', core.PRESENT_RCAS,
            "Only with FSR 1 EASU and an output below your display's. FSR 1 RCAS on top; off by default "
            "because the upscaler's own sharpening already runs, so more can look over-sharpened."),
        row('frame_gen', 'Frame generation', 'choice', core.FRAME_GENERATION,
            "Makes frames between two of the game's: 60 FPS on screen becomes 120. Automatically enables "
            'NVIDIA Reflex with DLSS to maintain low latency. "FSR 3.1 + 4.1.1" is AMD FSR 3.1 frame '
            'generation: any GPU, and the one to use with the FSR 4 and FSR 4.1.1 upscalers (neither has its own). '
            '"DLSS (RTX 40+)" is NVIDIA DLSS Frame Generation on a GeForce RTX 40 or 50.'),
        row('frame_gen_multiplier', 'Frame generation multiplier', 'choice', core.FRAME_GEN_MULTIPLIERS,
            '3× and 4× need DLSS on a GeForce RTX 50.'),
        row('frame_gen_fit_display', 'Fit frame generation to the display', 'toggle',
            hint="Generates only the frames your display's refresh rate can show: none while the game runs above half of it (on by default)."),
        row('dlss5', 'DLSS 5 neural rendering (experimental)', 'choice', core.DLSS5_MODES,
            "Experimental. NVIDIA's AI relighting of the finished 3D image: richer light, skin and "
            "materials. It changes Bloodborne's look and costs a lot of GPU time. Needs an RTX 4080, "
            '4090 or newer, DLSS as the upscaler and 60 FPS, plus your own ReShade with the '
            'dlss5-bridge and renodx-dlss5 add-ons and your own nvngx_dlssnr.dll in the bin folder. '
            'On: ReShade loads with the game and the rows below go to its add-on; Off: ReShade stays '
            'off. Applies at the next start.'),
        # Right under the switch: it decides whether DLSS 5 can hold 60 FPS at 4K at all.
        row('nr_upscaling', 'NR upscaling', 'choice', core.NR_SWITCH,
            "Lets neural rendering run on the render-resolution guides and upscale (NREnableUpscaling, "
            'NGX DLSSNR.Upscaling). Off (the add-on default) runs it on every output pixel: measured to '
            'hold 60 FPS at 2560 × 1440, not at 4K. On (experimental) at 4K: 60 FPS with DLSS Balanced or '
            'Performance but softer, 60 → 120 with frame generation only at Ultra Performance, 55-57 FPS '
            'with Quality.'),
        row('nr_intensity', 'NR intensity', 'choice', core.NR_INTENSITIES,
            'How strongly the neural result replaces the frame (NRIntensity, NGX DLSSNR.Intensity).'),
        row('nr_preset', 'NR preset', 'choice', core.NR_PRESETS,
            'The network preset (NRPreset, NGX DLSSNR.Hint.Render.Preset).'),
        row('nr_style', 'NR style', 'choice', core.NR_STYLES,
            'The look: Default, Natural or Cinematic (NRStyle, NGX DLSSNR.Style).'),
        row('nr_local_structure', 'NR local structure', 'choice', core.NR_STRENGTHS,
            'Fine surface detail (NRLocalStructure, NGX DLSSNR.LocalStructureStrength).'),
        row('nr_local_tone', 'NR local tone', 'choice', core.NR_STRENGTHS,
            'Local lighting and colour change (NRLocalTone, NGX DLSSNR.LocalToneStrength).'),
        row('nr_skin_structure', 'NR skin structure', 'choice', core.NR_STRENGTHS,
            'Detail on skin (NRSkinStructure, NGX DLSSNR.SkinStructureStrength).'),
        row('nr_auto_mask', 'NR automatic mask', 'choice', core.NR_SWITCH,
            "Lets DLSS 5 mask areas it should not repaint (NRAutoMask, NGX DLSSNR.UseAutoMask). "
            "Not needed for the HUD: the add-on runs right after the game's DLSS, and this port draws "
            'the HUD after that, so the HUD never reaches neural rendering.'),
        row('nr_ui_correction', 'NR UI correction', 'choice', core.NR_SWITCH,
            'Corrects for interface drawn into the frame (NRUICorrection, NGX DLSSNR.UICorrection). '
            "Bloodborne's HUD is drawn after DLSS 5 here, so the frame it sees has none: leave it at the "
            'add-on default (off).'),
        row('reflex', 'NVIDIA Reflex Low Latency', 'choice', core.REFLEX_MODES,
            'NVIDIA GPUs only. Strongly recommended with DLSS Frame Generation to reduce queue latency. '
            'Off is default for native rendering as the port already keeps one frame queued.'),
        row('ray_tracing', 'Ray tracing', 'choice', core.RAY_TRACING,
            'Soft shadows in corners and under objects (ambient occlusion) and shadows from the moon, '
            "traced against the scene's real geometry. Torches and lamps keep the game's shadows. "
            'GPU time at 4K with DLSS Quality on an RTX 4080 SUPER: Low 1.3 ms, Medium 1.8 ms, '
            'High 1.7 ms, Ultra 3.7 ms. Custom: pick each effect in the Custom rows below; it starts '
            'from the level you had unless you picked Custom effects before. Needs a GPU '
            'with Vulkan ray tracing (GeForce RTX 20 or newer, Radeon RX 7000 or newer, Intel Arc) and '
            'object motion vectors. The in-game menu switches it at once.'),
        row('rt_ao_quality', 'Custom: ray-traced ambient occlusion', 'choice', core.RT_AO_QUALITIES,
            'Ray tracing Custom only. Soft shadows in corners, under objects and around characters. '
            'Medium is what the Low, Medium and High levels use, Ultra what the Ultra level uses. '
            'High and Ultra cost more GPU time.'),
        row('rt_ao_strength', 'Ambient occlusion intensity', 'choice', core.RT_AO_STRENGTHS,
            'Every ray tracing level. How dark the ray-traced ambient occlusion gets; above 100% it is '
            'darker than traced. No cost. More ambient occlusion options are in the in-game menu (Custom).'),
        row('rt_shadow_quality', 'Custom: ray-traced moon shadows', 'choice', core.RT_SHADOW_QUALITIES,
            "Ray tracing Custom only. Everything solid (railings, statues, props, characters) casts "
            'a shadow under the moon. Ultra is what the Ultra level uses; High is sharper than Medium '
            'and reaches as far (15 m), but costs more GPU time.'),
        row('rt_shadow_half', 'Custom: half-resolution moon shadows', 'toggle',
            hint='Ray tracing Custom only. Half-resolution tracing with edge-aware upsampling. Performance and edge quality depend on the scene and render resolution.'),
        row('hud_position', 'HUD position (ultrawide)', 'choice', core.HUD_POSITIONS,
            '21:9 and 32:9 outputs: health, items and Blood Echoes at the screen edges, or in the '
            'centred 16:9 area as on a 16:9 screen. Applies at the next start.'),
        row('live_resolution', 'Live resolution changes', 'choice', core.LIVE,
            'Lets the in-game menu change the upscaling preset without a restart, at some cost in speed.'),
        row('sharpen', 'Sharpening (RCAS)', 'toggle', hint='Sharpens the upscaled image.'),
        row('sharpness', 'Sharpness (0.00–1.00)'),
        row('object_motion', 'Object motion vectors', 'toggle',
            hint='Motion data for moving characters: fewer ghosting trails with an upscaler.'),
        row('model_lod', 'Model detail', 'choice', core.LODS,
            'How soon distant models switch to simpler versions. Highest costs GPU time.'),
        row('anisotropic_filtering', 'Texture filtering', 'choice', core.ANISOTROPY,
            'Keeps ground and walls seen at an angle sharp instead of blurring into the distance. '
            'The game uses 4x on most surfaces; 16x shows on long streets and floors seen at a '
            'shallow angle. No measurable GPU cost at 4K on an RTX 4080 SUPER. The menus and HUD '
            'are unchanged. Restart the game to apply.'),
        row('vram_budget_mb', 'Video memory pressure target', 'choice', core.VRAM_BUDGETS,
            'Starts clearing old textures and buffers before the chosen amount. This is not a hard VRAM cap; '
            'lower values may cause stutter. Restart the game to apply.'),
        row('show_fps', 'Show FPS counter', 'toggle'),
        *[row(key, title[0], 'toggle', hint=EFFECT_HINTS.get(key, '')) for key, title, _ in core.EFFECTS],
    ],
    'Display': [
        row('fps_mode', 'Frame rate', 'choice', core.FPS_MODES),
        row('frame_cap', 'Unlocked mode limit', 'choice', core.FRAME_CAPS),
        row('frames_ahead', 'Frames ahead', 'choice', core.FRAMES_AHEAD),
        row('fullscreen', 'Fullscreen', 'toggle'),
        row('fullscreen_mode', 'Fullscreen type', 'choice', core.FULLSCREEN_MODES,
            'Exclusive switches the display to its own mode: notifications and other windows do not show over the game.'),
        row('display', 'Monitor', 'choice', core.DISPLAYS,
            'The monitor the game window and fullscreen go to, in the order the game log lists them.'),
        row('present_mode', 'Presentation mode', 'choice', core.PRESENT_MODES),
        row('hdr', 'HDR output', 'toggle'),
        row('hdr_white_nits', 'HDR paper white', 'choice', core.HDR_WHITES,
            "HDR output only. How bright the game's white is. Raise it if the game looks dimmer than "
            "the Windows desktop; Match Windows uses Windows' SDR content brightness slider. Applies "
            'at the next frame.'),
        row('hdr_peak_nits', 'HDR peak brightness', 'choice', core.HDR_PEAKS,
            'HDR output only. The brightest highlights roll off towards this. Set it to your '
            "display's peak (From the display reads it from Windows) so highlights neither clip nor "
            'stay dim.'),
        row('hdr_highlight_boost', 'HDR highlight boost', 'choice', core.HDR_BOOSTS,
            "HDR output only. How far bright parts of the game's SDR picture (fire, lamps, the moon) "
            'are pushed above white. Off keeps them at paper white.'),
    ],
    'Game': [
        row('game_dir', 'Game folder (contains eboot.bin)', 'folder'),
        row('user_dir', 'Saves folder', 'folder'),
        row('custom_avatar_path', 'Custom avatar image', 'file', hint='Custom PNG, JPG, or WEBP image for your hunter profile'),
        row('dlc_dir', 'DLC folder (base-game dumps only, e.g. SPEXPANSIONDLC03)', 'folder'),
        row('language', 'Game language', 'choice', core.LANGUAGES),
        row('voice_language', 'Voice language', 'choice', core.VOICE_LANGUAGES,
            'As in the game uses the original voice setting; other choices use available tracks.'),
        row('player_name', 'Hunter name'),
        row('backup_after_play', 'Back up saves after playing', 'toggle',
            hint=f'When the game closes, a copy of your saves goes to save-backups in the saves folder. '
            f'The last {save_backups.KEEP_AUTO} automatic copies are kept; your own backups are never deleted.'),
        *[row(key, title[0], 'toggle') for key, title, _ in core.EXTRAS[:1]],
    ],
    'Controller': [
        row('mouse_camera', 'Mouse camera (click the game window to use it)', 'toggle'),
        row('mouse_menu', "Mouse pointer in the game's menus (hover, click, right-click back)", 'toggle'),
        row('mouse_sensitivity', 'Mouse sensitivity', 'choice', core.MOUSE_SPEEDS),
        row('mouse_invert_y', 'Invert mouse Y', 'toggle'),
        row('mouse_hide_cursor', 'Hide the mouse cursor in the game (for mouse-to-controller tools)', 'toggle'),
        row('move_smoothing', 'Keyboard movement smoothing (WASD direction changes)', 'choice',
            core.MOVE_SMOOTHING),
        row('debug_camera', 'Free camera', 'toggle'),
        row('debug_menu', 'Debug menu', 'toggle'),
    ],
    'Cheats': [
        *[row(key, title[0], 'toggle') for key, title, _ in core.CHEATS],
        *[row(key, title[0], 'toggle') for key, title, _ in core.TWEAKS],
    ],
    'Online': [
        row('online_upnp', 'UPnP', 'toggle',
            hint='Opens a port on your router for summons. Turn it off on Tailscale or another VPN.'),
    ],
    'Co-op': [
        row('coop_name', 'Co-op name', hint='Your name in co-op, 3-16 letters, numbers, - or _.'),
        row('coop_password', 'Co-op password', kind='password',
            hint="For your co-op account on the host's server. Use one you use nowhere else."),
        row('coop_invite', 'Host invite code',
            hint='Paste the BBCOOP- code your host sent you. Leave empty when you host.'),
        row('coop_server', 'Co-op server', 'choice', core.COOP_SERVERS,
            "A friend's PC (or yours) over Tailscale, or BBSC's public server, where you meet other "
            'BBSC 0.0.2 players (shadPS4 and BBport) without Tailscale.'),
    ],
    'Mods': [
        row('mods_enabled', 'Enable mods', 'toggle'),
        row('mods_dir', 'Mods folder', 'folder'),
        row('patches_dir', 'External patches folder', 'folder'),
        row('hd_pack_dir', 'HD Texture Pack folder', 'folder',
            hint='Where the pack is built, apart from this launcher, so every launcher on this PC (also a new one you download) '
            'uses it. Empty: Bloodborne HD Texture Pack in your local app data. Keep it on the launcher\'s drive, or every start '
            'copies the pack. Choose it before installing: a pack already built stays where it is.'),
        row('hd_pack_downloads', 'HD Texture Pack downloads folder', 'folder',
            hint='Where the Nexus Mods downloads for the HD Texture Pack are kept (6 zip files, about 20 GB). The pack is '
            'built from them on this PC; the zips themselves are never shared or changed. Downloads of them that finish in your '
            'Downloads folder are moved here by themselves.'),
    ],
    'Enhancements': [
        *[row(key, title[0], 'toggle') for key, title, _ in core.ENHANCEMENTS],
    ],
    'Atlas': [
        *[row(key, title[0], 'toggle') for key, title, _ in core.ATLAS],
        row('atlas_npc_mode', 'NPC markers', 'choice', core.ATLAS_NPC_MODES),
    ],
    # Launch behaviour (launchDirectly, close_on_play, shortcuts) lives on Home; the update
    # toggle has its own row with "Check now" in Main.qml.
    'Advanced': [
        row('ui_language', 'Launcher language', 'choice', [('', ('System default',))] + core.UI_LANGUAGES),
        row('draw_pipe', 'Draw pipeline', 'choice', core.DRAW_PIPE),
        row('readbacks', 'GPU readbacks', 'choice', core.READBACKS),
        row('extra_env', 'Extra environment variables'),
    ],
    'Diagnostics': [
        row('frame_stats', 'Frame statistics', 'toggle'),
        row('gpu_profile', 'GPU profiling', 'toggle'),
        row('vk_validation', 'Vulkan validation', 'toggle'),
    ],
}

# The Settings workspace groups the existing controls by player task. The legacy
# field definitions remain the single source for control types and options.
SETTINGS_SECTIONS = {
    'Visuals': [
        # One topic per section keeps each page short: Resolution, Window, HDR and Frame rate each
        # have their own, as do Sharpening, Detail and Post-processing.
        ('Resolution', ['output_res', 'present_upscale', 'present_rcas']),
        ('Window', ['fullscreen', 'fullscreen_mode', 'display', 'hud_position']),
        # HDR output and its levels: a section of their own (the levels only apply with HDR on).
        ('HDR', ['hdr', 'hdr_white_nits', 'hdr_peak_nits', 'hdr_highlight_boost']),
        ('Frame rate', ['fps_mode', 'frame_cap', 'frames_ahead', 'present_mode']),
        # dlss5_detail / dlss5_tone are the built-in route's (vk_dlss5.h, none yet): kept in bbport.ini,
        # no row until that route exists.
        ('Upscaling', ['upscaler', 'preset', 'dlss_model', 'live_resolution', 'object_motion']),
        ('Sharpening', ['sharpen', 'sharpness']),
        # One section of its own (tab); QML folds the NR_ADVANCED rows behind "More NR options".
        ('Neural rendering (DLSS 5)', ['dlss5', 'nr_upscaling', 'nr_intensity', 'nr_preset', 'nr_style',
                                       'nr_local_structure', 'nr_local_tone',
                                       'nr_skin_structure', 'nr_auto_mask', 'nr_ui_correction']),
        ('Frame generation', ['frame_gen', 'frame_gen_multiplier', 'frame_gen_fit_display', 'reflex']),
        ('Ray tracing', ['ray_tracing', 'rt_ao_quality', 'rt_ao_strength', 'rt_shadow_quality', 'rt_shadow_half']),
        ('Detail', ['model_lod', 'anisotropic_filtering']),
        ('Post-processing', [key for key, _, _ in core.EFFECTS]),
        ('High-resolution textures', ['hd_pack_dir', 'hd_pack_downloads']),
        ('Video memory', ['vram_budget_mb']),
        ('Overlay', ['show_fps']),
    ],
    'Controls': [
        ('Button prompts', []),
        ('Mouse', ['mouse_camera', 'mouse_menu', 'mouse_sensitivity', 'mouse_invert_y', 'mouse_hide_cursor']),
        ('Keyboard', ['move_smoothing']),
    ],
    'Game & Saves': [
        ('Game files', ['game_dir', 'dlc_dir']),
        ('Your data', ['user_dir', 'custom_avatar_path']),
        ('Save backups', ['backup_after_play']),
        ('In-game preferences', ['language', 'voice_language', 'player_name'] + [key for key, _, _ in core.EXTRAS[:1]]),
    ],
    # Online is The Hunter's Dream only; how PLAY starts the game is chosen on the Home page.
    'Online': [
        ("The Hunter's Dream", ['online_upnp']),
    ],
    'Co-op': [
        ('Seamless co-op', ['coop_name', 'coop_password', 'coop_server']),
        ('Host a session', []),
        ('Join a host', ['coop_invite']),
        ('BBSC public server', []),
    ],
    'Mods & Patches': [
        ('Installed mods', ['mods_enabled', 'mods_dir']),
        ('Built-in enhancements', [key for key, _, _ in core.ENHANCEMENTS]),
        ("Hunter's Atlas (map)", [key for key, _, _ in core.ATLAS] + ['atlas_npc_mode']),
        ('External patches', ['patches_dir']),
        ('Gameplay tweaks', [key for key, _, _ in core.TWEAKS]),
        ('Cheats', [key for key, _, _ in core.CHEATS]),
    ],
    'System': [
        ('Launch', ['ui_language']),
        ('Updates', []),
        ('Engine', ['draw_pipe', 'readbacks', 'extra_env']),
        ('Developer', ['debug_camera', 'debug_menu', 'frame_stats', 'gpu_profile', 'vk_validation']),
        ('Maintenance', []),
        ('Logs', []),
    ],
}
# The Neural rendering section's rows folded away until "More NR options" opens them.
NR_ADVANCED = ('nr_local_structure', 'nr_local_tone', 'nr_skin_structure', 'nr_auto_mask',
               'nr_ui_correction')
for _field in FIELDS['Graphics']:
    _field['advanced'] = _field['key'] in NR_ADVANCED
SETTING_FIELDS = {field['key']: field for fields in FIELDS.values() for field in fields}
SEARCH_TERMS = {
    'output_res': 'screen resolution display', 'fps_mode': 'fps frame rate',
    'frame_cap': 'fps limit unlocked', 'upscaler': 'dlss fsr taa',
    'dlss_model': 'dlss transformer model preset ai', 'reflex': 'nvidia reflex low latency boost',
    'present_upscale': 'fsr 1 easu bilinear stretch upscale display 1440p resolution sharp',
    'hdr_white_nits': 'hdr paper white brightness nits dim', 'hdr_peak_nits': 'hdr peak brightness nits display',
    'hdr_highlight_boost': 'hdr highlight boost bright expansion',
    'present_rcas': 'fsr 1 rcas sharpen sharpening sharpness upscale display',
    'dlss5': 'dlss 5 neural rendering renodx reshade dlss5-bridge nvngx_dlssnr on off enable',
    'nr_intensity': 'dlss 5 neural rendering nr intensity strength',
    'nr_preset': 'dlss 5 neural rendering nr preset', 'nr_style': 'dlss 5 neural rendering nr style natural cinematic',
    'rt_shadow_half': 'ray tracing shadows half resolution speed performance',
    'vram_budget_mb': 'vram video memory texture cache pressure budget',
    'user_dir': 'save folder save path', 'game_dir': 'eboot install game files',
    'custom_avatar_path': 'custom avatar image hunter icon picture',
    'backup_after_play': 'save backup copy restore automatic',
    'online_npid': 'account id username', 'mouse_camera': 'camera controls', 'mouse_menu': 'cursor pointer click menus',
    'mouse_hide_cursor': 'cursor pointer hide invisible',
    'ui_language': 'launcher language', 'mods_enabled': 'load mods',
    'hd_pack_downloads': 'hd texture pack high resolution textures reborne sky armor nexus',
    'hd_pack_dir': 'hd texture pack high resolution textures folder location',
}
SEARCH_ACTIONS = [
    ('Visuals', 'Ray tracing', 'Ray tracing quality & custom tiers', 'raytracing shadows ambient occlusion rtx'),
    ('Controls', 'Button prompts', 'Xbox and PlayStation prompts', 'button controller'),
    ('Visuals', 'Upscaling', 'Download FSR 4 assets', 'fsr shader'),
    ('Visuals', 'Upscaling', 'Download FSR 4.1.1 (fsr4vk)', 'fsr 4.1.1 fsr4vk experimental'),
    ('Game & Saves', 'Game files', 'Install from ZIP / PKG', 'game files setup'),
    ('Game & Saves', 'Your data', 'Import trophy keys', 'keys.json trophies'),
    ('Game & Saves', 'Your data', 'Open saves folder', 'save path'),
    ('Game & Saves', 'Save backups', 'Back up saves now', 'save backup restore copy savedata'),
    ('Online', "The Hunter's Dream", 'Sign in with Discord', 'discord account hunters dream thd online'),
    ('Mods & Patches', 'Installed mods', 'Refresh mods', 'load order'),
    ('Visuals', 'High-resolution textures', 'Install the HD Texture Pack', 'hd textures reborne sky armor'),
    ('System', 'Launch', 'Desktop shortcut', 'start menu'),
    ('System', 'Launch', 'Add to Steam', 'integration'),
    ('System', 'Logs', 'Copy log', 'activity diagnostics'),
    ('System', 'Maintenance', 'Clear shader cache', 'shaders'),
    ('System', 'Maintenance', 'Restore saved settings', 'restore json settings load backup profile'),
]

# The HD Texture Pack (scripts/hd_texture_pack.py): one mod folder of picture files built on this PC
# from the player's own Nexus Mods downloads, switched on the Visuals page rather than the Mods page.
# It lives in its own folder (core.hd_pack_home), not the launcher's, so a new launcher keeps it.
HD_PACK = core.HD_PACK


def size_text(size):
    """'4.3 GB' or '64 MB'."""
    return f'{size / 2**30:.1f} GB' if size >= 2**30 else f'{size / 2**20:.0f} MB'


def downloads_folder():
    """The player's Downloads folder, where the browser saves (Windows keeps it moved if they moved it)."""
    try:
        path = ctypes.c_wchar_p()
        folder_id = ctypes.c_byte * 16  # FOLDERID_Downloads {374DE290-123F-4565-9164-39C4925E467B}
        guid = folder_id(*bytes.fromhex('90e24d373f126545916439c4925e467b'))
        if ctypes.windll.shell32.SHGetKnownFolderPath(guid, 0, None, ctypes.byref(path)) == 0:
            try:
                return Path(path.value)
            finally:
                ctypes.windll.ole32.CoTaskMemFree(path)
    except (AttributeError, OSError):
        pass
    return Path.home() / 'Downloads'


LAUNCHER_ROUTE = {'mode': 'launcher', 'page': 'Home', 'step': 0, 'problem': ''}


# These keys keep their navigation/search destinations, but the guided QML form
# owns their editors. Do not also instantiate generic FieldRow controls for them.
GUIDED_SETTING_FIELDS = {
    ('Co-op', 'Seamless co-op'): frozenset({'coop_name', 'coop_password', 'coop_server'}),
}


class LauncherBackend(QObject):
    changed = Signal()
    # graphicsPreset's own notify: also after one field changes (setValue), which does not emit
    # changed (that would rebuild every row while a list is open).
    presetStateChanged = Signal()
    logChanged = Signal()
    noticeChanged = Signal()
    runningChanged = Signal()
    closeRequested = Signal()
    updateAvailable = Signal(str, str, str)
    updateStateChanged = Signal()
    whatsNewChanged = Signal()
    _updateDownloaded = Signal(str, str, str)
    _updateProgress = Signal(str)
    workerNotice = Signal(str)
    gpuDetected = Signal(str)
    rigDetected = Signal('QVariantMap')
    connectionResult = Signal(str)
    setupRunningChanged = Signal()
    setupCompleted = Signal(str)
    setupFailed = Signal(str)
    coopChanged = Signal()
    _coopDone = Signal(str)
    _coopProgress = Signal(str)
    _coopChecked = Signal(list)  # connection_checks' rows, from the checking thread
    _coopPortsDone = Signal(bool, str)  # Open ports' result, from the co-op thread
    thdChanged = Signal()
    playModeChanged = Signal()
    _thdUpdate = Signal(str, str)        # status, code
    _thdDone = Signal(str, str, str)     # error, online id, token
    gameStarted = Signal()
    gameFinished = Signal(int, bool)  # exit code, whether the game got as far as running
    presetApplied = Signal()
    profileDataChanged = Signal()
    avatarChanged = Signal()
    saveBackupsChanged = Signal()
    _saveBackupDone = Signal(str)

    def __init__(self, route=None):
        super().__init__()
        saved = core.load_all_saved_settings()
        self.app = core.app_settings(saved)
        for signal in (self.changed, self.coopChanged, self.thdChanged):
            signal.connect(self.playModeChanged)
        self._route = {**LAUNCHER_ROUTE, **(route or {})}
        self._atlas_progress = ''  # Hunter's Atlas: the map preparation's progress line
        self._problem: str = str(self._route.get('problem', '') or '')
        self._game_started = False
        self._checks_started = False
        # A first start (no bbport.ini, no saved settings anywhere): once the GPU check reports,
        # the settings come from this PC instead of INI_DEFAULTS (_apply_first_start).
        self._first_start = not core.ini_path().is_file() and not isinstance(saved.get('ini_settings'), dict)
        self._first_start_summary = ''
        self.ini, self.ini_lines = core.load_ini()
        if isinstance(saved.get('ini_settings'), dict):
            for k, v in saved['ini_settings'].items():
                if k in core.INI_DEFAULTS:
                    self.ini[k] = str(v)
            try:
                core.save_ini({k: self.ini[k] for k in core.INI_DEFAULTS}, self.ini_lines)
            except Exception:
                pass
        # Saved Custom settings ("mine") load at every start, whatever was tried last time.
        if core.apply_my_settings(self.ini, self.app):
            try:
                core.save_ini({k: self.ini[k] for k in core.INI_DEFAULTS}, self.ini_lines)
            except OSError:
                pass
        self._remember_written()
        self.process = None
        self.job = None
        self._log = ''
        self._notice = 'Ready to hunt.'
        self._mods = []
        self._patches = []
        # A newer release found earlier (a direct launch checks quietly): shown at once.
        self._update = core.remembered_update() if self.app.get('check_updates') else None
        self._update_busy = False
        self._update_ready = None
        self._update_status = ""
        self._update_prompted_on_start = False
        # A downloaded update waiting at start: the window offers it with its notes (UpdateSheet).
        self._install_offer = False
        self._restore_update_download()
        # After an update, the first start shows this version's notes once. A first install
        # (no saved settings yet) just remembers the version.
        self._whats_new = ''
        if self.app.get('last_seen_version') != core.VERSION:
            if saved and self._route.get('page') != 'Setup':
                self._whats_new = core.release_notes_section(core.VERSION)
            if not self._whats_new:
                self.app['last_seen_version'] = core.VERSION
        self._updateDownloaded.connect(self._finish_update_download)
        self._updateProgress.connect(self._set_update_status)
        self._settings_revision = 0
        self._gpu_status = 'Checking graphics card…'
        self._dlss5_not_offered = '' # the GPU check's reason (empty: offered, or not known yet)
        self._dlss5_offered = False  # the GPU check said "DLSS 5: eligible"
        self._setup_running = False
        self.workerNotice.connect(self._set_notice)
        self.updateAvailable.connect(self._offer_update)
        self.gpuDetected.connect(self._set_gpu_status)
        self._rig = {}  # bbport_rig.collect for the GPU check's card (the top bar's rig pill)
        self.rigDetected.connect(self._set_rig)
        self.connectionResult.connect(self._show_connection_result)
        self.setupCompleted.connect(self._complete_game_setup)
        self.setupFailed.connect(self._fail_game_setup)
        # Seamless co-op (bbport_coop): the servers this launcher hosts, and the last message.
        self._coop_host = coop.Host()
        self._coop_busy = False
        self._coop_status = ''
        self._coop_invite = ''
        self._coop_launch_env = None
        self._coopDone.connect(self._coop_finished)
        self._coopProgress.connect(self._coop_show_progress)
        # The Co-op page's "Connection details": the last check and BBSC's connection events.
        self._coop_checks = []
        self._coop_ports = {'state': '', 'text': ''}  # Open ports: '', 'working', 'ok', 'failed'
        self._coop_checking = False
        self._coop_events = []
        self._coopChecked.connect(self._coop_checks_done)
        self.changed.connect(self.presetStateChanged)
        self.presetApplied.connect(self.presetStateChanged)
        self._coopPortsDone.connect(self._coop_ports_done)
        # The Hunter's Dream's Discord sign-in (a code approved on its website).
        self._thd_status = ''
        self._thd_code = ''
        self._thd_busy = False
        self._thd_cancel = False
        self._thdUpdate.connect(self._thd_update)
        self._thdDone.connect(self._thd_finished)
        # HD Texture Pack build: its process, progress (0-1) and status line.
        self._hd_process = None
        self._hd_progress = 0.0
        self._hd_status = ''
        self._hd_started = 0.0
        self._hd_timer = None        # watches the Downloads folder while files are missing
        self._hd_seen = {}           # download name: its size at the last look
        self._hd_moving = set()
        # Save backups (bbport_save_backups): the list shown, a worker's state and its last message.
        self._save_backups = []
        self._save_backup_busy = False
        self._save_backup_status = ''
        self._save_restore_pending = False
        self._saveBackupDone.connect(self._save_backup_finished)
        # Character profile data (for launcher display)
        self._profile_data = {}
        self.refresh_profile_data()
        self._hd_move_from_mods()
        self.refresh_addons()
        if self._route['mode'] != 'direct':
            self.start_background_checks()

    def start_background_checks(self):
        """GPU detection and the update check, once the launcher window is shown; a direct
        launch skips them so nothing competes with the game starting."""
        if self._checks_started:
            return
        self._checks_started = True
        threading.Thread(target=self._detect_gpu, daemon=True).start()
        if self.app.get('download_updates') and self.updateReady and not self._update_prompted_on_start:
            self._update_prompted_on_start = True
            self._install_offer = True  # read by the window when it opens: no dialog before it
            self.updateStateChanged.emit()
        if self.app.get('check_updates'):
            self.checkForUpdates(False)
        if not self.hdPackInstalled and self._hd_in_downloads():
            self._hd_watch()  # a pack file downloaded (or downloading) since the launcher last ran
        self._hd_auto_build()  # every download already in its folder

    @Property(str, notify=noticeChanged)
    def notice(self):
        return self._notice

    @Property(str, constant=True)
    def version(self):
        return core.VERSION

    @Property(dict, notify=profileDataChanged)
    def profileData(self):
        return self._profile_data

    @Property(str, notify=avatarChanged)
    def userAvatar(self):
        custom = (self.app.get('custom_avatar_path') or '').strip()
        if custom and Path(custom).is_file():
            return Path(custom).resolve().as_uri()
        user_dir = Path(self.value('user_dir') or core.DATA_DIR / 'user')
        for ext in ('.png', '.jpg', '.jpeg', '.webp'):
            candidate = user_dir / f"avatar{ext}"
            if candidate.is_file():
                return candidate.resolve().as_uri()
        return ''

    @Property(str, notify=logChanged)
    def log(self):
        return self._log

    @Property(bool, notify=runningChanged)
    def running(self):
        return self.process is not None

    @Property(bool, notify=setupRunningChanged)
    def setupRunning(self):
        return self._setup_running

    # --- First-run setup and start-up routing -------------------------------------------------

    def open_at(self, page, step=0):
        """Page (and wizard step) the launcher window opens on; set before loading Main.qml."""
        self._route.update(page=page, step=step)

    @Property(str, constant=True)
    def startPage(self):
        return self._route['page']

    @Property(int, constant=True)
    def wizardStartStep(self):
        return self._route['step']

    def _problem_active(self):
        if self._problem == 'game':
            return not bbport_startup.game_ok(self.app)
        if self._problem == 'saves':
            return not bbport_startup.writable(bbport_startup.saves_folder(self.app, core.DATA_DIR))
        return False

    @Property(str, notify=changed)
    def startupProblem(self):
        """Banner text while the start-up problem persists; empty once fixed or dismissed."""
        if self._problem_active() and self._problem in bbport_startup.PROBLEMS:
            return bbport_startup.PROBLEMS[self._problem][0]
        return ''

    @Property(int, notify=changed)
    def fixStep(self):
        return bbport_startup.PROBLEMS.get(self._problem, ('', 1))[1]

    @Property(bool, notify=changed)
    def launchDirectly(self):
        return bool(self.app.get('launchDirectly'))

    @Property(bool, notify=changed)
    def closeOnPlay(self):
        return bool(self.app.get('close_on_play'))

    @Slot(str, str, result=bool)
    def confirm(self, title, text):
        answer = QMessageBox.question(None, title, text,
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        return answer == QMessageBox.StandardButton.Yes

    @Slot()
    def dismissProblem(self):
        self._problem = ''
        self.changed.emit()

    @Slot()
    def completeSetup(self):
        self.app.update(setupCompleted=True, setupSkipped=False, setupVersion=bbport_startup.SETUP_VERSION)
        self._write()

    @Slot()
    def skipSetup(self):
        self.app.update(setupSkipped=True, setupVersion=bbport_startup.SETUP_VERSION)
        if not bbport_startup.game_ok(self.app):
            self._problem = 'game'
        self._write()

    @Property(str, notify=changed)
    def gameStatus(self):
        info = core.game_info(self.app.get('game_dir'))
        return f'Game ready · version {info[1]}' if info else 'Choose your game folder to begin'

    @Property(str, notify=changed)
    def setupSummary(self):
        return (f"{self.ini.get('output_res', '1920x1080').replace('x', ' × ')}  ·  "
                f"{self.app.get('fps_mode', '120').upper()} FPS  ·  "
                f"{self.ini.get('upscaler', 'dlss').upper()}")

    @Property(dict, notify=changed)
    def setupFacts(self):
        fps = str(self.app.get('fps_mode', '120'))
        tech = [self.ini.get('upscaler', 'dlss').upper()]
        if self.ini.get('frame_gen', 'off') != 'off':
            tech.append('FG')
        if self.ini.get('ray_tracing', 'off') != 'off':
            tech.append('RT')
        return {
            'resolution': self.ini.get('output_res', '1920x1080').replace('x', ' × '),
            'frameRate': 'Target: unlocked' if fps == 'uncap' else f'Target: {fps} FPS',
            'upscaler': 'Requested: ' + ' · '.join(tech),
            'display': 'Fullscreen' if self.app.get('fullscreen') else 'Windowed',
        }

    @Slot(result=bool)
    def controllerConnected(self):
        try:
            xinput = ctypes.windll.xinput1_4
            return any(xinput.XInputGetState(index, ctypes.create_string_buffer(16)) == 0
                       for index in range(4))
        except (AttributeError, OSError):
            return False

    @Property(str, notify=changed)
    def gameFolder(self):
        return str(self.app.get('game_dir', ''))

    def _get_readiness(self):
        return check_readiness(self.app.get('game_dir'),
                               self.app.get('user_dir') or core.DATA_DIR / 'user',
                               core.game_info)

    @Property(str, notify=changed)
    def saveStatus(self):
        return self._get_readiness()[2]['detail']

    @Property(bool, notify=changed)
    def savesWritable(self):
        return bbport_startup.writable(bbport_startup.saves_folder(self.app, core.DATA_DIR))

    @Property(bool, notify=changed)
    def onlineIdInvalid(self):
        return False  # the shadNet account fields are gone; PLAY checks playModeBlocked

    @Property(list, notify=changed)
    def readiness(self):
        return self._get_readiness()

    @Slot()
    def refreshReadiness(self):
        self.changed.emit()

    @Property(str, notify=changed)
    def gpuStatus(self):
        return self._gpu_status

    @Property('QVariantMap', notify=changed)
    def rig(self):
        """This PC for the top bar: bbport_rig.collect's card, processor and memory (empty until the
        GPU check is done), plus the display the launcher is on."""
        screen = QGuiApplication.primaryScreen()
        display = {}
        if screen:
            size, ratio = screen.size(), screen.devicePixelRatio()
            width, height = round(size.width() * ratio), round(size.height() * ratio)
            display = {'width': width, 'height': height, 'resolution': rig.resolution_label(width, height),
                       'hz': round(screen.refreshRate())}
        return {**self._rig, **display}

    @Slot('QVariantMap')
    def _set_rig(self, values):
        self._rig = dict(values)
        self.changed.emit()

    @Slot(str)
    def _set_gpu_status(self, status):
        self._gpu_status = status
        self._settings_revision += 1 # the DLSS 5 row: greyed out where it is not offered
        if self._first_start:
            self._first_start = False
            self._apply_first_start(status)
        self.changed.emit()

    def _apply_first_start(self, gpu):
        """The first start's settings from this PC (core.first_start_settings): the display's
        resolution, DLSS or FSR 3.1 by card, and the suggested preset. Written once; a later
        start finds bbport.ini and keeps the player's own choices."""
        screen = QGuiApplication.primaryScreen()
        display = None
        if screen:
            size, ratio = screen.size(), screen.devicePixelRatio()
            display = (round(size.width() * ratio), round(size.height() * ratio))
        values, preset = core.first_start_settings(gpu, display)
        self.ini.update(values)
        if preset:
            core.apply_graphics_preset(preset, self.ini, self.app)
        try:
            core.save_ini({k: self.ini[k] for k in core.INI_DEFAULTS}, self.ini_lines)
            self._write()
        except OSError:
            pass  # still applied for this session; Save settings retries
        parts = [gpu.split(',')[0]] if preset else []
        if 'output_res' in values:
            parts.append(values['output_res'].replace('x', ' × '))
        parts.append(core.GRAPHICS_PRESET_INFO[preset][0] if preset else
                     'DLSS' if values['upscaler'] == 'dlss' else 'FSR 3.1')
        self._first_start_summary = 'Set for your PC: ' + ', '.join(parts) + '. Change anything you like.'
        self.presetApplied.emit()
        self._set_notice(self._first_start_summary)

    @Property(str, notify=changed)
    def firstStartSummary(self):
        """What the first start set from this PC (_apply_first_start), or ''."""
        return self._first_start_summary

    # --- Graphics presets (core.GRAPHICS_PRESETS) ---------------------------------------------

    @Property(str, notify=presetStateChanged)
    def graphicsPreset(self):
        return core.graphics_preset_of(self.ini, self.app)

    @Property(list, notify=changed)
    def graphicsPresets(self):
        """The preset buttons; "DLSS 5 ready" only on cards the GPU check offers DLSS 5, and
        "My settings" once saved."""
        return core.graphics_presets(self._dlss5_offered) + (['mine'] if core.saved_my_settings(self.app) else [])

    @Property(str, notify=changed)
    def recommendedPreset(self):
        return core.recommended_graphics_preset(self._gpu_status) or ''

    @Property('QVariantMap', notify=changed)
    def presetMarks(self):
        """The preset buttons' suggestion marks by name: " ★", or " ★ DLSS 4" / " ★ DLSS 5"
        (core.preset_tags). A property, so the buttons follow the GPU check."""
        return {name: ' ★ ' + tag if tag else ' ★'
                for name, tag in core.preset_tags(self._gpu_status, self._dlss5_offered).items()}

    @Property(str, notify=changed)
    def presetSuggestion(self):
        """The line under the preset buttons about the marks, or ''."""
        tags = core.preset_tags(self._gpu_status, self._dlss5_offered)
        if not tags:
            return ''
        if 'remastered' not in tags:
            return '★ Suggested for ' + self._gpu_status + '.'
        text = '★ DLSS 4: Remastered, the sharpest picture at your full output.'
        if 'dlss5_ready' in tags:
            text += ' ★ DLSS 5: DLSS 5 ready (on a 4K display it renders 2560 × 1440).'
        return text

    @Slot(str, result=str)
    def presetLabel(self, name):
        return core.GRAPHICS_PRESET_INFO.get(name, ('', ''))[0]

    @Slot(str, result=str)
    def presetDescription(self, name):
        return core.GRAPHICS_PRESET_INFO.get(name, ('', ''))[1]

    @Slot(str, result=str)
    def presetInfo(self, name):
        """A tuned preset's "?" on the Visuals page: its description and, where it is suggested
        for this card, why (one per DLSS generation, core.PRESET_TAGS)."""
        text = self.presetDescription(name)
        tag = core.preset_tags(self._gpu_status, self._dlss5_offered).get(name)
        why = {'remastered': 'the sharpest picture at your full output.',
               'dlss5_ready': 'on a 4K display it renders 2560 × 1440.'}.get(name)
        if tag and why:
            text += f'\n\n★ Suggested for your card ({tag}): {why}'
        return text

    @Property(int, notify=presetApplied)
    def settingsRevision(self):
        """Bumped when a preset rewrites several rows at once, so the pages rebuild them."""
        return self._settings_revision

    @Property(bool, notify=changed)
    def hasMySettings(self):
        return core.saved_my_settings(self.app) is not None

    @Slot()
    def saveMySettings(self):
        """Saves the current Visuals settings as Custom (the Custom pill loads them, and so does
        every start)."""
        self.app['my_settings'] = core.my_settings_snapshot(self.ini, self.app)
        self._write()
        self._settings_revision += 1
        self.presetApplied.emit()
        self.changed.emit()  # the Custom pill now loads them
        self._set_notice('Settings saved. They load every time the launcher starts.')

    @Slot(str)
    def applyGraphicsPreset(self, name):
        if name == 'mine':
            if core.apply_my_settings(self.ini, self.app):
                self._write()
                self._settings_revision += 1
                self.presetApplied.emit()
                self.changed.emit()
                self._set_notice('Custom settings loaded. Restart the game to apply them.' if self.running else
                                 'Custom settings loaded. They apply the next time the game starts.')
            return
        if name not in core.GRAPHICS_PRESETS or (name in core.DLSS5_PRESETS and not self._dlss5_offered):
            return
        previous_overrides = self.app.get('extra_env', '')
        previous_output = self.ini.get('output_res')
        core.apply_graphics_preset(name, self.ini, self.app)
        overrides_reset = previous_overrides != self.app.get('extra_env', '')
        if name == 'remastered' and self.hdPackInstalled:
            self._hd_enable(True)  # only the pack: "Enable mods" stays as the player set it
        self._write()
        self._settings_revision += 1
        self.presetApplied.emit()
        label = core.GRAPHICS_PRESET_INFO[name][0]
        message = (f'{label} preset chosen. Restart the game to apply it.' if self.running else
                   f'{label} preset chosen. It applies the next time the game starts.')
        if overrides_reset:
            message += ' Manual frame-rate overrides were reset.'
        if name in core.DLSS5_PRESETS:
            if previous_output != self.ini.get('output_res'):
                message += (' Output set to 2560 × 1440 (scaled to the display): DLSS 5 at 4K output '
                            'misses 60 FPS.')
            if self.ini.get('dlss5') != 'on':
                message += ' Turn DLSS 5 on in Neural rendering (DLSS 5).'
        self._set_notice(message)

    def _detect_gpu(self):
        exe = core.PORT_DIR / 'bin' / 'bb-gpu-capabilities.exe'
        if not exe.is_file():
            exe = core.PORT_DIR / 'out' / 'bb-gpu-capabilities.exe'
        if not exe.is_file():
            self.gpuDetected.emit('Graphics card check unavailable')
            return
        env = dict(os.environ)
        clang = next((p / 'msys64' / 'clang64' / 'bin' for p in core.PORT_DIR.parents
                      if (p / 'msys64' / 'clang64' / 'bin').is_dir()), None)
        if clang:
            env['PATH'] = str(clang) + os.pathsep + env.get('PATH', '')
        try:
            result = subprocess.run([str(exe), '--live-resolution'], capture_output=True, text=True,
                                    timeout=30, env=env, creationflags=core.NO_WINDOW)
            names = [line[5:].split(':')[0] for line in result.stderr.splitlines() if line.startswith('GPU: ')]
            # "DLSS 5: eligible" or "DLSS 5: not offered (<reason>)" (tools/gpu_capabilities.c).
            offer = [line for line in result.stderr.splitlines() if line.startswith('DLSS 5: not offered')]
            self._dlss5_not_offered = (offer[0][len('DLSS 5: not offered'):].strip(' ()')
                                       if offer else '')
            self._dlss5_offered = 'DLSS 5: eligible' in result.stderr.splitlines()
            self.gpuDetected.emit(names[0] if names else 'Vulkan graphics card not detected')
            if names:
                try:
                    self.rigDetected.emit(rig.collect(names[0]))
                except Exception:  # the pill is a nicety: it stays hidden rather than break the check
                    pass
        except (OSError, subprocess.TimeoutExpired):
            self.gpuDetected.emit('Graphics card check unavailable')

    @Property(list, notify=changed)
    def mods(self):
        return self._mods

    @staticmethod
    def _is_prompt_mod(name):
        return ('xbox' in name.lower() and 'prompt' in name.lower()) or name == core.KEYBOARD_PROMPTS

    @Property(list, notify=changed)
    def contentMods(self):
        """Mods for the Mods page; the button prompt mod is chosen on the Controller page, the HD
        Texture Pack on the Visuals page."""
        return [m for m in self._mods if not self._is_prompt_mod(m['name']) and m['name'] != HD_PACK]

    @Property(list, notify=changed)
    def patches(self):
        return self._patches

    @Property(str, notify=changed)
    def promptChoice(self):
        """From the mods in use, so a choice made in the game's overlay shows here too."""
        enabled = {m['name'] for m in self._mods if self._is_prompt_mod(m['name']) and m['enabled']}
        if core.KEYBOARD_PROMPTS in enabled:
            return 'Keyboard'
        return 'Xbox' if enabled else 'PlayStation'

    @Property(str, notify=changed)
    def fsrStatus(self):
        missing = core.fsr4_missing()
        return 'FSR 4 assets ready' if not missing else f'{len(missing)} FSR 4 assets missing'

    @Property(str, notify=changed)
    def fsr4vkStatus(self):
        if core.bbport_fsr4vk.files_ok(core.fsr4vk_dir()):
            return 'FSR 4.1.1 (fsr4vk) installed. On NVIDIA it runs up to 1920×1080 output; above that FSR 3.1 is used.'
        return ('FSR 4.1.1 (experimental): fsr4vk v0.4.3 with the AMD driver fix, about 14 MB, '
                'SHA-256 checked. Up to 1920×1080 output on NVIDIA.')

    @Property(str, notify=changed)
    def neuralRuntimeStatus(self):
        return core.neural_runtime_text()

    @Property(bool, notify=changed)
    def neuralRuntimeInstalled(self):
        return core.neural_runtime_status()['runtime']

    @Property(bool, notify=changed)
    def dlss5On(self):
        return self.ini.get('dlss5') == 'on'

    @Property(bool, notify=changed)
    def dlss5Offered(self):
        """The GPU check said "DLSS 5: eligible" for the card the game runs on."""
        return self._dlss5_offered

    @Slot()
    def resetNeuralRendering(self):
        """Every NR row back to the add-on's own default (DLSS 5 on or off is left as it is)."""
        for key in core.NR_SETTINGS:
            self.app[key] = 'addon'
        self._write()
        self._settings_revision += 1
        self.presetApplied.emit()  # the rows show their new values

    def scene_size_text(self):
        """The size the game renders at before upscaling (patches.py scaled_sizes), so a soft
        image at 4K is explained: Balanced renders 3840x2160 at 2258x1270."""
        try:
            w, h = (int(v) for v in self.ini.get('output_res', '1920x1080').lower().split('x'))
        except ValueError:
            return ''
        scale = 1.0
        if self.ini.get('upscaler', 'dlss') not in ('off', 'taa'):
            try:
                scale = core.PRESET_SCALE_VALUES[int(self.ini.get('preset', '0') or 0)]
            except (ValueError, IndexError):
                return ''
        rw, rh = (max(2, round(v / scale / 2) * 2) for v in (w, h))
        if scale == 1.0:
            return f'Now: the game renders at the output size, {w} × {h}.'
        return f'Now: the game renders at {rw} × {rh} and upscales it to {w} × {h}.'

    def live_field(self, field):
        if field['key'] == 'fps_mode' and (fps := core.dlss5_fps_warning(self.ini, self.app)):
            return {**field, 'hint': f"{field.get('hint', '')} {fps}".strip()}
        if field['key'] == 'preset':
            return {**field, 'hint': f"{field['hint']} {self.scene_size_text()}".strip()}
        if field['key'] == 'dlss5':
            # The community route (run.py dlss5_environment): On keeps ReShade's layer on when the
            # player's own files are in bin\ and the launcher writes the add-on's settings.
            # The GPU check's reason, when it ran, says whether this card is offered it.
            notes = [core.neural_runtime_text()]
            if self._dlss5_not_offered:
                notes.append(f'This graphics card is not offered DLSS 5: {self._dlss5_not_offered}.')
            if fps := core.dlss5_fps_warning(self.ini, self.app):
                notes.append(fps)
            return {**field, 'hint': f"{field['hint']} {' '.join(notes)}"}
        if field['key'] in ('output_res', 'nr_upscaling') and (out := core.dlss5_output_warning(self.ini, self.app)):
            return {**field, 'hint': f"{field.get('hint', '')} {out}".strip()}
        return field

    @Slot(str, result='QVariantList')
    def fields(self, page):
        # The revision makes the rows differ after a preset, so the page builds them anew.
        return [{**self.live_field(field), 'revision': self._settings_revision} for field in FIELDS.get(page, [])]

    @Slot(str, result='QVariantList')
    def categorySections(self, category):
        return [name for name, _ in SETTINGS_SECTIONS.get(category, [])]

    @Slot(str, str, result='QVariantList')
    def sectionFields(self, category, section):
        for name, keys in SETTINGS_SECTIONS.get(category, []):
            if name == section:
                # The revision makes the rows differ after a preset, so the page builds them anew.
                return [{**self.live_field(SETTING_FIELDS[key]), 'revision': self._settings_revision}
                        for key in keys if key not in GUIDED_SETTING_FIELDS.get((category, section), ())]
        return []

    @Slot(str, result='QVariantList')
    def searchSettings(self, query):
        words = query.lower().split()
        if not words:
            return []
        results = []

        def add(category, section, label, key='', terms=''):
            label_text = f'{label} {terms} {SEARCH_TERMS.get(key, "")}'.lower()
            section_text = section.lower()
            category_text = category.lower()
            haystack = f'{label_text} {section_text} {category_text}'
            if all(word in haystack for word in words):
                score = sum(4 if word in label_text else 2 if word in section_text else 1
                            for word in words)
                results.append((score, {'category': category, 'section': section,
                                        'label': label, 'key': key}))

        for category, sections in SETTINGS_SECTIONS.items():
            for section, keys in sections:
                candidates = [(key, SETTING_FIELDS[key]['label']) for key in keys]
                if not keys:
                    candidates = [('', section)]
                for key, label in candidates:
                    add(category, section, label, key)
        for category, section, label, terms in SEARCH_ACTIONS:
            add(category, section, label, '', terms)
        return [item for _, item in sorted(results, key=lambda result: -result[0])[:30]]

    @Slot(str, result='QVariant')
    def value(self, key):
        return self.ini.get(key, '') if key in core.INI_DEFAULTS else self.app.get(key, '')

    @Property(str, notify=changed)
    def effectiveFrameRate(self):
        return core.effective_fps_mode(self.app)

    def _remember_written(self):
        """What settings.json and bbport.ini held when this launcher last read or wrote them."""
        self._written_app = json.loads(json.dumps(self.app))
        self._written_ini = dict(self.ini)

    def _sync_from_disk(self):
        """Takes what the game wrote while the launcher was open: the in-game menu saves to
        bbport.ini and the in-game Fullscreen switch to settings.json. A value the launcher changed
        itself since its last write stays; any other the launcher would have written back over the
        game's (after Supermedo 40a883e, ethan; Awaken's 0.9.30 release notes)."""
        saved = core.load_json(core.CONFIG_FILE, None)
        if isinstance(saved, dict) and saved:
            for key, value in core.app_settings(saved).items():
                if self.app.get(key) == self._written_app.get(key) and value != self._written_app.get(key):
                    self.app[key] = value
        disk, lines = core.load_ini()
        for key, value in disk.items():
            if self.ini.get(key) == self._written_ini.get(key) and value != self._written_ini.get(key):
                self.ini[key] = value
        self.ini_lines = lines

    def _write(self):
        self._sync_from_disk()
        core.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            **self.app,
            'ini_settings': {k: self.ini[k] for k in core.INI_DEFAULTS if k in self.ini},
        }
        json_data = json.dumps(payload, indent=2, ensure_ascii=False)
        core.CONFIG_FILE.write_text(json_data, encoding='utf-8')

        # Persist directly with game saves (user_dir)
        user_dir = Path(self.app.get('user_dir') or core.DATA_DIR / 'user')
        try:
            user_dir.mkdir(parents=True, exist_ok=True)
            (user_dir / 'bbport_settings.json').write_text(json_data, encoding='utf-8')
        except OSError:
            pass

        # Also persist with game files folder if configured
        if self.app.get('game_dir'):
            game_dir = Path(self.app['game_dir'])
            if game_dir.is_dir():
                try:
                    (game_dir / 'bbport_settings.json').write_text(json_data, encoding='utf-8')
                except OSError:
                    pass

        core.save_ini({k: self.ini[k] for k in core.INI_DEFAULTS}, self.ini_lines)
        self.ini, self.ini_lines = core.load_ini()
        self._remember_written()
        self.changed.emit()

    @Slot()
    def installFromArchive(self):
        if self._setup_running or self.running:
            self._set_notice('Close the game or wait for the current setup to finish.')
            return
        source, _ = QFileDialog.getOpenFileName(
            None, 'Step 1: choose the game ZIP or the BASE game PKG (CUSA03173.pkg, not the update)', str(Path.home() / 'Downloads'),
            'Game archive or base PKG (*.zip *.pkg)')
        if not source:
            return
        update = None
        if Path(source).suffix.casefold() == '.pkg':
            update, _ = QFileDialog.getOpenFileName(
                None, 'Step 2: choose the plain 1.09 UPDATE PKG (not 720p or 1080p)', str(Path(source).parent), 'Update PKG (*.pkg)')
            # Game of the Year PKGs may already hold 1.09: no separate update then (#43).
            if not update and QMessageBox.question(
                    None, 'No update PKG',
                    f'Is {Path(source).name} already updated to 1.09 (a PKG with the update merged in)?\n\n'
                    'Yes installs it without an update PKG; the installer checks the version.') != QMessageBox.StandardButton.Yes:
                return
        parent = QFileDialog.getExistingDirectory(
            None, 'Last step: choose where to create the CUSA03173 game folder', str(Path.home()))
        if not parent:
            return
        target = Path(parent) / 'CUSA03173'
        if target.exists():
            QMessageBox.warning(None, 'Game folder already exists',
                                f'{target} already exists. Choose another location so no game files are replaced.')
            return
        extractor = core.PORT_DIR / 'tools' / 'pkg-extractor' / 'pkg_extractor.exe'
        if not extractor.is_file() and not core.FROZEN:
            extractor = core.PORT_DIR / 'out' / 'vendor' / 'pkg-extractor' / 'pkg_extractor.exe'
        self._setup_running = True
        self.setupRunningChanged.emit()
        self._set_notice('Preparing your game files. Keep the launcher open…')

        def work():
            try:
                installed = install_game(source, parent, extractor, update, self.workerNotice.emit)
                self.setupCompleted.emit(str(installed))
            except PackageSetupError as error:
                self.setupFailed.emit(str(error))
            except Exception as error:
                self.setupFailed.emit(f'Unexpected installer error: {error}')
        threading.Thread(target=work, daemon=True).start()

    @Slot(str)
    def _complete_game_setup(self, folder):
        self.app['game_dir'] = folder
        self._write()
        self._setup_running = False
        self.setupRunningChanged.emit()
        info = core.game_info(folder)
        if info and info[1] == '01.09':
            self._set_notice('Game installed and version 1.09 verified. Press PLAY.')
        else:
            self._set_notice('Game installed. Check that the launcher reports version 1.09 before playing.')

    @Slot(str)
    def _fail_game_setup(self, message):
        self._setup_running = False
        self.setupRunningChanged.emit()
        self._set_notice(message)
        QMessageBox.warning(None, 'Game installation could not finish', message)

    @Slot(str, 'QVariant')
    def setValue(self, key, value):
        if key in core.INI_DEFAULTS:
            if key in core.INI_FLAGS:
                value = '1' if value in (True, 1, '1', 'true') else '0'
            elif key == 'sharpness':
                try:
                    value = f'{max(0.0, min(1.0, float(value))):.2f}'
                except (ValueError, TypeError):
                    value = self.ini.get(key, '0.50')
            previous = self.ini.get(key)
            self.ini[key] = str(value)
            if key == 'frame_gen' and value == 'dlss':
                # NVIDIA Reflex should be active with DLSS Frame Generation
                if self.ini.get('reflex', 'off') == 'off':
                    self.ini['reflex'] = 'on'
            if key in ('upscaler', 'preset', 'output_res', 'frame_gen', 'ray_tracing', 'dlss5'):
                self._settings_revision += 1  # the hints name the new scene size, DLSS 5's warning
            # Custom starts from what the level traced (as the in-game menu does).
            if key == 'ray_tracing' and value == 'custom' and core.custom_start(previous, self.ini):
                self._write()
                self._settings_revision += 1
                self.presetApplied.emit()  # the Custom rows show their new values
                self.presetStateChanged.emit()
                return
        else:
            self.app[key] = value
            if key == 'nr_upscaling':
                self._settings_revision += 1  # DLSS 5's 4K warning (core.dlss5_output_warning)
        self._write()
        self.presetStateChanged.emit()  # the preset row: Custom once nothing matches
        if key == "download_updates" and value:
            self.downloadUpdate()

    @Slot()
    @Slot(bool)
    def saveSettings(self, quiet=False):
        self._write()
        save_path = str((Path(self.app.get('user_dir') or core.DATA_DIR / 'user') / 'bbport_settings.json').resolve())
        ini_path = str(core.ini_path().resolve()) if hasattr(core, 'ini_path') else 'bbport.ini'
        self._set_notice(f'Settings saved to {save_path}')
        if not quiet and not os.environ.get('PYTEST_CURRENT_TEST'):
            QMessageBox.information(
                None,
                'Settings Saved',
                f'Settings have been saved successfully!\n\n'
                f'Stored in persistent locations:\n'
                f'• Save folder: {save_path}\n'
                f'• Game INI: {ini_path}\n'
                f'• AppData config: {core.CONFIG_FILE}\n\n'
                f'Your settings will persist and can also be restored anytime from System → Maintenance.'
            )

    @Slot()
    def restoreSavedSettings(self):
        saved = core.load_all_saved_settings()
        found_source = None
        candidate_dirs = []
        if self.app.get('user_dir'):
            candidate_dirs.append(Path(self.app['user_dir']))
        candidate_dirs.extend([
            core.DATA_DIR / 'user',
            core.PORT_DIR / 'user',
            core.PORT_DIR.parent / 'CUSA03173' / 'user',
            core.PORT_DIR.parent / 'CUSA03173',
        ])
        if self.app.get('game_dir'):
            candidate_dirs.append(Path(self.app['game_dir']) / 'user')
            candidate_dirs.append(Path(self.app['game_dir']))
        for cdir in candidate_dirs:
            json_path = cdir / 'bbport_settings.json'
            if json_path.is_file():
                found_source = str(json_path.resolve())
                break
        if not found_source and core.CONFIG_FILE.is_file():
            found_source = str(core.CONFIG_FILE.resolve())

        if not saved and not found_source:
            source, _ = QFileDialog.getOpenFileName(
                None, 'Locate your bbport_settings.json', '', 'JSON files (*.json)'
            )
            if source:
                try:
                    user_saved = core.load_json(Path(source), {})
                    if isinstance(user_saved, dict) and user_saved:
                        saved = user_saved
                        found_source = source
                except Exception as e:
                    QMessageBox.warning(None, 'Restore Failed', f'Could not read settings from {source}:\n{e}')
                    return

        if not saved:
            QMessageBox.warning(
                None,
                'No Saved Settings Found',
                'No saved bbport_settings.json was found in the save folder, game directory, or AppData.'
            )
            return

        self.app = core.app_settings(saved)
        if isinstance(saved.get('ini_settings'), dict):
            for k, v in saved['ini_settings'].items():
                if k in core.INI_DEFAULTS:
                    self.ini[k] = str(v)
            try:
                core.save_ini({k: self.ini[k] for k in core.INI_DEFAULTS}, self.ini_lines)
            except Exception:
                pass
        self._write()
        self._settings_revision += 1
        self.changed.emit()
        self.coopChanged.emit()
        self.playModeChanged.emit()
        self.presetApplied.emit(self.graphicsPreset)
        self._set_notice(f'Settings restored from {found_source}')
        QMessageBox.information(
            None,
            'Settings Restored',
            f'Settings restored successfully from:\n{found_source}\n\n'
            f'All launcher configurations and engine options have been reloaded.'
        )

    @Property(str, notify=changed)
    def saveFolderPath(self):
        return str(Path(self.app.get('user_dir') or core.DATA_DIR / 'user').resolve())

    @Slot(str, result=bool)
    def checked(self, key):
        value = self.value(key)
        return value is True or value == '1'

    @Slot()
    def importTrophyKeys(self):
        source, _ = QFileDialog.getOpenFileName(
            None, 'Choose your trophy keys.json', '',
            'JSON files (*.json)'
        )
        if not source:
            return

        try:
            data = json.loads(Path(source).read_text(encoding='utf-8-sig'))
            trophy_key = data['TrophyKeySet']['ReleaseTrophyKey']
            if not valid_trophy_key(trophy_key):
                raise ValueError('ReleaseTrophyKey must be 32 hexadecimal characters')
        except (OSError, ValueError, KeyError, TypeError) as error:
            QMessageBox.warning(None, 'Invalid trophy keys',
                                f'This is not a valid trophy keys.json: {error}')
            return

        user_dir = Path(self.app.get('user_dir') or core.DATA_DIR / 'user')
        destination = user_dir / 'keys.json'

        if destination.exists():
            if Path(source).resolve() == destination.resolve():
                self._set_notice('Trophy keys are already installed.')
                return
            answer = QMessageBox.question(
                None, 'Replace trophy keys?',
                'This folder already contains keys.json. Replace it?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        try:
            user_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        except OSError as error:
            QMessageBox.warning(None, 'Import failed', str(error))
            return

        self._set_notice('Trophy keys installed successfully.')
        self.changed.emit()
    def _apply_custom_avatar(self, file_path):
        p = Path(file_path)
        if p.is_file():
            self.setValue('custom_avatar_path', str(p.resolve()))
            self.avatarChanged.emit()
            self._set_notice(f'Avatar updated: {p.name}')

    @Slot()
    def chooseCustomAvatar(self):
        parent_window = QApplication.activeWindow()
        file_path, _ = QFileDialog.getOpenFileName(
            parent_window,
            'Choose Avatar Image',
            str(Path.home() / 'Pictures'),
            'Image Files (*.png *.jpg *.jpeg *.webp *.bmp *.ico);;All Files (*.*)'
        )
        if file_path:
            self._apply_custom_avatar(file_path)

    @Slot(str)
    def setCustomAvatarUrl(self, url):
        if not url:
            return
        if url.startswith('file:'):
            file_path = QUrl(url).toLocalFile()
        else:
            file_path = url
        self._apply_custom_avatar(file_path)

    @Slot()
    def resetCustomAvatar(self):
        self.setValue('custom_avatar_path', '')
        user_dir = Path(self.value('user_dir') or core.DATA_DIR / 'user')
        for ext in ('.png', '.jpg', '.jpeg', '.webp'):
            candidate = user_dir / f"avatar{ext}"
            if candidate.is_file():
                try:
                    candidate.unlink()
                except OSError:
                    pass
        self.avatarChanged.emit()
        self._set_notice('Avatar reset to default.')

    @Slot(str)
    def browse(self, key):
        if key == 'custom_avatar_path':
            self.chooseCustomAvatar()
            return
        if key not in ('game_dir', 'user_dir', 'dlc_dir', 'mods_dir', 'patches_dir', 'hd_pack_dir', 'hd_pack_downloads'):
            return
        start = {'hd_pack_dir': self._hd_home, 'hd_pack_downloads': self._hd_downloads}.get(key)
        parent_window = QApplication.activeWindow()
        folder = QFileDialog.getExistingDirectory(parent_window, f'Choose {key.replace("_", " ")}',
                                                  str(start() if start else self.value(key) or core.DATA_DIR))
        if folder:
            if key.startswith('hd_pack'):
                self.setValue(key, folder)
                self._hd_auto_build()
                return
            old_user = Path(self.value('user_dir') or core.DATA_DIR / 'user')
            self.setValue(key, folder)
            if key == 'user_dir':
                self._carry_trophy_keys(old_user, Path(folder))
            if key in ('mods_dir', 'patches_dir'):
                self.refresh_addons()

    def _carry_trophy_keys(self, old_user, new_user):
        """The game reads keys.json from the saves folder: one imported before the saves folder
        was changed (the setup wizard asks for it first) stayed behind, and trophy names were
        missing. It moves along unless the new folder has its own."""
        source, target = old_user / 'keys.json', new_user / 'keys.json'
        if source.is_file() and not target.exists() and source.resolve() != target.resolve():
            try:
                new_user.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            except OSError as error:
                self._set_notice(f'Copy keys.json to the new saves folder yourself: {error}')
                return
            self._set_notice('Trophy keys copied to the new saves folder.')
            self.changed.emit()

    @Slot(str)
    def openFolder(self, key):
        path = self.value(key) if key else core.PORT_DIR
        if key == 'hd_pack_dir':
            path = self._hd_home()
        elif key == 'hd_pack_downloads':
            path = self._hd_downloads()
        if not path:
            path = core.DATA_DIR / {'user_dir': 'user', 'mods_dir': 'mods', 'patches_dir': 'patches'}.get(key, '')
        path = Path(path)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        os.startfile(str(path))

    def _set_notice(self, message):
        self._notice = message
        self.noticeChanged.emit()

    def _append_log(self, value):
        self._log = (self._log + value)[-350000:]
        self.logChanged.emit()

    @Slot()
    def play(self, env=None):
        if self._setup_running:
            self._set_notice('Wait for the game files to finish installing.')
            return
        if self._hd_process:
            self._set_notice('Wait for the HD Texture Pack to finish installing (or cancel it).')
            return
        if self.process:
            return
        if self._save_backup_busy:
            self._set_notice('Wait for the save backup to finish.')
            return
        if not core.game_info(self.app.get('game_dir')):
            self._set_notice('Choose the game folder containing eboot.bin first.')
            return
        if not self.savesWritable:
            self._set_notice('Choose a writable saves folder before playing.')
            return
        if self.onlineIdInvalid:
            self._set_notice('Online ID must be your account name, not an email address.')
            return
        if (env is None and self.app.get('online') and core.hunters_dream_selected(self.app)
                and not self.thdSignedIn):
            self._set_notice("The Hunter's Dream: sign in with Discord on the Online page first.")
            return
        self._write()
        self._log = ''
        self.logChanged.emit()
        try:
            if core.apply_renodx_nr(self.app, self.ini):
                self._append_log('Launcher: DLSS 5 neural rendering settings written to bin\\ReShade.ini.\n')
            if warning := core.dlss5_fps_warning(self.ini, self.app):
                self._append_log(f'Launcher: {warning}\n')
        except OSError as error:
            self._set_notice(f'Could not write the DLSS 5 settings to ReShade.ini: {error}')
        if env is None:  # no BBSC this time: its co-op bells would be "?GoodsName?" (bbport_coop.KIT_TO_VANILLA)
            try:
                if backup := coop.restore_vanilla_bells(self.app.get('user_dir') or core.DATA_DIR / 'user'):
                    self._append_log(f"Launcher: BBSC's co-op bells changed back to the vanilla bells for "
                                     f'this launch (saves backed up to {backup}).\n')
            except OSError as error:
                self._append_log(f"Launcher: could not change BBSC's co-op bells back: {error}\n")
        self._game_started = False
        try:
            self.process = subprocess.Popen(core.run_command(), cwd=core.PORT_DIR,
                                            env=env or core.game_environment(self.app, self.ini), stdin=subprocess.DEVNULL,
                                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                            creationflags=core.NO_WINDOW)
        except OSError as error:
            self._set_notice(f'Could not start: {error}')
            self.process = None
            return
        self.job = core.GameJob(self.process)
        self.runningChanged.emit()
        self._set_notice('Preparing the game…')
        threading.Thread(target=self._read_output, args=(self.process,), daemon=True).start()
        if self.app.get('close_on_play'):
            from PySide6.QtCore import QTimer
            QTimer.singleShot(5000, self.closeRequested.emit)

    # The game's output reaches the window in batches: one GUI update per line rebuilt the
    # 350 KB log text and its view for every line, and the burst the game prints when it quits
    # (Exit to desktop: about 2,300 lines) froze the launcher for minutes (Windows: "not
    # responding"). The log file still gets every line as it comes.
    OUTPUT_BATCH_S = 0.1

    def _read_output(self, process):
        batch, last = [], time.monotonic()
        with core.open_run_log(self.app.get('user_dir') or core.DATA_DIR / 'user') as log:
            for raw in iter(process.stdout.readline, b''):
                line = raw.decode('utf-8', errors='replace')
                log.write(line)
                batch.append(line)
                now = time.monotonic()
                if now - last >= self.OUTPUT_BATCH_S:
                    self._outputLine.emit(''.join(batch))
                    batch, last = [], now
        if batch:
            self._outputLine.emit(''.join(batch))
        self._gameExited.emit(process.wait())

    _outputLine = Signal(str)
    _gameExited = Signal(int)

    @Slot(str)
    def _receive_line(self, text):
        """A batch of the game's output lines (see _read_output)."""
        self._append_log(text)
        running = text.rfind('Entering original x86-64 code')
        restarting = text.rfind('restarting through run.py')
        if running >= 0 and not self._game_started:
            self._game_started = True
            self.gameStarted.emit()
        # Within one batch the later of the two lines says what is happening now.
        if running > restarting:
            self._set_notice('The game is running.')
        elif restarting >= 0:
            self._set_notice('Restarting with the new settings…')

    @Slot(int)
    def _receive_exit(self, code):
        self._append_log(f'\n— The game exited (code {code}) —\n')
        self.process = None
        if self.job:
            self.job.close()
            self.job = None
        self.runningChanged.emit()
        self._sync_from_disk()  # what the in-game menu changed, shown at once
        self._remember_written()
        self._settings_revision += 1
        self.presetApplied.emit()  # the pages rebuild their rows with those values
        self.changed.emit()
        if self._game_started or code == 0:
            self._set_notice('Ready to hunt.')
        else:
            self._set_notice(f'The game could not start (exit code {code}). See the log for details.')
        if self._game_started and self.app.get('backup_after_play', True):
            self._auto_backup_saves()  # zipped in a worker thread: this exit path stays fast
        self.gameFinished.emit(code, self._game_started)

    def connect_workers(self):
        self._outputLine.connect(self._receive_line)
        self._gameExited.connect(self._receive_exit)

    @Slot()
    def stop(self):
        if self.job:
            self.job.terminate()

    # --- Save backups (bbport_save_backups) ------------------------------------------------------
    # Zips of <saves folder>/savedata in <saves folder>/save-backups. The zip work runs in a
    # worker thread (_save_backup_run); nothing touches savedata while the game runs.

    def _saves_root(self):
        return bbport_startup.saves_folder(self.app, core.DATA_DIR)

    @Property(list, notify=saveBackupsChanged)
    def saveBackups(self):
        return self._save_backups

    @Property(bool, notify=saveBackupsChanged)
    def saveBackupBusy(self):
        return self._save_backup_busy

    @Property(str, notify=saveBackupsChanged)
    def saveBackupStatus(self):
        return self._save_backup_status

    @Property(str, notify=saveBackupsChanged)
    def saveBackupsFolder(self):
        return str(save_backups.backups_dir(self._saves_root()))

    @Slot()
    def refreshSaveBackups(self):
        try:
            self._save_backups = save_backups.list_backups(self._saves_root())
        except OSError as error:
            self._save_backups = []
            self._save_backup_status = f'Could not read the backups: {error}'
        self.saveBackupsChanged.emit()

    def _save_backup_refused(self):
        """A message when saves must not be touched now, else ''."""
        if self.running:
            return 'Close the game first: its saves are open while it runs.'
        if self._save_backup_busy:
            return 'Wait for the current save backup to finish.'
        if self._coop_busy:
            return 'Wait for co-op to finish starting.'
        return ''

    def _save_backup_run(self, message, work):
        """WORK(user_dir) in a worker thread; its result (a message) comes back to the GUI thread."""
        refused = self._save_backup_refused()
        if refused:
            self._save_backup_status = refused
            self.saveBackupsChanged.emit()
            return False
        root = self._saves_root()
        self._save_backup_busy = True
        self._save_backup_status = message
        self.saveBackupsChanged.emit()

        def run():
            try:
                result = work(root)
            except (save_backups.BackupError, OSError, ValueError) as error:
                result = str(error)
            except BaseException as error:  # a worker must always report back
                result = f'Save backup failed: {error}'
            self._saveBackupDone.emit(result)
        threading.Thread(target=run, daemon=True).start()
        return True

    @Slot(str)
    def _save_backup_finished(self, message):
        self._save_backup_busy = False
        self._save_backup_status = message
        self.refreshSaveBackups()
        if self._save_restore_pending:
            self._save_restore_pending = False
            self.refresh_profile_data()

    @staticmethod
    def _save_summary(root):
        try:
            return save_backups.character_summary(character.get_characters(str(root)))
        except Exception:
            return ''

    @Slot()
    @Slot(str)
    def backupSavesNow(self, label=''):
        def work(root):
            info = save_backups.create_backup(root, label, 'manual', self._save_summary(root))
            return f"Backed up {info['files']} files to {info['name']}."
        self._save_backup_run('Backing up your saves…', work)

    def _auto_backup_saves(self):
        def work(root):
            info = save_backups.create_backup(root, '', 'auto', self._save_summary(root))
            save_backups.prune_auto(root)
            return f"Saves backed up after playing ({info['name']})."
        if not save_backups.folder_stats(save_backups.savedata_dir(self._saves_root()))[0]:
            return
        self._save_backup_run('Backing up your saves after playing…', work)

    @Slot(str)
    def restoreSaveBackup(self, name):
        def work(root):
            safety = save_backups.restore_backup(root, name, self._save_summary(root))
            kept = f" Your previous saves are in {safety['name']}." if safety else ''
            return f'Restored {name}.{kept}'
        if self._save_backup_run(f'Restoring {name}…', work):
            self._save_restore_pending = True  # the Home dossier reloads with the restored character

    @Slot(str)
    def deleteSaveBackup(self, name):
        try:
            if self._save_backup_busy:  # (a backup may be deleted while the game runs)
                raise save_backups.BackupError('Wait for the current save backup to finish.')
            save_backups.delete_backup(self._saves_root(), name)
            self._save_backup_status = f'Deleted {name}.'
        except (save_backups.BackupError, OSError) as error:
            self._save_backup_status = str(error)
        self.refreshSaveBackups()

    @Slot()
    def openSaveBackups(self):
        folder = save_backups.backups_dir(self._saves_root())
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(str(folder))

    @Slot()
    def refresh_profile_data(self):
        """Load character profile data from save files."""
        try:
            char_mod = character
            try:
                import importlib.util
                char_py = core.PORT_DIR / 'launcher' / 'bbport_character.py'
                if char_py.is_file():
                    spec = importlib.util.spec_from_file_location("bbport_character_dyn", str(char_py))
                    if spec and spec.loader:
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)
                        char_mod = mod
            except Exception:
                char_mod = character

            import bbport_startup
            # Get saves folder configured by user in launcher settings
            save_dir = bbport_startup.saves_folder(self.app, core.DATA_DIR)
            chars = []
            if save_dir and Path(save_dir).exists():
                chars = char_mod.get_characters(str(save_dir))

            if not chars:
                detected = self._find_save_dir()
                if detected and detected != save_dir:
                    chars = char_mod.get_characters(str(detected))

            if chars:
                self._profile_data = chars[0]
            else:
                self._profile_data = {}
        except Exception:
            self._profile_data = {}
        self.profileDataChanged.emit()

    def _find_save_dir(self):
        """Auto-detect common Bloodborne save directory locations."""
        import os

        user_cfg = self.app.get('user_dir')
        common_paths = [
            Path(user_cfg) if user_cfg else None,
            Path(os.path.expandvars('%USERPROFILE%')) / 'OneDrive' / 'Documents' / 'BB',
            Path(os.path.expandvars('%USERPROFILE%')) / 'Documents' / 'BB',
            Path(os.path.expandvars('%USERPROFILE%')) / 'Saves',
            Path(os.path.expandvars('%USERPROFILE%')) / 'AppData' / 'Local' / 'bbport',
            core.DATA_DIR / 'user',
            Path('.') / 'user',
        ]

        for path in common_paths:
            if path and path.exists():
                if (path / 'savedata').exists() or list(path.glob('*/*/SPRJ*')) or list(path.glob('SPRJ*')):
                    return path

        return None

    def refresh_addons(self):
        from mods import discover
        from patches import external_patches
        folder = Path(self.app.get('mods_dir') or core.DATA_DIR / 'mods')
        profile = core.load_json(core.DATA_DIR / 'mods.json', {})
        disabled = set(profile.get('disabled', []))
        names = discover(folder)
        order = [n for n in profile.get('order', []) if n in names]
        order += [n for n in sorted(names) if n not in order]
        self._mods = [{'name': n, 'enabled': n not in disabled} for n in order]
        patch_profile = core.load_json(core.DATA_DIR / 'patches.json', {})
        patch_folder = Path(self.app.get('patches_dir') or core.DATA_DIR / 'patches')
        found = external_patches(patch_folder, core.PATCH_VERSION)
        enabled = set(patch_profile.get('enabled', []))
        denied = set(patch_profile.get('disabled', []))
        self._patches = [{'name': name,
                          'enabled': name in enabled or (name not in denied and
                                       meta.get('isEnabled', 'false').lower() == 'true')}
                         for name, _path, meta in found]
        self.changed.emit()

    @Slot(str, bool)
    def setMod(self, name, enabled):
        profile_file = core.DATA_DIR / 'mods.json'
        profile_file.parent.mkdir(parents=True, exist_ok=True)
        profile = core.load_json(profile_file, {})
        names = [m['name'] for m in self._mods]
        if name not in names:
            return
        disabled = set(profile.get('disabled', []))
        (disabled.discard if enabled else disabled.add)(name)
        profile.update({'order': names, 'disabled': sorted(disabled)})
        profile_file.write_text(json.dumps(profile, indent=2), encoding='utf-8')
        self.refresh_addons()
        self._set_notice('Mod change saved. Restart the game to apply it.')

    @Slot(str, int)
    def moveMod(self, name, step):
        names = [m['name'] for m in self._mods]
        if name not in names:
            return
        index = names.index(name)
        other = index + step
        if not 0 <= other < len(names):
            return
        names[index], names[other] = names[other], names[index]
        profile_file = core.DATA_DIR / 'mods.json'
        profile_file.parent.mkdir(parents=True, exist_ok=True)
        profile = core.load_json(profile_file, {})
        profile['order'] = names
        profile_file.write_text(json.dumps(profile, indent=2), encoding='utf-8')
        self.refresh_addons()

    @Slot(str, bool)
    def setPatch(self, name, enabled):
        profile_file = core.DATA_DIR / 'patches.json'
        profile_file.parent.mkdir(parents=True, exist_ok=True)
        profile = core.load_json(profile_file, {})
        enabled_names = set(profile.get('enabled', []))
        disabled_names = set(profile.get('disabled', []))
        (enabled_names.add if enabled else enabled_names.discard)(name)
        (disabled_names.discard if enabled else disabled_names.add)(name)
        profile.update({'enabled': sorted(enabled_names), 'disabled': sorted(disabled_names)})
        profile_file.write_text(json.dumps(profile, indent=2), encoding='utf-8')
        self.refresh_addons()

    def _mods_dir(self):
        return Path(self.app.get('mods_dir') or core.DATA_DIR / 'mods')

    def _choose_prompt_download(self, choice):
        """The player's own download of a prompt pack: opens its Nexus page, then asks for the
        file. '' when cancelled."""
        _, page, title, creator = core.PROMPT_PACKS[choice]
        webbrowser.open(page)
        source, _ = QFileDialog.getOpenFileName(
            None, f'Choose your {title} download (by {creator}, opened on Nexus Mods)',
            str(Path.home() / 'Downloads'), 'Prompt mod download (*.zip *.7z *.rar common.tpf.dcx);;All files (*)')
        return source

    @Slot(str)
    def setPrompt(self, choice):
        """Xbox and Keyboard: prompt images from Nexus Mods (Dommo's Xbox prompts; JinkiJinn's
        PCBButtons key images, with the keys those images show bound in bbport.ini). The port does
        not ship them: the first time, the player's own download is added to the mods folder
        (core.install_prompt_pack). PlayStation: the game's own."""
        if choice not in ('Xbox', 'PlayStation', 'Keyboard'):
            return
        names = [m['name'] for m in self._mods if self._is_prompt_mod(m['name'])]
        xbox = [n for n in names if n != core.KEYBOARD_PROMPTS]
        if (choice == 'Xbox' and not xbox) or (choice == 'Keyboard' and core.KEYBOARD_PROMPTS not in names):
            _, page, title, creator = core.PROMPT_PACKS[choice]
            source = self._choose_prompt_download(choice)
            if not source:
                self._set_notice(f'{choice} prompts are a separate download: get {title} by {creator} from '
                                 f'{page}, then choose {choice} again and pick the downloaded file.')
                return
            try:
                core.install_prompt_pack(choice, source, self._mods_dir())
            except (OSError, ValueError) as error:
                self._set_notice(str(error))
                return
            self.refresh_addons()
            names = [m['name'] for m in self._mods if self._is_prompt_mod(m['name'])]
            xbox = [n for n in names if n != core.KEYBOARD_PROMPTS]
        profile_file = core.DATA_DIR / 'mods.json'
        profile_file.parent.mkdir(parents=True, exist_ok=True)
        profile = core.load_json(profile_file, {})
        disabled, enabled = set(profile.get('disabled', [])), set(profile.get('enabled', []))
        chosen = {'Xbox': xbox[:1], 'Keyboard': [core.KEYBOARD_PROMPTS]}.get(choice, [])
        for name in names:
            (disabled.discard if name in chosen else disabled.add)(name)
            (enabled.add if name in chosen else enabled.discard)(name)
        profile.update({'enabled': sorted(enabled), 'disabled': sorted(disabled)})
        profile_file.write_text(json.dumps(profile, indent=2), encoding='utf-8')
        if choice == 'Keyboard':  # the keys the images show
            core.save_ini(core.KEYBOARD_PROMPT_LAYOUT, self.ini_lines)
            self.ini, self.ini_lines = core.load_ini()
        self.refresh_addons()
        self._set_notice(f'{choice} button prompts selected. Restart the game to apply them.'
                         + (' Keys now match the prompt images (E interact, Left Shift dodge, Q item, F transform).'
                            if choice == 'Keyboard' else ''))

    # --- HD Texture Pack ---------------------------------------------------------------------
    # The player downloads the pack's Nexus files in their browser (Open on Nexus beside each, then
    # Manual Download); the launcher moves each finished zip from the Downloads folder into the
    # pack's downloads folder, and Build the HD Texture Pack makes the pack (scripts/hd_texture_pack.py).

    def _hd_home(self):
        return core.hd_pack_home(self.app)

    def _hd_downloads(self):
        if self.app.get('hd_pack_downloads'):
            return Path(self.app['hd_pack_downloads'])
        # Without a chosen folder, an hd-pack-downloads folder beside the launcher's folder is used
        # when its own one is missing (the zips kept next to the launcher, not inside it).
        own, beside = self._hd_home() / 'downloads', core.DATA_DIR.resolve().parent / 'hd-pack-downloads'
        return beside if not own.is_dir() and beside.is_dir() else own

    def _hd_pack_info(self):
        try:
            return json.loads((self._hd_home() / HD_PACK / 'pack.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None

    def _hd_move_from_mods(self):
        """Packs built before it had its own folder sit in this launcher's mods folder, which a
        new launcher folder lacks: move them there (a rename on the same drive) with their
        downloads, keeping the switch. A pack that cannot move stays, and its folder is used."""
        legacy = self._mods_dir() / HD_PACK
        home = self._hd_home()
        if not (legacy / 'pack.json').is_file() or (home / HD_PACK).exists():
            return  # nothing to move, already its folder, or a pack is there (this one stays a mod)
        profile_file = core.DATA_DIR / 'mods.json'
        profile = core.load_json(profile_file, {})
        try:
            home.mkdir(parents=True, exist_ok=True)
            os.replace(legacy, home / HD_PACK)
        except OSError as error:
            home = self._mods_dir()  # still loaded once only (mods.py --hd-pack)
            self._append_log(f'HD Texture Pack: left in {legacy} ({error}).\n')
        downloads = core.DATA_DIR / 'downloads' / 'hd-pack'
        if not self.app.get('hd_pack_downloads') and downloads.is_dir():
            try:
                if home == self._mods_dir():
                    raise OSError('pack not moved')
                os.replace(downloads, home / 'downloads')
            except OSError:
                self.app['hd_pack_downloads'] = str(downloads)
        self.app['hd_pack_dir'] = str(home)
        self.app['hd_textures'] = HD_PACK not in profile.get('disabled', [])
        if HD_PACK in profile.get('disabled', []) + profile.get('order', []):
            profile['disabled'] = [n for n in profile.get('disabled', []) if n != HD_PACK]
            profile['order'] = [n for n in profile.get('order', []) if n != HD_PACK]
            profile_file.write_text(json.dumps(profile, indent=2), encoding='utf-8')
        self._write()

    def _hd_script(self):
        sys.path.insert(0, str(core.PORT_DIR / 'scripts'))
        import hd_texture_pack
        return hd_texture_pack

    def _hd_sources(self):
        try:
            return self._hd_script().load_sources(self._hd_downloads())
        except (OSError, ValueError):
            return [], []

    def _hd_listed(self):
        """The sources the pack is built from by default, from hd_pack_sources.json."""
        try:
            listing = json.loads(self._hd_script().SOURCES.read_text(encoding='utf-8'))['sources']
        except (OSError, ValueError, KeyError):
            return []
        return [s for s in listing if s.get('default', True) is not False]

    @Property(bool, notify=changed)
    def hdPackInstalled(self):
        return self._hd_pack_info() is not None

    @Property(bool, notify=changed)
    def hdPackEnabled(self):
        return self.hdPackInstalled and bool(self.app.get('hd_textures', True))

    @Property(bool, notify=changed)
    def hdPackBusy(self):
        return self._hd_process is not None

    @Property(str, notify=changed)
    def hdPackState(self):
        """For the installed indicator: busy, on, off (installed, switched off) or missing."""
        return ('busy' if self.hdPackBusy else 'missing' if not self.hdPackInstalled else
                'on' if self.hdPackEnabled else 'off')

    @Property(float, notify=changed)
    def hdPackProgress(self):
        return self._hd_progress

    @Property(bool, notify=changed)
    def hdPackReady(self):
        """Every download the pack needs is in its downloads folder."""
        found, missing = self._hd_sources()
        return bool(found) and not missing

    @Property(list, notify=changed)
    def hdPackFiles(self):
        """The pack's Nexus files, each with its page and whether its zip is in the folder."""
        found, _missing = self._hd_sources()
        have = {source['id'] for source, _zip in found}
        script = self._hd_script()
        return [{'id': s['id'], 'title': s['title'], 'author': s.get('author', ''), 'file': s['download'],
                 'size': size_text(s.get('size', 0)), 'page': script.nexus_page(s), 'found': s['id'] in have}
                for s in self._hd_listed()]

    @Property(str, notify=changed)
    def hdPackStatus(self):
        if self.hdPackBusy:
            return self._hd_status
        info = self._hd_pack_info()
        found, missing = self._hd_sources()
        if info:
            text = (f"Installed: version {info.get('pack_version', '?')}, {info.get('files', 0)} files from "
                    f"{len(info.get('sources', []))} downloads, built {info.get('built', '')[:10]}, in "
                    f"{self._hd_home()}. Every launcher on this PC uses it, also one you download later.")
            return text
        if missing:
            listed = {s['id']: s for s in self._hd_listed()}
            size = sum(listed[i].get('size', 0) for i in missing if i in listed) / 2**30
            return (f'Not installed. {len(missing)} of {len(found) + len(missing)} files still to download '
                    f'(about {size:.0f} GB): press Open on Nexus beside each, then Manual Download on its page. '
                    f'Finished downloads are moved from {downloads_folder()} into {self._hd_downloads()} by themselves.')
        return f'All {len(found)} downloads found. Build the HD Texture Pack makes it on this PC (a few minutes on an SSD).'

    @Slot(str)
    def hdPackOpenFile(self, source_id):
        """Opens one file's Nexus page; the launcher then watches the browser's Downloads folder for it."""
        page = next((f['page'] for f in self.hdPackFiles if f['id'] == source_id), '')
        if page:
            webbrowser.open(page)
            self._hd_watch()

    def _hd_watch(self):
        """Looks for finished downloads every few seconds while files are missing."""
        if self._hd_timer is None:
            self._hd_timer = QTimer(self)
            self._hd_timer.setInterval(3000)
            self._hd_timer.timeout.connect(self._hd_collect)
        if not self._hd_timer.isActive():
            self._hd_timer.start()
        self._hd_collect()

    def _hd_in_downloads(self):
        """Whether a missing pack file is in the Downloads folder, finished or not."""
        _found, missing = self._hd_sources()
        script = self._hd_script()
        wanted = [s for s in self._hd_listed() if s['id'] in missing]
        try:
            return any(script.is_download(s, path.name) for path in downloads_folder().glob('*.zip') for s in wanted)
        except OSError:
            return False

    def _hd_collect(self):
        """Moves the pack's finished Nexus downloads from the browser's Downloads folder into the
        pack's downloads folder (a rename on the same drive). A file still downloading is left:
        its browser's partial file is beside it (Firefox), or its size is still changing."""
        _found, missing = self._hd_sources()
        if not missing:
            if self._hd_timer:
                self._hd_timer.stop()
            self._hd_auto_build()
            return
        inbox, folder = downloads_folder(), self._hd_downloads()
        try:
            if not inbox.is_dir() or inbox.resolve() == folder.resolve():
                return
            zips = list(inbox.glob('*.zip'))
        except OSError:
            return
        script = self._hd_script()
        wanted = [s for s in self._hd_listed() if s['id'] in missing]
        for path in zips:
            source = next((s for s in wanted if script.is_download(s, path.name)), None)
            if not source or path.name in self._hd_moving:
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            seen, self._hd_seen[path.name] = self._hd_seen.get(path.name), size
            partial = any(path.with_name(path.name + end).exists() for end in ('.part', '.crdownload', '.partial'))
            if partial or not size or (size != source.get('size') and seen != size):
                continue
            wanted.remove(source)
            self._hd_moving.add(path.name)
            threading.Thread(target=self._hd_move, args=(source, path, folder), daemon=True).start()

    def _hd_move(self, source, path, folder):
        try:
            folder.mkdir(parents=True, exist_ok=True)
            try:
                os.replace(path, folder / path.name)
            except OSError:  # another drive: copy under a name the build skips, then rename
                part = folder / (path.name + '.part')
                shutil.copyfile(path, part)
                os.replace(part, folder / path.name)
                path.unlink()
        except OSError as error:
            self.workerNotice.emit(f'Could not move {path.name} into {folder}: {error}')
            return
        finally:
            self._hd_moving.discard(path.name)
        _found, missing = self._hd_sources()
        self.workerNotice.emit(f"{source['title']}: downloaded and moved into {folder}. " +
                               (f'{len(missing)} more to download.' if missing else
                                'Every file is in: press Build the HD Texture Pack.'))
        self.changed.emit()

    @Slot()
    def hdPackInstall(self):
        if self.hdPackBusy:
            return
        game = self.app.get('game_dir')
        if not core.game_info(game):
            self._set_notice('Choose the game folder containing eboot.bin first.')
            return
        _found, missing = self._hd_sources()
        if missing:
            self._set_notice(f'{len(missing)} files still to download: press Open on Nexus beside each.')
            self._hd_watch()
            return
        self._hd_start_build()

    def _hd_auto_build(self):
        """Builds the pack by itself once every download is in and none is built yet: nothing to
        press. Not while the game runs (play waits for the build instead)."""
        if self.hdPackInstalled or self.hdPackBusy or self.process or not self.hdPackReady:
            return
        if core.game_info(self.app.get('game_dir')):
            self._hd_start_build()

    def _hd_start_build(self):
        out = self._hd_home()
        out.mkdir(parents=True, exist_ok=True)
        if not self.app.get('hd_pack_dir'):
            self.app['hd_pack_dir'] = str(out)  # where every launcher looks, wherever it is
            self._write()
        found, _missing = self._hd_sources()
        if not found:
            self._set_notice(f'No HD Texture Pack downloads in {self._hd_downloads()}.')
            return
        need = sum(z.stat().st_size for _, z in found) * 1.2
        free = shutil.disk_usage(out).free
        if free < need:
            self._set_notice(f'Not enough free space: the pack needs about {need / 2**30:.0f} GB on '
                             f'{out.anchor}, {free / 2**30:.0f} GB are free.')
            return
        game = self.app.get('game_dir')
        if core.DATA_DIR.resolve().anchor.casefold() != out.resolve().anchor.casefold():
            self._append_log('HD Texture Pack: its folder and the launcher are on different drives; '
                             'every start will copy the pack. Choose an HD Texture Pack folder on the launcher\'s drive.\n')
        if self.process:
            self._set_notice('Close the game first: building replaces the HD Texture Pack it reads.')
            return
        command = core.script_command('hd_texture_pack.py', '--game', str(game), '--sources',
                                      str(self._hd_downloads()), '--out', str(out), '--progress')
        try:
            self._hd_process = subprocess.Popen(command, cwd=core.PORT_DIR, stdin=subprocess.DEVNULL,
                                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                                encoding='utf-8', errors='replace', creationflags=core.NO_WINDOW)
        except OSError as error:
            self._set_notice(f'Could not start the HD Texture Pack build: {error}')
            return
        self._hd_progress, self._hd_started = 0.0, time.monotonic()
        self._hd_status = 'Checking the downloads…'
        self._set_notice('Building the HD Texture Pack…')
        self.changed.emit()
        process = self._hd_process
        threading.Thread(target=self._hd_read_log, args=(process,), daemon=True).start()
        threading.Thread(target=self._hd_read_progress, args=(process,), daemon=True).start()

    def _hd_read_log(self, process):
        for line in process.stderr:
            self._append_log('HD Texture Pack: ' + line)

    def _hd_read_progress(self, process):
        stages = {'checking downloads': 'Checking the downloads', 'building': 'Building the pack', 'done': 'Done'}
        for line in process.stdout:
            try:
                record = json.loads(line)
                done, total = record['done'], max(1, record['total'])
            except (ValueError, KeyError, TypeError):
                continue
            fraction = min(1.0, done / total)
            self._hd_progress = fraction
            elapsed = time.monotonic() - self._hd_started
            left = ''
            if fraction > 0.03 and record.get('stage') != 'done':
                minutes = elapsed * (1 - fraction) / fraction / 60
                left = f' · about {max(1, round(minutes))} min left'
            where = record.get('file') or ''
            self._hd_status = (f"{stages.get(record.get('stage'), record.get('stage'))}: "
                               f"{fraction:.0%}{left}" + (f' · {where}' if where and record.get('stage') == 'building' else ''))
            self.changed.emit()
        code = process.wait()
        if self._hd_process is not process:
            return
        self._hd_process = None
        self._hd_progress = 0.0
        if code == 0:
            self._hd_status = ''
            self._hd_enable(True)
            message = 'HD Texture Pack installed and switched on. It applies the next time the game starts.'
        else:
            self._hd_status = ''
            message = 'The HD Texture Pack was not installed: see System › Logs.'
        self.workerNotice.emit(message)
        self.changed.emit()

    @Slot()
    def hdPackCancel(self):
        process, self._hd_process = self._hd_process, None
        if process:
            process.terminate()
            self._hd_progress, self._hd_status = 0.0, ''
            self._set_notice('HD Texture Pack build stopped; the pack you had is unchanged.')
            self.changed.emit()

    def _hd_enable(self, enabled):
        self.app['hd_textures'] = bool(enabled)  # settings.json: shared by every launcher
        self._write()
        self.changed.emit()

    @Slot(bool)
    def setHdPack(self, enabled):
        if not self.hdPackInstalled:
            return
        self._hd_enable(enabled)
        self._set_notice(f"High-resolution textures {'on' if enabled else 'off'}. Restart the game to apply.")

    @Property(str, notify=changed)
    def atlasStatus(self):
        if self._atlas_progress:
            return self._atlas_progress
        sys.path.insert(0, str(core.PORT_DIR / 'scripts'))
        import atlas
        return ('Maps ready.' if atlas.ready(core.ATLAS_DIR) else
                'Maps not prepared yet: Prepare maps makes them from your game (5-15 minutes, once).')

    @Slot()
    def prepareAtlas(self):
        """Prepare Hunter's Atlas maps from the game folder (5-15 minutes)."""
        game_dir = self.app.get('game_dir')
        if not game_dir or not core.game_info(game_dir):
            self._set_notice('Choose your game folder first.')
            return
        if self.running:
            self._set_notice('Close the game before preparing maps.')
            return
        self._set_notice('Preparing Hunter\'s Atlas maps (5-15 minutes)…')
        def work():
            try:
                sys.path.insert(0, str(core.PORT_DIR / 'scripts'))
                import atlas
                def progress_callback(msg):
                    if msg:
                        self.workerNotice.emit(str(msg))
                # atlas.prepare() will use exe if available, falls back to Python
                atlas.prepare(str(game_dir), str(core.ATLAS_DIR), progress=progress_callback)
                self.workerNotice.emit('Hunter\'s Atlas maps are ready.')
            except FileNotFoundError as error:
                if 'generate_atlas' in str(error):
                    self.workerNotice.emit('Atlas generator not found. Maps will auto-prepare on first game start.')
                else:
                    self.workerNotice.emit(f'Map preparation failed: {error}')
            except RuntimeError as error:
                self.workerNotice.emit(f'Map generation error: {error}')
            except Exception as error:
                self.workerNotice.emit(f'Unexpected error: {type(error).__name__}: {error}')
            self.changed.emit()
        threading.Thread(target=work, daemon=True).start()

    @Slot()
    def downloadFsr4(self):
        missing = core.fsr4_missing()
        if not missing:
            self._set_notice('FSR 4 assets are already installed.')
            return
        self._set_notice(f'Downloading {len(missing)} FSR 4 files…')
        def work():
            try:
                folder = core.PORT_DIR / 'fsr4_shaders'
                folder.mkdir(parents=True, exist_ok=True)
                for name in missing:
                    part = folder / (name + '.part')
                    with urllib.request.urlopen(f'{core.FSR4_BASE}/{name}', timeout=60) as reply:
                        part.write_bytes(reply.read())
                    part.replace(folder / name)
                self.workerNotice.emit('FSR 4 assets installed.')
            except OSError as error:
                self.workerNotice.emit(f'FSR 4 download failed: {error}')
            self.changed.emit()
        threading.Thread(target=work, daemon=True).start()

    @Slot()
    def downloadFsr4Vk(self):
        folder = core.fsr4vk_dir()
        if core.bbport_fsr4vk.files_ok(folder):
            self._set_notice('FSR 4.1.1 (fsr4vk) is already installed.')
            return
        self._set_notice('Downloading FSR 4.1.1 (fsr4vk, about 14 MB)…')
        def work():
            try:
                core.bbport_fsr4vk.fetch(folder)
                self.workerNotice.emit('FSR 4.1.1 installed. Choose FSR 4.1.1 as the upscaler.')
            except (core.bbport_fsr4vk.FetchError, OSError) as error:
                self.workerNotice.emit(f'FSR 4.1.1 download failed: {error}')
            self.changed.emit()
        threading.Thread(target=work, daemon=True).start()

    @Slot(bool)
    def checkForUpdates(self, manual=True):
        # A manual check answers in the Updates card's status line (Settings) and in the notice
        # (Home): the notice alone was invisible from Settings, where Check now is.
        def tell(message):
            if manual:
                self._updateProgress.emit(message)
                self.workerNotice.emit(message)

        def work():
            try:
                version, url, page = core.latest_release()
                if core.release_is_newer(version):
                    self.updateAvailable.emit(version, url or '', page)
                    tell(f'Version {version.removeprefix("v")} is available (you have {core.VERSION}).')
                else:
                    self.updateAvailable.emit('', '', '')  # forget a remembered one
                    tell(f'You have the latest version ({core.VERSION}).')
            except urllib.request.HTTPError as error:
                if error.code == 404:
                    tell(f'Could not find a published release to compare with (you have {core.VERSION}).')
                else:
                    tell(f'Could not check for updates: {error}')
            except (OSError, ValueError, KeyError) as error:
                tell(f'Could not check for updates: {error}')
        if manual and not self._update_busy:
            self._set_update_status('Checking for updates…')
        threading.Thread(target=work, daemon=True).start()

    @Slot(str, str, str)
    def _offer_update(self, version, url, page):
        if not version:
            if self._update:
                self._update = None
                self._update_ready = None
                self.updateStateChanged.emit()
                self.noticeChanged.emit()
            return
        offered = (version, url or None, page)
        if self._update != offered:
            self._update_ready = None
        self._update = offered
        self._restore_update_download()
        if self.updateReady:
            self._set_notice(f'Version {version.removeprefix("v")} is ready to install.')
        else:
            self._set_notice(f'Version {version.removeprefix("v")} is available.')
        self.updateStateChanged.emit()
        if self.app.get('download_updates') and not self.updateReady:
            self.downloadUpdate()

    @Property(bool, notify=noticeChanged)
    def hasUpdate(self):
        return self._update is not None

    @Property(str, notify=noticeChanged)
    def updateVersion(self):
        """The release as players read it: "1.2.3", not the tag "v1.2.3"."""
        return self._update[0].removeprefix('v') if self._update else ''

    @Property(str, notify=updateStateChanged)
    def updateNotes(self):
        """The offered release's notes (Markdown) from GitHub, as the last check saw them."""
        return core.concise_release_notes(core.cached_release_notes(self._update[0])[0]) if self._update else ''

    @Property(str, notify=updateStateChanged)
    def updateDate(self):
        return core.cached_release_notes(self._update[0])[1] if self._update else ''

    @Property(bool, notify=updateStateChanged)
    def installOffer(self):
        return self._install_offer and self.updateReady

    @Slot()
    def dismissInstallOffer(self):
        self._install_offer = False
        self.updateStateChanged.emit()

    @Property(str, constant=True)
    def currentVersion(self):
        return core.VERSION

    @Property(str, notify=whatsNewChanged)
    def whatsNew(self):
        """This version's short notes, until the player has seen them once after an update."""
        return core.concise_release_notes(self._whats_new) if self._whats_new else ''

    @Slot(result=str)
    def currentReleaseNotes(self):
        return core.concise_release_notes(core.release_notes_section(core.VERSION))

    @Slot(str, result=str)
    def releaseNotesHtml(self, markdown):
        """Release notes for a QML Text: Qt's own Markdown reader, then the page's link colour
        (Text ignores linkColor for Markdown) and no fixed font, so the sheet's font applies."""
        from PySide6.QtGui import QTextDocument
        document = QTextDocument()
        document.setMarkdown(markdown.replace('\r\n', '\n'))
        html = document.toHtml()
        html = re.sub(r'<body style="[^"]*">', '<body>', html)
        html = re.sub(r'color:#0000ff;?', 'color:#8cc8ff;', html)
        return html

    @Slot()
    def dismissWhatsNew(self):
        self._whats_new = ''
        if self.app.get('last_seen_version') != core.VERSION:
            self.app['last_seen_version'] = core.VERSION
            self._write()
        self.whatsNewChanged.emit()

    def _restore_update_download(self):
        try:
            ready = json.loads((core.UPDATE_DIR / 'ready.json').read_text(encoding='utf-8'))
            folder = (core.UPDATE_DIR / 'new' / ready['folder']).resolve()
            folder.relative_to((core.UPDATE_DIR / 'new').resolve())
            version = ready.get('version')
            url = ready.get('url') or None
            if not self._update and isinstance(version, str) and core.release_is_newer(version):
                self._update = (version, url, core.RELEASES_PAGE)
            if self._update and (version, url) == self._update[:2] and (folder / 'Bloodborne.exe').is_file():
                self._update_ready = (*self._update[:2], str(folder))
                self._update_status = f'Version {self._update[0].removeprefix("v")} downloaded. Ready to install.'
                self._notice = f'Version {self._update[0].removeprefix("v")} is ready to install.'
        except (OSError, ValueError, KeyError, TypeError):
            pass

    @Property(bool, notify=updateStateChanged)
    def updateBusy(self):
        return self._update_busy

    @Property(bool, notify=updateStateChanged)
    def updateReady(self):
        return bool(self._update_ready and self._update and
                    self._update_ready[:2] == self._update[:2] and
                    (Path(self._update_ready[2]) / 'Bloodborne.exe').is_file())

    @Property(str, notify=updateStateChanged)
    def updateStatus(self):
        return self._update_status

    @Slot(str)
    def _set_update_status(self, message):
        self._update_status = message
        self.updateStateChanged.emit()

    @Slot(str, str, str)
    def _finish_update_download(self, version, url, result):
        self._update_busy = False
        if result.startswith('error:'):
            self._update_ready = None
            self._set_update_status('Download failed: ' + result[6:])
        elif self._update and self._update[:2] == (version, url):
            self._update_ready = (version, url, result)
            self._set_update_status(f'Version {version.removeprefix("v")} downloaded. Ready to install.')
            self._set_notice(f'Version {version.removeprefix("v")} is ready to install.')
        else:
            self._set_update_status('A newer release is available. Download it before installing.')
            if self.app.get('download_updates'):
                self.downloadUpdate()
        self.updateStateChanged.emit()

    @Slot()
    def viewRelease(self):
        webbrowser.open(core.RELEASES_PAGE)

    @Slot(str)
    def openReleaseLink(self, link):
        """A link in release notes: web links open as they are; the notes' repository paths
        (docs/changelog/...) open on GitHub."""
        if link in ('release:update', 'release:current'):
            # The full notes: the offered release's GitHub page, or this version's.
            page = self._update[2] if link == 'release:update' and self._update else ''
            if not str(page).startswith(core.RELEASES_PAGE):
                page = core.RELEASES_PAGE + ('/tag/v' + core.VERSION if link == 'release:current' else '')
            webbrowser.open(page)
        elif link.startswith(('https://', 'http://')):
            webbrowser.open(link)
        elif link and '..' not in link:
            webbrowser.open(core.RELEASES_PAGE.rsplit('/releases', 1)[0] + '/blob/main/' + link.lstrip('/'))

    @Slot()
    def downloadUpdate(self):
        if not self._update or self._update_busy or self.updateReady:
            return
        version, url, page = self._update
        if not url:
            self._set_update_status('No downloadable package is available. Open Releases.')
            return
        self._update_busy = True
        self._update_ready = None
        self._set_update_status(f'Downloading version {version.removeprefix("v")} in the background…')
        def work():
            try:
                if not core.remove_update_folder():
                    raise OSError('an update is still being installed; try again in a minute')
                core.UPDATE_DIR.mkdir(parents=True, exist_ok=True)
                archive = core.UPDATE_DIR / 'update.zip'
                request = urllib.request.Request(url, headers={'User-Agent': 'bbport-launcher'})
                with urllib.request.urlopen(request, timeout=60) as reply, open(archive, 'wb') as out:
                    total = int(reply.headers.get('Content-Length', 0))
                    received = 0
                    while chunk := reply.read(1 << 20):
                        out.write(chunk)
                        received += len(chunk)
                        progress = f'{received * 100 // total}%' if total else f'{received // (1 << 20)} MB'
                        self._updateProgress.emit(f'Downloading version {version.removeprefix("v")}: {progress}')
                    if total and received != total:
                        raise OSError('the download was incomplete; try again')
                self._updateProgress.emit('Download complete. Preparing the installation…')
                core.extract_update(archive, core.UPDATE_DIR / 'new')
                new = next((p.parent for p in (core.UPDATE_DIR / 'new').rglob('Bloodborne.exe')), None)
                if not new:
                    raise OSError('Bloodborne.exe is missing from the download')
                (core.UPDATE_DIR / 'ready.json').write_text(json.dumps(dict(
                    version=version, url=url, folder=str(new.relative_to(core.UPDATE_DIR / 'new')))), encoding='utf-8')
                self._updateDownloaded.emit(version, url, str(new))
            except (OSError, ValueError, zipfile.BadZipFile) as error:
                self._updateDownloaded.emit(version, url, 'error:' + str(error))
        threading.Thread(target=work, daemon=True).start()

    @Slot()
    @Slot(bool)
    def installUpdate(self, confirmed=False):
        if not self.updateReady or self._update_busy:
            self._set_update_status('Download the update completely before installing.')
            return
        if self.running:
            self._set_update_status('Close the game before updating.')
            return
        if not core.FROZEN:
            self._set_update_status('Install updates from the packaged launcher. Open Releases for manual installation.')
            return
        version = self._update[0]
        if not confirmed and QMessageBox.question(None, 'Bloodborne',
                                f'Install version {version.removeprefix("v")} now? Saves, settings and mods are kept.') != QMessageBox.StandardButton.Yes:
            return
        self._install_offer = False
        new = Path(self._update_ready[2])
        try:
            subprocess.Popen([str(new / 'Bloodborne.exe'), '--install-update', str(core.PORT_DIR), str(os.getpid())],
                             cwd=new, stdin=subprocess.DEVNULL, creationflags=core.NO_WINDOW)
        except OSError as error:
            self._set_update_status(f'Could not start installation: {error}')
            return
        self._update_busy = True
        self._set_update_status('Installing the downloaded update…')
        self.closeRequested.emit()

    @Slot()
    def createShortcut(self):
        if core.FROZEN:
            target, arguments, icon = sys.executable, '', f'{sys.executable},0'
        else:
            pythonw = Path(sys.executable).with_name('pythonw.exe')
            target = str(pythonw if pythonw.exists() else sys.executable)
            arguments = str(Path(core.__file__).resolve())
            icon = str(core.PORT_DIR / 'launcher' / 'bloodborne.ico')
        def ps_string(value):
            return "'" + str(value).replace("'", "''") + "'"
        quoted = chr(34) + arguments + chr(34) if arguments else ''

        def shortcut(folder, name, extra):
            options = ' '.join(part for part in (quoted, extra) if part)
            return (f'$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath("{folder}")'
                    f'+"\\{name}.lnk");'
                    f'$s.TargetPath={ps_string(target)};$s.WorkingDirectory={ps_string(core.PORT_DIR)};'
                    f'$s.IconLocation={ps_string(icon)};'
                    + (f'$s.Arguments={ps_string(options)};' if options else '') + '$s.Save();')
        # The Start Menu entry always opens the launcher, since a plain start may launch the game directly.
        script = shortcut('Desktop', 'Bloodborne', '') + shortcut('Programs', 'Bloodborne (Launcher)', '--launcher')
        result = subprocess.run(['powershell', '-NoProfile', '-Command', script], capture_output=True,
                                creationflags=core.NO_WINDOW)
        self._set_notice('Desktop and Start Menu shortcuts created.' if result.returncode == 0 else
                         result.stderr.decode(errors='replace')[:300])

    @Slot()
    def addToSteam(self):
        import bbport_steam
        steam = bbport_steam.steam_folder()
        if not steam:
            self._set_notice('Steam was not found on this PC.')
            return
        configs = bbport_steam.user_configs(steam)
        if not configs:
            self._set_notice('Steam was not found on this PC or no account has signed in.')
            return
        if core.FROZEN:
            exe, options = core.PORT_DIR / 'Play Bloodborne.exe', ''
        else:
            pythonw = Path(sys.executable).with_name('pythonw.exe')
            exe = pythonw if pythonw.exists() else Path(sys.executable)
            options = f'"{Path(core.__file__).resolve()}" --play'
        self._write()
        restart = False
        if bbport_steam.steam_running():
            if QMessageBox.question(None, 'Bloodborne',
                                    'Steam must close while the game is added. Close Steam now?') != QMessageBox.StandardButton.Yes:
                return
            subprocess.Popen([str(steam / 'steam.exe'), '-shutdown'], creationflags=core.NO_WINDOW)
            for _ in range(60):
                time.sleep(0.5)
                if not bbport_steam.steam_running():
                    break
            else:
                self._set_notice('Steam did not close. Close it yourself and try again.')
                return
            time.sleep(1)
            restart = True
        try:
            for config in configs:
                bbport_steam.add_shortcut(config / 'shortcuts.vdf', 'Bloodborne', str(exe), str(core.PORT_DIR),
                                          str(exe), options)
        except (OSError, ValueError) as error:
            self._set_notice(f'Could not add the game to Steam: {error}')
            return
        if restart:
            os.startfile('steam://open/games')
        self._set_notice('Bloodborne was added to your Steam library.')


    # --- Seamless co-op (experimental): BBSC, hosted on one player's PC over Tailscale -------------

    def _coop_public(self):
        return self.app.get('coop_server') == 'public'

    def _coop_kinds(self):
        """The BBSC packages co-op needs: the server package only to host (not for the public server)."""
        return ('client',) if self._coop_public() else ('client', 'server')

    @Property(str, notify=coopChanged)
    def coopStatus(self):
        if self._coop_status:
            return self._coop_status
        if not all(coop.installed(kind) for kind in self._coop_kinds()):
            size = 100 if self._coop_public() else 130
            return (f'Not set up yet: Download BBSC {coop.VERSION} gets it (about {size} MB) from its '
                    'GitHub release. Play co-op and Start hosting also download it when it is missing.')
        if self._coop_public():
            return ('Ready for the BBSC public server: Play co-op signs you in (or makes your account) '
                    'and starts the game. Ring a bell to meet other hunters.')
        if self._coop_host.running:
            return f'Hosting on {self._coop_host.address}. Send your friend the invite code.'
        return "Ready. Host a session, or paste a host's invite code and play."

    @Property(list, notify=coopChanged)
    def coopChecks(self):
        """The last "Check connection": [{label, ok, detail}] (coop.connection_checks)."""
        return self._coop_checks

    @Property(bool, notify=coopChanged)
    def coopChecking(self):
        return self._coop_checking

    @Property(list, notify=coopChanged)
    def coopEvents(self):
        """BBSC's newest session's connection lines (coop.connection_events); refreshCoopEvents."""
        return self._coop_events

    @Slot(str)
    def checkCoopConnection(self, role):
        """Checks BBSC, the firewall rule, the network and the host's ports (role 'host' or 'join'),
        off the UI thread; coopChecks has the rows when it is done."""
        if self._coop_checking:
            return
        self._coop_checking = True
        self.coopChanged.emit()
        try:
            game = self._coop_game_exe()
        except coop.CoopError:
            game = core.PORT_DIR / 'bin' / 'bb-probe.exe'
        invite, hosting, public = self.app.get('coop_invite', ''), self._coop_host.running, self._coop_public()

        def run():
            try:
                rows = coop.connection_checks(game, role, invite, hosting, public)
            except Exception as error:  # a check must never take the launcher down
                rows = [('Connection check', False, f'{type(error).__name__}: {error}')]
            self._coopChecked.emit([{'label': l, 'ok': bool(ok), 'detail': d} for l, ok, d in rows])

        threading.Thread(target=run, daemon=True).start()

    @Property(bool, notify=coopChanged)
    def coopFirewallMissing(self):
        """The last check found this game's firewall rule missing (Open ports makes it)."""
        return any(row['label'].startswith('Firewall rule') and not row['ok'] for row in self._coop_checks)

    @Slot(str)
    def openCoopPorts(self, role):
        """Opens this PC's co-op ports: the firewall rules co-op makes (coop.run_setup, or
        run_public_setup for the public server), with one Windows administrator prompt, then
        checks the connection again. Rerunning it replaces the rules, so it also repairs them."""
        public = self._coop_public()
        invite, hosting = self.app.get('coop_invite', ''), self._coop_host.running

        def work():
            try:
                game = self._coop_game_exe()
                self._coop_progress('Say Yes to the Windows prompt to open the co-op ports…')
                (coop.run_public_setup if public else coop.run_setup)(game)
            except Exception as error:
                self._coopPortsDone.emit(False, str(error) or type(error).__name__)
                raise
            rows = coop.connection_checks(game, role, invite, hosting, public)
            self._coopChecked.emit([{'label': l, 'ok': bool(ok), 'detail': d} for l, ok, d in rows])
            text = ('Ports opened: Windows firewall now allows co-op from '
                    + ('any address.' if public else 'Tailscale and your home network.'))
            self._coopPortsDone.emit(True, text)
            return text
        if self._coop_busy:
            return
        self._coop_ports = {'state': 'working', 'text': 'Waiting for the Windows prompt…'}
        self._coop_run('Opening the co-op ports…', work)

    @Property('QVariantMap', notify=coopChanged)
    def coopPortsResult(self):
        """Open ports' last result beside the button: {state: ''|'working'|'ok'|'failed', text}."""
        return self._coop_ports

    @Slot(bool, str)
    def _coop_ports_done(self, ok, text):
        self._coop_ports = {'state': 'ok' if ok else 'failed', 'text': text}
        self.coopChanged.emit()

    @Slot(list)
    def _coop_checks_done(self, rows):
        self._coop_checks = rows
        self._coop_checking = False
        self.coopChanged.emit()

    @Slot()
    def refreshCoopEvents(self):
        events = coop.connection_events()
        if events != self._coop_events:
            self._coop_events = events
            self.coopChanged.emit()

    @Property(bool, notify=coopChanged)
    def coopInstalled(self):
        """BBSC's packages this co-op choice needs are downloaded (coop.installed)."""
        return all(coop.installed(kind) for kind in self._coop_kinds())

    @Property(str, notify=coopChanged)
    def coopVersion(self):
        return coop.VERSION

    @Property(str, notify=coopChanged)
    def coopInvite(self):
        return self._coop_invite

    @Property(bool, notify=coopChanged)
    def coopHosting(self):
        return self._coop_host.running

    @Property(bool, notify=coopChanged)
    def coopBusy(self):
        return self._coop_busy

    def _coop_run(self, message, work):
        if self._coop_busy:
            return
        self._coop_busy = True
        self._coop_status = message
        self.coopChanged.emit()

        def run():
            try:
                result = work()
            except (coop.CoopError, OSError, ValueError) as error:
                result = f'Co-op: {error}'
            except Exception as error:  # download and process errors: report, never crash the UI
                result = f'Co-op: {type(error).__name__}: {error}'
            self._coopDone.emit(result or '')

        threading.Thread(target=run, daemon=True).start()

    @Slot(str)
    def _coop_finished(self, message):
        self._coop_busy = False
        self._coop_status = message
        self.coopChanged.emit()
        env, self._coop_launch_env = self._coop_launch_env, None
        if env:
            self.play(env)

    def _coop_progress(self, text):
        self._coopProgress.emit(text)  # from the worker thread: queued to the UI thread

    @Slot(str)
    def _coop_show_progress(self, text):
        self._coop_status = text
        self.coopChanged.emit()

    def _coop_ensure_packages(self, kinds=None):
        for kind in (kinds or self._coop_kinds()):
            if not coop.installed(kind):
                coop.download(kind, progress=self._coop_progress)

    def _coop_game_exe(self):
        for candidate in (core.PORT_DIR / 'bin' / 'bb-probe.exe', core.PORT_DIR / 'out' / 'bb-probe.exe'):
            if candidate.is_file():
                return candidate
        raise coop.CoopError('bb-probe.exe is missing from this install.')

    def _coop_account(self):
        return self.app.get('coop_name', '').strip(), self.app.get('coop_password', '')

    @Slot()
    def openCoopHelp(self):
        webbrowser.open(coop.RELEASES)

    @Slot()
    def coopSetup(self):
        def work():
            for kind in self._coop_kinds():
                coop.download(kind, progress=self._coop_progress)
            if self._coop_public():
                return f'Co-op is set up (BBSC {coop.VERSION}). Press Play co-op to join the public server.'
            return f'Co-op is set up (BBSC {coop.VERSION}). Host a session, or paste an invite code and play.'
        self._coop_run('Downloading BBSC…', work)

    @Slot()
    def coopStartHosting(self):
        name, password = self._coop_account()
        if not name or not password:
            self._coop_status = 'Fill in your co-op name and password first; they make your account on your server.'
            self.coopChanged.emit()
            return

        def work():
            self._coop_ensure_packages()
            address, network = coop.host_address()
            if not address:
                raise coop.CoopError('No network found. Connect Tailscale, then try again.')
            game = self._coop_game_exe()
            if not coop.setup_done(game):
                self._coop_progress('First time: say Yes to the Windows prompt (firewall and C++ runtime)…')
                coop.run_setup(game)
            key = coop.registration_key()
            self._coop_host.start(address)
            how = coop.create_account(address, key, name, password)
            self._coop_invite = coop.make_invite(address, key)
            return (f'Hosting on {network} ({address}); your account is {how}. Copy the invite code '
                    'for your friend, then press Play co-op. Keep this launcher open while you play.')
        self._coop_run('Starting the co-op servers…', work)

    @Slot()
    def coopStopHosting(self):
        self._coop_host.stop()
        self._coop_invite = ''
        self._coop_status = 'Stopped hosting.'
        self.coopChanged.emit()

    @Slot()
    def coopCopyInvite(self):
        if self._coop_invite:
            QGuiApplication.clipboard().setText(self._coop_invite)
            self._coop_status = 'Invite code copied. Send it to your friend in a private message.'
            self.coopChanged.emit()

    @Slot()
    def coopPlay(self):
        if self._setup_running:
            self._set_notice('Wait for the game files to finish installing.')
            return
        if self._hd_process:
            self._set_notice('Wait for the HD Texture Pack to finish installing (or cancel it).')
            return
        if self.process or self._coop_busy:
            return
        name, password = self._coop_account()
        if not name or not password:
            self._coop_status = 'Fill in your co-op name and password first.'
            self.coopChanged.emit()
            return
        if self._coop_public():
            self._write()
            self._coop_run('Getting co-op ready…', lambda: self._coop_play_public(name, password))
            return
        if self._coop_host.running:
            address, key = self._coop_host.address, coop.registration_key()
        else:
            try:
                address, key = coop.read_invite(self.app.get('coop_invite', ''))
            except coop.CoopError as error:
                self._coop_status = f'{error}. Or host a session yourself.'
                self.coopChanged.emit()
                return
        self._write()

        def work():
            self._coop_ensure_packages(('client', 'server'))
            game = self._coop_game_exe()
            if not coop.setup_done(game):
                self._coop_progress('First time: say Yes to the Windows prompt (firewall)…')
                coop.run_setup(game)
            coop.create_account(address, key, name, password)
            backup = coop.backup_saves(self.app.get('user_dir') or core.DATA_DIR / 'user')
            fps_mode = str(self.app.get('coop_fps') or self.app.get('coop_frame_rate') or '60')
            vblank = {'120': 120, '144': 144, '90': 90, '60': 60, '30': 30, 'uncap': None}.get(fps_mode, 60)
            base_env = core.game_environment(self.app, self.ini)
            base_env['BB_FPS'] = fps_mode
            if vblank is not None:
                base_env['BB_VBLANK_HZ'] = str(vblank)
            self._coop_launch_env = coop.co_op_environment(base_env, address,
                                                           name, password, game, save_copy=backup, vblank=vblank, fps=fps_mode)
            where = f' Saves backed up to {backup}.' if backup else ''
            return f'Starting co-op with {address}. Host: ring the Hunt Bell. Guest: ring the Kin Bell.{where}'
        self._coop_run('Getting co-op ready…', work)

    def _coop_play_public(self, name, password):
        """Play co-op on the BBSC public server (worker thread): its card, the firewall rule that
        lets other players reach this game, the account, then the game."""
        self._coop_ensure_packages(('client',))
        game = self._coop_game_exe()
        server = coop.public_server()
        address = coop.resolve_ipv4(server['host'])
        if not coop.public_setup_done(game):
            self._coop_progress('First time: say Yes to the Windows prompt (lets other players '
                                'connect to your game)…')
            coop.run_public_setup(game)
        how = coop.create_account(address, server['key'], name, password, public=True)
        backup = coop.backup_saves(self.app.get('user_dir') or core.DATA_DIR / 'user')
        fps_mode = str(self.app.get('coop_fps') or self.app.get('coop_frame_rate') or '60')
        vblank = {'120': 120, '144': 144, '90': 90, '60': 60, '30': 30, 'uncap': None}.get(fps_mode, 60)
        base_env = core.game_environment(self.app, self.ini)
        base_env['BB_FPS'] = fps_mode
        if vblank is not None:
            base_env['BB_VBLANK_HZ'] = str(vblank)
        self._coop_launch_env = coop.co_op_environment(base_env, address,
                                                       name, password, game, save_copy=backup, vblank=vblank, fps=fps_mode)
        where = f' Saves backed up to {backup}.' if backup else ''
        return (f'Starting co-op on the BBSC public server ({server["host"]}) as {name} (account '
                f'{how}). Host: ring the Hunt Bell. Guest: ring the Kin Bell.{where}')

    def shutdown_coop(self):
        """The launcher is closing: hosted servers stop with it."""
        self._coop_host.stop()

    # --- The Hunter's Dream (BB_NET_BACKEND=thd): Discord sign-in by device code -------------------

    @Property(bool, constant=True)
    def huntersDreamPool(self):
        return core.HUNTERS_DREAM_POOL

    # --- Play mode: what PLAY starts (offline, The Hunter's Dream, seamless co-op) ----------------

    @Property(str, notify=playModeChanged)
    def playMode(self):
        return core.play_mode(self.app)

    @Slot(str)
    def setPlayMode(self, mode):
        if mode not in core.PLAY_MODES:
            return
        self.app['play_mode'] = mode
        # The game's online switch follows: on for The Hunter's Dream; co-op launches turn it on
        # for themselves, pointed at the host.
        self.app['online'] = mode == 'huntersdream'
        if mode == 'huntersdream':
            self.app['online_pool'] = 'huntersdream'
        self._write()
        self.playModeChanged.emit()

    def _coop_ready(self):
        name, password = self._coop_account()
        return bool(name and password and (self._coop_public() or self._coop_host.running
                                           or self.app.get('coop_invite', '').strip()))

    @Property(bool, notify=playModeChanged)
    def playModeBlocked(self):
        mode = self.playMode
        if mode == 'huntersdream':
            return not self.thdSignedIn
        if mode == 'coop':
            return not self._coop_ready()
        return False

    @Property(str, notify=playModeChanged)
    def playModeSummary(self):
        """One line under PLAY: what it will start."""
        mode = self.playMode
        if mode == 'huntersdream':
            if self.thdSignedIn:
                return f"Online on The Hunter's Dream as {self.app.get('thd_online_id')}: messages, bloodstains and summons with everyone."
            return "Online on The Hunter's Dream: sign in with Discord first (Settings → Online)."
        if mode == 'coop':
            name, password = self._coop_account()
            if not name or not password:
                return 'Seamless co-op: choose a co-op name and password first (Settings → Co-op).'
            if self._coop_public():
                fps_mode = str(self.app.get('coop_fps') or self.app.get('coop_frame_rate') or '60')
                return f'Seamless co-op on the BBSC public server as {name} (BBSC {coop.VERSION}, {fps_mode} FPS).'
            if self._coop_host.running:
                return f'Seamless co-op: you host on {self._coop_host.address}; send your friends the invite code.'
            if self.app.get('coop_invite', '').strip():
                return "Seamless co-op: joining your host's server from the invite code."
            return "Seamless co-op: start hosting, or paste a host's invite code (Settings → Co-op)."
        return 'Offline: your own world, no servers.'

    @Property(list, notify=playModeChanged)
    def playModeSettings(self):
        """Where the setting that blocks PLAY is: [category, section]."""
        if self.playMode == 'huntersdream':
            return ['Online', "The Hunter's Dream"]
        if self.playMode == 'coop':
            name, password = self._coop_account()
            return ['Co-op', 'Seamless co-op' if not (name and password) or self._coop_public()
                    else 'Host a session']
        return ['Online', "The Hunter's Dream"]

    @Slot()
    def playSelected(self):
        """PLAY: the selected mode."""
        if self.playMode == 'coop':
            self.coopPlay()
        else:
            self.play()

    @Property(bool, notify=thdChanged)
    def thdSignedIn(self):
        return bool(self.app.get('thd_token') and self.app.get('thd_online_id'))

    @Property(str, notify=thdChanged)
    def thdStatus(self):
        if self._thd_status:
            return self._thd_status
        if self.thdSignedIn:
            return f"Signed in to The Hunter's Dream as {self.app.get('thd_online_id')}."
        return "Not signed in to The Hunter's Dream."

    @Property(str, notify=thdChanged)
    def thdCode(self):
        return self._thd_code

    @Property(bool, notify=thdChanged)
    def thdBusy(self):
        return self._thd_busy

    @Slot()
    def thdSignIn(self):
        if self._thd_busy:
            return
        self._thd_busy, self._thd_cancel, self._thd_code = True, False, ''
        self._thd_status = 'Starting the sign-in…'
        self.thdChanged.emit()
        game = self.app.get('online_community', '')

        def on_code(page, code):
            self._thdUpdate.emit('On the page that opened, sign in with Discord and approve this code '
                                 '(not in its "code from the game" box):', code)
            webbrowser.open(page)

        def work():
            try:
                name, token = core.thd_sign_in(game, on_code, lambda: self._thd_cancel)
            except (OSError, ValueError) as error:
                self._thdDone.emit(f'Sign-in failed: {core.connection_error_text(error)}', '', '')
                return
            self._thdDone.emit('', name, token)
        threading.Thread(target=work, daemon=True).start()

    @Slot(str, str)
    def _thd_update(self, status, code):
        self._thd_status, self._thd_code = status, code
        self.thdChanged.emit()

    @Slot(str, str, str)
    def _thd_finished(self, error, name, token):
        self._thd_busy, self._thd_code = False, ''
        if error:
            self._thd_status = error
        else:
            self.app['thd_online_id'], self.app['thd_token'] = name, token
            self._thd_status = ''
            self._write()
        self.thdChanged.emit()

    @Slot()
    def thdCancel(self):
        self._thd_cancel = True
        self._thd_status = 'Cancelling…'
        self.thdChanged.emit()

    @Slot()
    def thdSignOut(self):
        self.app['thd_online_id'], self.app['thd_token'] = '', ''
        self._thd_status = "Signed out of The Hunter's Dream on this PC."
        self._write()
        self.thdChanged.emit()

    @Slot()
    def thdCopyCode(self):
        if self._thd_code:
            QGuiApplication.clipboard().setText(self._thd_code)
            self._set_notice('Sign-in code copied.')

    @Slot()
    def openShadNetRegistration(self):
        webbrowser.open('https://shadps4.net/shadnet/register/')

    @Slot()
    def testConnection(self):
        self._set_notice("Testing The Hunter's Dream…")
        online_id, token = (self.app.get('thd_online_id', ''), self.app.get('thd_token', '')) \
            if self.thdSignedIn else ('', '')

        def work():
            community = core.community_address(self.app['online_community'])
            result = core.server_check_hunters_dream(community)
            result += '\n' + core.thd_account_check(community, online_id, token)
            self.connectionResult.emit(result)
        threading.Thread(target=work, daemon=True).start()

    @Slot(str)
    def _show_connection_result(self, result):
        QMessageBox.information(None, 'Online connection', result)
        self._set_notice('Online connection test finished.')

    @Slot(str)
    def action(self, name):
        if name == 'openGame':
            self.openFolder('game_dir')
        elif name == 'openSaves':
            self.openFolder('user_dir')
        elif name == 'openMods':
            self.openFolder('mods_dir')
        elif name == 'openPort':
            self.openFolder('')
        elif name == 'openConfig':
            self._write()
            os.startfile(str(core.ini_path()))
        elif name == 'mod19':
            webbrowser.open('https://www.nexusmods.com/bloodborne/mods/19')
        elif name == 'releases':
            webbrowser.open(core.RELEASES_PAGE)
        elif name == 'clearCache':
            if self.running:
                self._set_notice('Close the game before clearing its cache.')
                QMessageBox.warning(None, 'Cannot Clear Cache', 'Please close the game before clearing its shader cache.')
            else:
                user_base = Path(self.app.get('user_dir') or core.DATA_DIR / 'user')
                for folder_name in ('shader', 'cache', 'vk_cache', 'shaders'):
                    target = user_base / folder_name
                    if target.exists():
                        shutil.rmtree(target, ignore_errors=True)
                port_user = core.PORT_DIR / 'user'
                if port_user.resolve() != user_base.resolve():
                    for folder_name in ('shader', 'cache', 'vk_cache', 'shaders'):
                        target = port_user / folder_name
                        if target.exists():
                            shutil.rmtree(target, ignore_errors=True)
                self._set_notice('Shader cache cleared. The next launch will rebuild it.')
                QMessageBox.information(None, 'Shader Cache Cleared', 'Shader cache has been cleared successfully.\nShaders will be recompiled on the next launch.')
        elif name == 'copyLog':
            QGuiApplication.clipboard().setText(self._log)
            self._set_notice('Log copied to clipboard.')
        elif name == 'clearLog':
            self._log = ''
            self.logChanged.emit()

