"""DLSS 5 neural rendering through renodx-dlss5: the launcher's nr_* settings, the [RenoDX.DLSS5]
keys it writes to bin\\ReShade.ini, and the neural runtime status (presence of the player's own
nvngx_dlssnr.dll). Every file here is a placeholder in a temporary folder."""
from pathlib import Path
import json
import os
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


class PaperWhiteScaleTests(unittest.TestCase):
    TUNED = '[RenoDX.DLSS5]\nNeuralUplift=1\nNRPaperWhiteScale=1.35\n\n[SCREENSHOT]\nClearAlpha=1\n'
    KIT = '[ADDON]\nDisabledAddons=\n\n[RenoDX.DLSS5]\nNRColorStrength=0.8\n\n[SCREENSHOT]\nClearAlpha=1\n'

    def test_capture_records_it_and_keeps_the_line(self):
        with tempfile.TemporaryDirectory() as folder:
            bin_dir = make_bin(folder, reshade_ini=self.TUNED)
            app = nr_app()
            self.assertTrue(core.apply_renodx_nr(app, ON, bin_dir))
            text = (bin_dir / 'ReShade.ini').read_text(encoding='utf-8')
        self.assertEqual(app['renodx_paper_white_scale'], '1.35')
        self.assertIn('NRPaperWhiteScale=1.35\n', text)

    def test_the_file_wins_over_the_recorded_value(self):
        with tempfile.TemporaryDirectory() as folder:
            bin_dir = make_bin(folder, reshade_ini=self.TUNED)
            app = nr_app(renodx_paper_white_scale='0.90')
            core.apply_renodx_nr(app, ON, bin_dir)
            text = (bin_dir / 'ReShade.ini').read_text(encoding='utf-8')
        self.assertEqual(app['renodx_paper_white_scale'], '1.35')
        self.assertNotIn('0.90', text)

    def test_only_the_addons_section_counts(self):
        with tempfile.TemporaryDirectory() as folder:
            bin_dir = make_bin(folder, reshade_ini='[OTHER]\nNRPaperWhiteScale=9\n\n' + self.KIT)
            app = nr_app()
            core.apply_renodx_nr(app, ON, bin_dir)
        self.assertEqual(app['renodx_paper_white_scale'], '')

    def test_restored_into_a_kit_fresh_file_then_left_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as folder:
            bin_dir = make_bin(folder, reshade_ini=self.KIT)
            app = nr_app(renodx_paper_white_scale='1.35')
            core.apply_renodx_nr(app, ON, bin_dir)
            ini = bin_dir / 'ReShade.ini'
            first = ini.read_bytes()
            self.assertTrue(core.apply_renodx_nr(app, ON, bin_dir))
            second = ini.read_bytes()
            text = ini.read_text(encoding='utf-8')
        self.assertEqual(first, second)
        self.assertEqual(text, '[ADDON]\nDisabledAddons=\n\n[RenoDX.DLSS5]\nNRColorStrength=0.8\n'
                               'NeuralUplift=1\nNRPaperWhiteScale=1.35\n\n[SCREENSHOT]\nClearAlpha=1\n')
        self.assertEqual(app['renodx_paper_white_scale'], '1.35')

    def test_restored_when_the_kit_file_has_no_section(self):
        with tempfile.TemporaryDirectory() as folder:
            bin_dir = make_bin(folder, reshade_ini='[GENERAL]\nNoDebugInfo=1\n')
            core.apply_renodx_nr(nr_app(renodx_paper_white_scale='1.35'), ON, bin_dir)
            text = (bin_dir / 'ReShade.ini').read_text(encoding='utf-8')
        self.assertEqual(text, '[GENERAL]\nNoDebugInfo=1\n\n[RenoDX.DLSS5]\nNeuralUplift=1\nNRPaperWhiteScale=1.35\n')

    def test_nothing_recorded_adds_no_key(self):
        with tempfile.TemporaryDirectory() as folder:
            bin_dir = make_bin(folder, reshade_ini=self.KIT)
            core.apply_renodx_nr(nr_app(), ON, bin_dir)
            self.assertNotIn('NRPaperWhiteScale', (bin_dir / 'ReShade.ini').read_text(encoding='utf-8'))

    def test_not_an_offered_setting_so_it_is_never_removed(self):
        self.assertNotIn(core.RENODX_PAPER_WHITE, {name for name, _options in core.NR_SETTINGS.values()})
        self.assertNotIn(core.RENODX_PAPER_WHITE, core.renodx_nr_values(nr_app()))

    def test_backend_saves_a_new_scale_and_a_fresh_folder_gets_it_back(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old, new = root / 'old', root / 'new'
            old.mkdir()
            new.mkdir()
            make_bin(old, reshade_ini=self.TUNED)
            make_bin(new, reshade_ini=self.KIT)
            settings = root / 'settings.json'
            with mock.patch.object(core, 'CONFIG_DIR', root), mock.patch.object(core, 'CONFIG_FILE', settings), \
                    mock.patch.object(core, 'DATA_DIR', root), \
                    mock.patch.dict(os.environ, {'BB_CONFIG': str(root / 'bbport.ini')}), \
                    mock.patch.dict(core.APP_DEFAULTS, {'check_updates': False, 'game_dir': str(root / 'missing')}), \
                    mock.patch.object(core, 'load_all_saved_settings', return_value={}):
                launcher = backend.LauncherBackend(route={'mode': 'direct'})
                launcher.setValue('dlss5', 'on')
                launcher._apply_neural_settings(old)
                self.assertEqual(json.loads(settings.read_text(encoding='utf-8'))['renodx_paper_white_scale'], '1.35')
                launcher._apply_neural_settings(new)
            self.assertIn('NRPaperWhiteScale=1.35', (new / 'ReShade.ini').read_text(encoding='utf-8'))


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

    LIMITED_LOG = ("20:20:47:938 [ 9836] | WARN  | Skipped loading add-on from 'C:\\x\\bin\\dlss5-bridge.addon64' "
                   "because this build of ReShade has only limited add-on functionality.\n")

    def test_status_and_start_warning_name_reshades_standard_build(self):
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(core, 'reshade_loads_here', return_value=True), \
                mock.patch.object(core, 'PORT_DIR', Path(folder)):
            (Path(folder) / 'bin').mkdir()
            bin_dir = make_bin(Path(folder) / 'bin')
            self.assertFalse(core.reshade_addons_skipped(bin_dir))  # no log yet
            (bin_dir / 'ReShade.log').write_text(self.LIMITED_LOG, encoding='utf-8')
            self.assertTrue(core.reshade_addons_skipped(bin_dir))
            self.assertIn('full add-on support', core.neural_runtime_text(bin_dir))
            warning = core.dlss5_fps_warning(ON, nr_app())
            self.assertIn("DLSS 5 won't take effect", warning)
            self.assertIn('full add-on support', warning)
            (bin_dir / 'ReShade.log').write_text('INFO | Loaded add-on "DLSS 5 Bridge"\n', encoding='utf-8')
            self.assertFalse(core.reshade_addons_skipped(bin_dir))
            self.assertEqual(core.neural_runtime_text(bin_dir),
                             'Neural runtime: installed. dlss5-bridge and renodx-dlss5 add-ons found.')


class NeuralRenderingQmlTests(unittest.TestCase):
    def test_group_has_status_fold_and_reset(self):
        qml = (Path(backend.__file__).parent / 'qml' / 'SettingsWorkspace.qml').read_text(encoding='utf-8')
        for name in ('neuralRuntimeStatus', 'nrAdvancedToggle', 'nrReset', 'nrAdvancedOpen',
                     'launcher.resetNeuralRendering()'):
            self.assertIn(name, qml)
        self.assertIn('def resetNeuralRendering', Path(backend.__file__).read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
