"""run.py keeps ReShade off unless DLSS 5 is on and the player's own files are in bin
(dlss5_environment): the community route."""
from paths import ROOT
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('run', ROOT / 'run.py')
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)


class Dlss5EnvironmentTests(unittest.TestCase):
    def test_reshade_layer_is_disabled(self):
        env = {}
        run.dlss5_environment(env)
        self.assertEqual(env, {'DISABLE_VK_LAYER_reshade_1': '1'})

    def test_inherited_bridge_variables_are_dropped(self):
        # An inherited BB_DLSS5_ROUTE_A=1 would make ConfigureDlss5 report the bridge as set up.
        env = {'BB_DLSS5_ROUTE_A': '1', 'BB_DLSS5_PROBLEM': 'old reason', 'BB_FPS': '60',
               'DISABLE_VK_LAYER_reshade_1': '0'}
        run.dlss5_environment(env)
        self.assertEqual(env, {'BB_FPS': '60', 'DISABLE_VK_LAYER_reshade_1': '1'})

    def test_setting_override_passes(self):
        # BB_DLSS5 is only the dlss5 setting's override: it cannot set up a backend.
        env = {'BB_DLSS5': 'on'}
        run.dlss5_environment(env)
        self.assertEqual(env['BB_DLSS5'], 'on')

    def test_scripted_bridge_test_keeps_the_layer(self):
        env = {'BB_DLSS5_BRIDGE_TEST': '1', 'BB_DLSS5_ROUTE_A': '1'}
        run.dlss5_environment(env)
        self.assertNotIn('DISABLE_VK_LAYER_reshade_1', env)
        self.assertNotIn('BB_DLSS5_ROUTE_A', env)

    def test_test_override_survives(self):
        env = {'BB_DLSS5_ANY_GPU': '1'}
        run.dlss5_environment(env)
        self.assertEqual(env['BB_DLSS5_ANY_GPU'], '1')


class Dlss5CommunityRouteTests(unittest.TestCase):
    def bin_with(self, folder, names):
        for name in names:
            (Path(folder) / name).write_bytes(b'placeholder')
        return folder

    def apps_listing(self, folder, *bins):
        apps = Path(folder) / 'ReShadeApps.ini'
        apps.write_text('Apps=' + ','.join(str(Path(b) / 'bb-probe.exe') for b in bins) + '\n', encoding='utf-8')
        return apps

    def test_on_with_every_file_keeps_the_layer_and_announces_the_route(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'bbport.ini'
            config.write_text('dlss5=on\n', encoding='utf-8')
            env = {'DISABLE_VK_LAYER_reshade_1': '1', 'BB_DLSS5_PROBLEM': 'old'}
            run.dlss5_environment(env, config, self.bin_with(folder, run.DLSS5_FILES),
                                  self.apps_listing(folder, folder))
        self.assertEqual(env, {'BB_DLSS5_ROUTE_A': '1'})

    def test_on_where_reshade_never_listed_this_folder_says_so(self):
        # The 4.2.3 package's folder was not in ReShadeApps.ini: the bridge never loaded, but the
        # game reported "DLSS 5: on (community bridge)".
        with tempfile.TemporaryDirectory() as folder:
            env = {'BB_DLSS5': 'on'}
            run.dlss5_environment(env, None, self.bin_with(folder, run.DLSS5_FILES),
                                  self.apps_listing(folder, Path(folder) / 'older-version'))
        self.assertEqual(env['DISABLE_VK_LAYER_reshade_1'], '1')
        self.assertIn('ReShade is not set to load', env['BB_DLSS5_PROBLEM'])
        self.assertNotIn('BB_DLSS5_ROUTE_A', env)

    def test_an_unreadable_reshade_list_does_not_block_the_route(self):
        with tempfile.TemporaryDirectory() as folder:
            env = {'BB_DLSS5': 'on'}
            run.dlss5_environment(env, None, self.bin_with(folder, run.DLSS5_FILES), Path(folder) / 'missing.ini')
        self.assertEqual(env, {'BB_DLSS5': 'on', 'BB_DLSS5_ROUTE_A': '1'})

    def test_on_with_a_file_missing_keeps_reshade_off_and_says_which(self):
        with tempfile.TemporaryDirectory() as folder:
            env = {'BB_DLSS5': 'on'}
            run.dlss5_environment(env, None, self.bin_with(folder, run.DLSS5_FILES[1:]))
        self.assertEqual(env['DISABLE_VK_LAYER_reshade_1'], '1')
        self.assertEqual(env['BB_DLSS5_PROBLEM'], 'missing in bin: nvngx_dlssnr.dll')
        self.assertNotIn('BB_DLSS5_ROUTE_A', env)

    def test_off_keeps_reshade_off_even_with_the_files(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'bbport.ini'
            config.write_text('dlss5=off\n', encoding='utf-8')
            env = {}
            run.dlss5_environment(env, config, self.bin_with(folder, run.DLSS5_FILES))
        self.assertEqual(env, {'DISABLE_VK_LAYER_reshade_1': '1'})

    def test_the_env_override_beats_the_file(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'bbport.ini'
            config.write_text('dlss5=on\n', encoding='utf-8')
            env = {'BB_DLSS5': 'off'}
            run.dlss5_environment(env, config, self.bin_with(folder, run.DLSS5_FILES))
        self.assertEqual(env['DISABLE_VK_LAYER_reshade_1'], '1')


if __name__ == '__main__':
    unittest.main()
