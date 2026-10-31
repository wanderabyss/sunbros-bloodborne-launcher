import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import bbport_launcher_win as core
import bbport_launcher_backend
from bbport_launcher_backend import HD_PACK, LauncherBackend


class HdPackIndicatorTests(unittest.TestCase):
    """Home and Visuals show whether the HD Texture Pack is installed (hdPackState), and the pack's
    Nexus files the player downloads in their browser are moved from Downloads into its folder."""

    def setUp(self):
        parent = Path(__file__).resolve().parents[1] / 'out'
        parent.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.temporary.name)
        self.patches = [patch.object(core, 'CONFIG_DIR', self.root),
                        patch.object(core, 'CONFIG_FILE', self.root / 'settings.json'),
                        patch.object(core, 'DATA_DIR', self.root),
                        patch.dict(os.environ, {'BB_CONFIG': str(self.root / 'bbport.ini')}),
                        patch.dict(core.APP_DEFAULTS, {'check_updates': False, 'mods_dir': '',
                                                       'game_dir': str(self.root / 'missing')}),
                        patch.object(bbport_launcher_backend, 'downloads_folder', lambda: self.root / 'Downloads'),
                        patch.object(LauncherBackend, '_detect_gpu', lambda self: None)]
        for active in self.patches:
            active.start()
        self.backend = LauncherBackend()

    def tearDown(self):
        for active in reversed(self.patches):
            active.stop()
        self.temporary.cleanup()

    def make_pack(self, folder):
        pack = folder / HD_PACK
        (pack / 'dvdroot_ps4' / 'map').mkdir(parents=True)
        (pack / 'dvdroot_ps4' / 'map' / 'placeholder.txt').write_text('x', encoding='utf-8')
        (pack / 'pack.json').write_text(json.dumps({'pack_version': '1', 'files': 1}), encoding='utf-8')
        return pack

    def test_remastered_persists_dlss_quality_and_enables_installed_pack_with_mods_off(self):
        self.backend.app.update(hd_pack_dir=str(self.root / 'shared'), hd_textures=False, mods_enabled=False)
        pack = self.make_pack(self.root / 'shared')
        self.backend.ini.update(upscaler='fsr3', preset='3', object_motion='0', ray_tracing='off')
        self.backend.applyGraphicsPreset('remastered')
        saved, _ = core.load_ini()
        self.assertEqual((saved['upscaler'], saved['preset'], saved['object_motion'], saved['ray_tracing']),
                         ('dlss', '1', '1', 'ultra'))
        self.assertEqual(self.backend.graphicsPreset, 'remastered')
        self.assertEqual(self.backend.hdPackState, 'on')
        self.assertFalse(self.backend.app['mods_enabled'])
        self.assertEqual(core.game_environment(self.backend.app)['BB_HD_PACK'], str(pack))

    def test_states(self):
        self.backend.app['hd_pack_dir'] = str(self.root / 'shared')
        self.assertEqual(self.backend.hdPackState, 'missing')
        self.make_pack(self.root / 'shared')
        self.assertEqual(self.backend.hdPackState, 'on')
        self.backend.setHdPack(False)
        self.assertEqual(self.backend.hdPackState, 'off')
        self.assertFalse(json.loads((self.root / 'settings.json').read_text(encoding='utf-8'))['hd_textures'])
        self.backend._hd_process = object()
        self.assertEqual(self.backend.hdPackState, 'busy')
        self.backend._hd_process = None

    def test_game_gets_the_pack_from_its_own_folder_while_on(self):
        settings = {**core.app_settings({}), 'hd_pack_dir': str(self.root / 'shared')}
        self.assertNotIn('BB_HD_PACK', core.game_environment(settings))
        pack = self.make_pack(self.root / 'shared')
        self.assertEqual(core.game_environment(settings)['BB_HD_PACK'], str(pack))
        self.assertNotIn('BB_HD_PACK', core.game_environment({**settings, 'hd_textures': False}))
        self.assertIn('BB_HD_PACK', core.game_environment({**settings, 'mods_enabled': False}))

    def test_default_folder_is_outside_the_launcher(self):
        home = core.hd_pack_home(core.app_settings({}))
        self.assertNotIn(self.root.resolve(), home.resolve().parents)
        self.assertEqual(home.anchor.casefold(), self.root.resolve().anchor.casefold())

    def test_pack_in_the_mods_folder_moves_to_its_own_folder(self):
        self.make_pack(self.root / 'mods')
        (self.root / 'downloads' / 'hd-pack').mkdir(parents=True)
        (self.root / 'downloads' / 'hd-pack' / 'a.zip').write_bytes(b'zip')
        (self.root / 'mods.json').write_text(json.dumps({'disabled': [HD_PACK, 'Other'], 'order': [HD_PACK]}),
                                             encoding='utf-8')
        shared = self.root / 'shared'
        with patch.object(core, 'hd_pack_home', lambda s: Path(s.get('hd_pack_dir') or shared)):
            backend = LauncherBackend()
            self.assertEqual(backend.hdPackState, 'off')  # it was switched off as a mod
        self.assertTrue((shared / HD_PACK / 'pack.json').is_file())
        self.assertFalse((self.root / 'mods' / HD_PACK).exists())
        self.assertTrue((shared / 'downloads' / 'a.zip').is_file())
        profile = json.loads((self.root / 'mods.json').read_text(encoding='utf-8'))
        self.assertEqual((profile['disabled'], profile['order']), (['Other'], []))
        saved = json.loads((self.root / 'settings.json').read_text(encoding='utf-8'))
        self.assertEqual((saved['hd_pack_dir'], saved['hd_textures']), (str(shared), False))

    def collect(self):
        """One look at Downloads, then waits for the moves it started."""
        self.backend._hd_collect()
        while self.backend._hd_moving:
            time.sleep(0.01)

    def test_downloads_beside_the_launcher_build_by_themselves(self):
        beside = self.root / 'hd-pack-downloads'
        self.backend.app['hd_pack_dir'] = str(self.root / 'pack')
        with patch.object(core, 'DATA_DIR', self.root / 'launcher'):
            self.assertNotEqual(self.backend._hd_downloads(), beside)
            beside.mkdir()
            try:
                self.assertEqual(self.backend._hd_downloads(), beside)
                self.backend.app['hd_pack_downloads'] = str(self.root / 'chosen')
                self.assertEqual(self.backend._hd_downloads(), self.root / 'chosen')
            finally:
                beside.rmdir()
        started = []
        with patch.object(LauncherBackend, '_hd_start_build', lambda self: started.append(True)), \
                patch.object(core, 'game_info', lambda game: {'title': 'x'}):
            with patch.object(LauncherBackend, 'hdPackReady', False):
                self.backend._hd_auto_build()
            self.assertEqual(started, [])
            with patch.object(LauncherBackend, 'hdPackReady', True):
                self.backend._hd_auto_build()
                self.assertEqual(started, [True])
                self.make_pack(self.root / 'pack')
                self.backend._hd_auto_build()  # built already
            self.assertEqual(started, [True])

    def test_files_link_to_their_nexus_file(self):
        self.backend.app['hd_pack_downloads'] = str(self.root / 'hd-downloads')
        files = {f['id']: f for f in self.backend.hdPackFiles}
        self.assertEqual(set(files), {'R0', 'R1', 'R2', 'R3', 'SKY', 'SFX'})
        self.assertEqual(files['R0']['page'], 'https://www.nexusmods.com/bloodborne/mods/503?tab=files&file_id=2665')
        self.assertEqual((files['SFX']['size'], files['R0']['size']), ('64 MB', '3.8 GB'))
        self.assertFalse(any(f['found'] for f in files.values()))

    def test_finished_downloads_move_into_the_pack_downloads_folder(self):
        inbox, folder = self.root / 'Downloads', self.root / 'hd-downloads'
        self.backend.app['hd_pack_downloads'] = str(folder)
        inbox.mkdir()
        sfx = inbox / 'SFX Texture Overhaul-430-1-0-1700000000.zip'
        sfx.write_bytes(b'z' * 10)
        firefox = inbox / 'BBReborne Texture 0-503-1-0-1700000000.zip'
        firefox.write_bytes(b'')  # Firefox's empty file while the .part fills
        (inbox / (firefox.name + '.part')).write_bytes(b'z' * 5)
        other = inbox / 'Something else-99-1-0.zip'
        other.write_bytes(b'z')
        self.collect()
        self.assertTrue(sfx.exists())  # not the listed size: moved once it stops growing
        self.collect()
        self.assertFalse(sfx.exists())
        self.assertTrue((folder / sfx.name).is_file())
        self.assertTrue(firefox.exists() and other.exists())
        self.assertEqual({f['id'] for f in self.backend.hdPackFiles if f['found']}, {'SFX'})
        self.assertTrue(self.backend._hd_in_downloads())
        self.assertFalse(self.backend.hdPackReady)
