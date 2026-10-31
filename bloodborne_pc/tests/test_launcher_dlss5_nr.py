"""DLSS 5 neural rendering through renodx-dlss5: the launcher's nr_* settings, the [RenoDX.DLSS5]
keys it writes to bin\\ReShade.ini, and the neural runtime status (presence of the player's own
nvngx_dlssnr.dll). Every file here is a placeholder in a temporary folder."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import bbport_launcher_win as core
import bbport_launcher_backend as backend


def make_bin(folder, runtime=True, renodx=True, bridge=True, reshade_ini=None):
    bin_dir = Path(folder)
    for present, name in ((runtime, core.NEURAL_RUNTIME), (renodx, core.RENODX_ADDON),
                          (bridge, core.DLSS5_BRIDGE_ADDON)):
        if present:
            (bin_dir / name).write_bytes(b'placeholder')
    if reshade_ini is not None:
        (bin_dir / 'ReShade.ini').write_text(reshade_ini, encoding='utf-8')
    return bin_dir


ON = {'dlss5': 'on'}


def nr_app(**values):
    return core.app_settings(values)


class NeuralRuntimeStatusTests(unittest.TestCase):
    def test_not_installed_says_where_and_that_we_never_download_it(self):
        with tempfile.TemporaryDirectory() as folder:
            bin_dir = make_bin(folder, runtime=False)
            self.assertFalse(core.neural_runtime_status(bin_dir)['runtime'])
            text = core.neural_runtime_text(bin_dir)
        self.assertIn('not installed', text)
        self.assertIn('nvngx_dlssnr.dll', text)
        self.assertIn('never downloads or redistributes', text)

    def test_installed_names_missing_addons(self):
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(core, 'reshade_loads_here', return_value=True):
            self.assertEqual(core.neural_runtime_text(make_bin(folder)),
                             'Neural runtime: installed. dlss5-bridge and renodx-dlss5 add-ons found.')
        with tempfile.TemporaryDirectory() as folder:
            text = core.neural_runtime_text(make_bin(folder, renodx=False))
        self.assertIn('installed', text)
        self.assertIn('Missing ReShade add-on: renodx-dlss5.addon64', text)


class NrSettingsTests(unittest.TestCase):
    def test_defaults_leave_everything_to_the_addon(self):
        app = core.app_settings({})
        for key in core.NR_SETTINGS:
            self.assertEqual(app[key], 'addon', key)
        self.assertEqual({k: v for k, v in core.renodx_nr_values(app).items() if v is not None},
                         {'NeuralUplift': '1'})

    def test_unknown_values_become_addon_default(self):
        app = core.app_settings({'nr_intensity': '7', 'nr_style': 'Vivid', 'nr_local_tone': '0.50'})
        self.assertEqual((app['nr_intensity'], app['nr_style'], app['nr_local_tone']), ('addon', 'addon', '0.50'))

    def test_every_nr_key_has_a_row_in_the_neural_rendering_section(self):
        sections = dict(backend.SETTINGS_SECTIONS['Visuals'])
        keys = sections['Neural rendering (DLSS 5)']
        self.assertEqual(keys[:2], ['dlss5', 'nr_upscaling'])
        self.assertFalse(backend.SETTING_FIELDS['nr_upscaling']['advanced'])
        self.assertEqual(set(keys), {'dlss5', *core.NR_SETTINGS})
        for key in core.NR_SETTINGS:
            field = backend.SETTING_FIELDS[key]
            self.assertEqual(field['kind'], 'choice')
            self.assertEqual(field['options'][0], {'value': 'addon', 'text': 'Add-on default'})
        self.assertTrue(all(backend.SETTING_FIELDS[k]['advanced'] for k in backend.NR_ADVANCED))
        self.assertFalse(backend.SETTING_FIELDS['nr_intensity']['advanced'])

    def test_renodx_keys_are_the_addons_own(self):
        # renodx-dlss5 v2.5's setting keys (strings in the add-on; ReShade.ini [RenoDX.DLSS5]).
        self.assertEqual({name for name, _options in core.NR_SETTINGS.values()} | {'NeuralUplift'},
                         {'NeuralUplift', 'NREnableUpscaling', 'NRPreset', 'NRStyle', 'NRIntensity',
                          'NRLocalStructure', 'NRLocalTone', 'NRSkinStructure', 'NRAutoMask',
                          'NRUICorrection'})


class ApplyRenodxTests(unittest.TestCase):
    INI = ('[ADDON]\nDisabledAddons=\n\n[RenoDX.DLSS5]\nNREnableUpscaling=1\nNRColorStrength=0.8\n\n'
           '[SCREENSHOT]\nClearAlpha=1\n')

    def test_writes_chosen_keys_and_keeps_the_rest(self):
        with tempfile.TemporaryDirectory() as folder:
            bin_dir = make_bin(folder, reshade_ini=self.INI)
            app = nr_app(nr_intensity='0.80', nr_skin_structure='-1.00', nr_upscaling='addon')
            self.assertTrue(core.apply_renodx_nr(app, ON, bin_dir))
            text = (bin_dir / 'ReShade.ini').read_text(encoding='utf-8')
        self.assertEqual(text, '[ADDON]\nDisabledAddons=\n\n[RenoDX.DLSS5]\nNRColorStrength=0.8\n'
                               'NeuralUplift=1\nNRIntensity=0.80\nNRSkinStructure=-1.00\n\n'
                               '[SCREENSHOT]\nClearAlpha=1\n')

    def test_adds_the_section_when_missing_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            bin_dir = make_bin(folder, reshade_ini='[GENERAL]\nNoDebugInfo=1\n')
            app = nr_app(nr_style='2', nr_auto_mask='0')
            core.apply_renodx_nr(app, ON, bin_dir)
            first = (bin_dir / 'ReShade.ini').read_text(encoding='utf-8')
            core.apply_renodx_nr(app, ON, bin_dir)
            second = (bin_dir / 'ReShade.ini').read_text(encoding='utf-8')
        self.assertEqual(first, '[GENERAL]\nNoDebugInfo=1\n\n[RenoDX.DLSS5]\nNeuralUplift=1\nNRStyle=2\nNRAutoMask=0\n')
        self.assertEqual(first, second)

    def test_leaves_reshade_ini_alone_unless_asked_and_set_up(self):
        for on, renodx, has_ini in ((False, True, True), (True, False, True), (True, True, False)):
            with self.subTest(on=on, renodx=renodx, has_ini=has_ini), \
                    tempfile.TemporaryDirectory() as folder:
                bin_dir = make_bin(folder, renodx=renodx, reshade_ini=self.INI if has_ini else None)
                app = core.app_settings({'nr_intensity': '0.50'})
                self.assertFalse(core.apply_renodx_nr(app, {'dlss5': 'on' if on else 'off'}, bin_dir))
                ini = bin_dir / 'ReShade.ini'
                self.assertEqual(ini.read_text(encoding='utf-8') if has_ini else None,
                                 self.INI if has_ini else None)


class ReshadeAppsTests(unittest.TestCase):
    def test_status_says_when_reshade_does_not_load_for_this_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            bin_dir = make_bin(folder)
            apps = Path(folder) / 'ReShadeApps.ini'
            apps.write_text('\ufeffApps=C:\\other\\bin\\bb-probe.exe\n', encoding='utf-8')
            self.assertFalse(core.reshade_loads_here(bin_dir, apps))
            apps.write_text(f'Apps=C:\\other\\bin\\bb-probe.exe,{bin_dir / "bb-probe.exe"}\n',
                            encoding='utf-8')
            self.assertTrue(core.reshade_loads_here(bin_dir, apps))
            self.assertTrue(core.reshade_loads_here(bin_dir, Path(folder) / 'missing.ini'))


class NeuralRenderingQmlTests(unittest.TestCase):
    def test_group_has_status_fold_and_reset(self):
        qml = (Path(backend.__file__).parent / 'qml' / 'SettingsWorkspace.qml').read_text(encoding='utf-8')
        for name in ('neuralRuntimeStatus', 'nrAdvancedToggle', 'nrReset', 'nrAdvancedOpen',
                     'launcher.resetNeuralRendering()'):
            self.assertIn(name, qml)
        self.assertIn('def resetNeuralRendering', Path(backend.__file__).read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
