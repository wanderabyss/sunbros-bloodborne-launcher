from pathlib import Path
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import bbport_launcher_win as core


class GraphicsPresetTests(unittest.TestCase):
    def defaults(self):
        return dict(core.INI_DEFAULTS), dict(core.APP_DEFAULTS)

    def test_presets_only_use_settings_that_exist(self):
        for name, values in core.GRAPHICS_PRESETS.items():
            with self.subTest(name=name):
                for key, value in values.items():
                    self.assertTrue(key in core.INI_DEFAULTS or key in core.APP_DEFAULTS, key)
                self.assertIn(name, core.GRAPHICS_PRESET_INFO)
                self.assertIn(values['preset'], [v for v, _ in core.PRESETS])
                self.assertIn(values['model_lod'], [v for v, _ in core.LODS])
                self.assertIn(values['fps_mode'], [v for v, _ in core.FPS_MODES])

    def test_shipped_defaults_are_balanced_and_overrides_are_custom(self):
        ini, app = self.defaults()
        self.assertEqual(core.graphics_preset_of(ini, app), 'balanced')
        core.apply_graphics_preset('ultra', ini, app)
        self.assertEqual(core.graphics_preset_of(ini, app), 'ultra')
        ini['effect_ssr'] = '0'
        self.assertEqual(core.graphics_preset_of(ini, app), 'custom')

    def test_remastered_restores_dlss_quality_and_maximum_detail_from_custom_settings(self):
        ini, app = self.defaults()
        ini.update(upscaler='fsr3', preset='3', dlss_model='K', object_motion='0',
                   model_lod='2', effect_ssao='0', effect_dynamic_shadows='0', effect_ssr='0',
                   ray_tracing='off', rt_ao_strength='0.00', anisotropic_filtering='game',
                   frame_gen='fsr3', reflex='off', output_res='2560x1440',
                   effect_dof='0', effect_motion_blur='0')
        core.apply_graphics_preset('remastered', ini, app)
        self.assertEqual((ini['upscaler'], ini['preset'], ini['dlss_model']), ('dlss', '1', 'auto'))
        self.assertEqual((ini['object_motion'], ini['ray_tracing'], ini['rt_ao_strength']), ('1', 'ultra', '1.00'))
        self.assertEqual((ini['model_lod'], ini['anisotropic_filtering']), ('-2', '16'))
        self.assertEqual((ini['effect_ssao'], ini['effect_dynamic_shadows'], ini['effect_ssr']), ('1', '1', '1'))
        self.assertEqual((ini['frame_gen'], ini['reflex'], ini['frame_gen_multiplier'], ini['frame_gen_fit_display']),
                         ('dlss', 'on', '2', '1'))
        self.assertEqual(app['fps_mode'], '60')
        self.assertEqual((ini['output_res'], ini['effect_dof'], ini['effect_motion_blur']), ('2560x1440', '0', '0'))
        self.assertEqual(core.graphics_preset_of(ini, app), 'remastered')

    def test_remastered_label_requires_dlss_quality_and_its_dependencies(self):
        ini, app = self.defaults()
        core.apply_graphics_preset('remastered', ini, app)
        for key, value in [('upscaler', 'fsr3'), ('preset', '2'), ('object_motion', '0'),
                           ('ray_tracing', 'off'), ('frame_gen', 'fsr3'), ('effect_ssr', '0')]:
            with self.subTest(key=key):
                changed = {**ini, key: value}
                self.assertEqual(core.graphics_preset_of(changed, app), 'custom')

    def test_remastered_clears_conflicting_fps_overrides_and_preserves_other_variables(self):
        ini, app = self.defaults()
        core.apply_graphics_preset('remastered', ini, app)
        app.update(extra_env='BB_FPS=uncap BB_GPU_PROFILE=1 BB_FPS_LIMIT=120 BB_VBLANK_HZ=120 BB_FPS=90',
                   frame_cap='120')
        self.assertEqual(core.effective_fps_mode(app), '90')
        self.assertEqual(core.graphics_preset_of(ini, app), 'custom')
        core.apply_graphics_preset('remastered', ini, app)
        self.assertEqual(app['extra_env'], 'BB_GPU_PROFILE=1')
        self.assertEqual(app['frame_cap'], '')
        self.assertEqual(core.effective_fps_mode(app), '60')
        env = core.game_environment(app, ini)
        self.assertEqual(env['BB_FPS'], '60')
        self.assertNotIn('BB_VBLANK_HZ', env)
        self.assertEqual(env['BB_GPU_PROFILE'], '1')
        self.assertEqual(core.graphics_preset_of(ini, app), 'remastered')

    def test_preset_leaves_upscaler_output_and_look_alone(self):
        ini, app = self.defaults()
        ini.update(upscaler='fsr3', output_res='3840x2160', effect_dof='0', effect_motion_blur='0')
        core.apply_graphics_preset('low', ini, app)
        self.assertEqual((ini['upscaler'], ini['output_res'], ini['effect_dof'], ini['effect_motion_blur']),
                         ('fsr3', '3840x2160', '0', '0'))
        self.assertEqual(app['fps_mode'], '60')

    def test_dlss5_ready_leaves_room_for_dlss5_and_keeps_it_as_set(self):
        ini, app = self.defaults()
        ini.update(upscaler='fsr3', output_res='3840x2160', ray_tracing='ultra', dlss5='off')
        app.update(extra_env='BB_FPS=120 BB_GPU_PROFILE=1', nr_upscaling='1')
        core.apply_graphics_preset('dlss5_ready', ini, app)
        # 4K output: DLSS 5 runs at the output resolution and missed 60 there (run 1, 4090).
        self.assertEqual((ini['upscaler'], ini['preset'], ini['output_res']), ('dlss', '1', '2560x1440'))
        self.assertEqual((ini['ray_tracing'], ini['frame_gen'], ini['frame_gen_multiplier']), ('high', 'dlss', '2'))
        self.assertEqual((app['fps_mode'], app['extra_env'], app['nr_upscaling']), ('60', 'BB_GPU_PROFILE=1', '0'))
        self.assertEqual(ini['dlss5'], 'off')
        self.assertEqual(core.graphics_preset_of(ini, app), 'dlss5_ready')
        ini['ray_tracing'] = 'ultra'
        self.assertEqual(core.graphics_preset_of(ini, app), 'custom')

    def test_dlss5_ready_keeps_outputs_up_to_1440p(self):
        for output in ('2560x1440', '1920x1080', '3440x1440'):
            with self.subTest(output=output):
                ini, app = self.defaults()
                ini['output_res'] = output
                core.apply_graphics_preset('dlss5_ready', ini, app)
                self.assertEqual((ini['output_res'], ini['preset'], ini['ray_tracing']), (output, '1', 'high'))
                self.assertEqual(core.graphics_preset_of(ini, app), 'dlss5_ready')
        for output in ('3840x2160', '5120x1440', '3200x1800'):
            with self.subTest(output=output):
                ini, app = self.defaults()
                ini['output_res'] = output
                self.assertTrue(core.dlss5_heavy_output(ini))
                self.assertEqual(core.graphics_preset_values('dlss5_ready', ini)['output_res'], '2560x1440')

    def test_presets_keep_reflex_boost(self):
        for name in ('remastered', 'dlss5_ready'):
            with self.subTest(name=name):
                ini, app = self.defaults()
                ini['reflex'] = 'boost'
                core.apply_graphics_preset(name, ini, app)
                self.assertEqual(ini['reflex'], 'boost')
                self.assertEqual(core.graphics_preset_of(ini, app), name)
                ini['reflex'] = 'off'
                self.assertEqual(core.graphics_preset_of(ini, app), 'custom')
                core.apply_graphics_preset(name, ini, app)
                self.assertEqual(ini['reflex'], 'on')

    def test_dlss5_at_4k_output_warns(self):
        ini, app = self.defaults()
        core.apply_graphics_preset('dlss5_ready', ini, app)
        ini.update(dlss5='on', output_res='2560x1440')
        self.assertEqual(core.dlss5_fps_warning(ini, app), '')
        ini.update(output_res='3840x2160', preset='3', ray_tracing='off')
        warning = core.dlss5_fps_warning(ini, app)
        self.assertIn('misses 60 FPS', warning)
        self.assertIn('2560 × 1440', warning)
        self.assertEqual(warning, core.dlss5_output_warning(ini, app))
        app['nr_upscaling'] = '1'
        self.assertIn('experimental', core.dlss5_output_warning(ini, app))
        ini['dlss5'] = 'off'
        self.assertEqual(core.dlss5_output_warning(ini, app), '')
        # Away from 60 the frame-rate reason comes first.
        ini['dlss5'] = 'on'
        app['fps_mode'] = '120'
        self.assertIn('fixed 60 FPS', core.dlss5_fps_warning(ini, app))

    def test_dlss5_ready_is_offered_only_where_dlss5_is(self):
        self.assertNotIn('dlss5_ready', core.graphics_presets(False))
        self.assertEqual(core.graphics_presets(False), ['low', 'balanced', 'high', 'ultra', 'remastered'])
        self.assertEqual(core.graphics_presets(True)[-1], 'dlss5_ready')

    def test_dlss5_request_warns_away_from_60(self):
        ini, app = self.defaults()
        ini['output_res'] = '2560x1440'
        app['fps_mode'] = '120'
        self.assertEqual(core.dlss5_fps_warning(ini, app), '')
        ini['dlss5'] = 'on'
        self.assertIn('fixed 60 FPS', core.dlss5_fps_warning(ini, app))
        self.assertIn('120 FPS', core.dlss5_fps_warning(ini, app))
        app['fps_mode'] = 'uncap'
        self.assertIn('uncapped', core.dlss5_fps_warning(ini, app))
        app.update(fps_mode='60', extra_env='BB_FPS=90')
        self.assertIn('90 FPS', core.dlss5_fps_warning(ini, app))
        app['extra_env'] = ''
        self.assertEqual(core.dlss5_fps_warning(ini, app), '')

    def test_new_installs_run_120_and_saved_settings_keep_their_frame_rate(self):
        self.assertEqual(core.app_settings({})['fps_mode'], '120')
        # Saved before 120 was the default, without a frame rate of their own: they ran unlocked.
        self.assertEqual(core.app_settings({'game_dir': 'x'})['fps_mode'], 'uncap')
        self.assertEqual(core.app_settings({'fps_mode': '60'})['fps_mode'], '60')
        modes = [v for v, _ in core.FPS_MODES]
        self.assertEqual(modes[0], '120')
        self.assertTrue({'120', '144', 'uncap', '90', '60', '30'} <= set(modes))
        self.assertIn('Amelia', dict(core.FPS_MODES)['uncap'][0])

    def test_window_options_reach_the_game(self):
        app = dict(core.APP_DEFAULTS)
        with patch.dict(os.environ, {}, clear=True):
            env = core.game_environment(app)
            self.assertEqual(env['BB_FULLSCREEN_MODE'], 'borderless')
            self.assertNotIn('BB_DISPLAY', env)
            self.assertEqual(env['BB_VOICE_LANGUAGE'], 'auto')
            app.update(fullscreen_mode='exclusive', display='2', voice_language='ptb')
            env = core.game_environment(app)
            self.assertEqual((env['BB_FULLSCREEN_MODE'], env['BB_DISPLAY'], env['BB_VOICE_LANGUAGE']),
                             ('exclusive', '2', 'ptb'))
        for key, options in (('fullscreen_mode', core.FULLSCREEN_MODES), ('display', core.DISPLAYS),
                             ('voice_language', core.VOICE_LANGUAGES)):
            self.assertIn(core.APP_DEFAULTS[key], [v for v, _ in options])

    def test_recommendation_from_gpu_status(self):
        cases = {
            'NVIDIA GeForce RTX 4060 Laptop GPU, discrete, 7956 MiB': 'high',
            'NVIDIA GeForce RTX 4090, discrete, 24564 MiB': 'remastered',
            'NVIDIA GeForce RTX 4080 SUPER, discrete, 16376 MiB': 'remastered',
            'NVIDIA GeForce RTX 3090, discrete, 24576 MiB': 'ultra',
            'AMD Radeon RX 7900 XTX, discrete, 24560 MiB': 'ultra',
            'NVIDIA GeForce GTX 1060 6GB, discrete, 6144 MiB': 'balanced',
            'AMD Radeon RX 560, discrete, 2048 MiB': 'low',
            'AMD Custom GPU 0405 (RADV VANGOGH), integrated or other, 1024 MiB': 'low',
            'Graphics card check unavailable': None,
            '': None,
        }
        for status, expected in cases.items():
            with self.subTest(status=status):
                self.assertEqual(core.recommended_graphics_preset(status), expected)

    def test_rtx_40_50_cards_get_a_dlss4_and_a_dlss5_suggestion(self):
        rtx4090 = 'NVIDIA GeForce RTX 4090, discrete, 24564 MiB'
        self.assertEqual(core.preset_tags(rtx4090, True), {'remastered': 'DLSS 4', 'dlss5_ready': 'DLSS 5'})
        # No DLSS 5 ready button where the card is not offered DLSS 5, so no mark for it.
        self.assertEqual(core.preset_tags(rtx4090, False), {'remastered': 'DLSS 4'})
        # Every other card keeps its one plain suggestion.
        self.assertEqual(core.preset_tags('NVIDIA GeForce RTX 3090, discrete, 24576 MiB', True), {'ultra': ''})
        self.assertEqual(core.preset_tags('', True), {})

    def test_my_settings_save_match_and_load(self):
        ini, app = self.defaults()
        self.assertIsNone(core.saved_my_settings(app))
        self.assertFalse(core.apply_my_settings(ini, app))
        core.apply_graphics_preset('remastered', ini, app)
        ini.update(output_res='2560x1440', dlss5='on')
        app['my_settings'] = core.my_settings_snapshot(ini, app)
        # Still a named preset: saved on Remastered, the launcher starts on Remastered.
        self.assertEqual(core.graphics_preset_of(ini, app), 'remastered')
        ini['model_lod'] = '0'  # off every preset: the saved set is Custom
        app['my_settings'] = core.my_settings_snapshot(ini, app)
        self.assertEqual(core.graphics_preset_of(ini, app), 'mine')
        # Another preset, then back: every saved value returns.
        core.apply_graphics_preset('low', ini, app)
        ini['output_res'] = '1920x1080'
        self.assertNotEqual(core.graphics_preset_of(ini, app), 'mine')
        self.assertTrue(core.apply_my_settings(ini, app))
        self.assertEqual((ini['output_res'], ini['dlss5'], ini['ray_tracing'], app['fps_mode'], ini['model_lod']),
                         ('2560x1440', 'on', 'ultra', '60', '0'))
        self.assertEqual(core.graphics_preset_of(ini, app), 'mine')
        # A key a later version dropped is skipped, not added.
        app['my_settings']['ini']['retired_key'] = '1'
        core.apply_my_settings(ini, app)
        self.assertNotIn('retired_key', ini)
        for key in core.MY_SETTINGS_INI:
            self.assertIn(key, core.INI_DEFAULTS)
        for key in core.MY_SETTINGS_APP:
            self.assertIn(key, core.APP_DEFAULTS)

    def test_first_start_settings_come_from_this_pc(self):
        # INI_DEFAULTS is one machine's (3840x2160, DLSS): a first start uses the player's own.
        values, preset = core.first_start_settings('NVIDIA GeForce RTX 4090, discrete, 24564 MiB', (3840, 2160))
        self.assertEqual((values, preset), ({'upscaler': 'dlss', 'output_res': '3840x2160'}, 'remastered'))
        values, preset = core.first_start_settings('AMD Radeon RX 7900 XTX, discrete, 24560 MiB', (2560, 1440))
        self.assertEqual((values, preset), ({'upscaler': 'fsr3', 'output_res': '2560x1440'}, 'ultra'))
        values, preset = core.first_start_settings('NVIDIA GeForce GTX 1060 6GB, discrete, 6144 MiB', (1920, 1080))
        self.assertEqual((values['upscaler'], preset), ('fsr3', 'balanced'))  # no DLSS before RTX
        # No GPU answer and no usable display: FSR 3.1 (every GPU), the output left as shipped.
        self.assertEqual(core.first_start_settings('Graphics card check unavailable', None), ({'upscaler': 'fsr3'}, None))
        self.assertNotIn('output_res', core.first_start_settings('', (10000, 5000))[0])

    def test_dlss5_where_reshade_will_not_load_warns(self):
        # The 4.2.3 package's folder was not in ReShadeApps.ini: DLSS 5 never loaded (run.py now
        # turns it off and says why; the launcher says it first).
        ini, app = self.defaults()
        ini.update(dlss5='on', output_res='2560x1440')
        app['extra_env'] = 'BB_FPS=60'
        every_file = {'runtime': True, 'renodx': True, 'bridge': True}
        with patch.object(core, 'neural_runtime_status', return_value=every_file):
            with patch.object(core, 'reshade_loads_here', return_value=False):
                self.assertIn("ReShade isn't set to load", core.dlss5_fps_warning(ini, app))
            with patch.object(core, 'reshade_loads_here', return_value=True):
                self.assertEqual(core.dlss5_fps_warning(ini, app), '')

    def test_video_memory_target_is_passed_to_the_game(self):
        app = dict(core.APP_DEFAULTS)
        with patch.dict(os.environ, {}, clear=True):
            self.assertNotIn('BB_GC_BUDGET_MB', core.game_environment(app))
            app['vram_budget_mb'] = '3072'
            self.assertEqual(core.game_environment(app)['BB_GC_BUDGET_MB'], '3072')
            app['vram_budget_mb'] = '999999'
            self.assertNotIn('BB_GC_BUDGET_MB', core.game_environment(app))


if __name__ == '__main__':
    unittest.main()
