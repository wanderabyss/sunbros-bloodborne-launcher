"""bbport.ini hdr_white_nits / hdr_peak_nits read by the launcher keep a tuned value, clamped as the
game clamps it; hdr_highlight_boost matches one of its row's options; the rows follow HDR output in
the HDR section; bbport.ini's HDR keys win over the saved JSON at launcher start."""
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import bbport_launcher_win as core
import bbport_launcher_backend as backend

KEYS = ('hdr_white_nits', 'hdr_peak_nits', 'hdr_highlight_boost')


class HdrLevelsTests(unittest.TestCase):
    def test_defaults_are_the_old_fixed_levels(self):
        # gpu/shim/bbport_settings.h HdrWhiteDefault / HdrPeakDefault / HdrBoostDefault.
        self.assertEqual([core.INI_DEFAULTS[k] for k in KEYS], ['120', '1000', '1.00'])
        for key, options in zip(KEYS, (core.HDR_WHITES, core.HDR_PEAKS, core.HDR_BOOSTS)):
            self.assertIn(core.INI_DEFAULTS[key], {value for value, _ in options})

    def test_levels_are_clamped_and_boost_snaps_to_an_option(self):
        cases = {
            'hdr_white_nits': (('250', '250'), ('137', '137'), ('137.0', '137'), ('display', '0'), ('-3', '0'),
                               ('99999', '800'), ('50', '80'), ('550', '550'), ('inf', '800'),
                               ('nan', '120'), ('bright', '120'), ('high', '120')),
            'hdr_peak_nits': (('700', '700'), ('display', '0'), ('1200', '1200'), ('5000', '4000'),
                              ('100', '400')),
            'hdr_highlight_boost': (('high', '1.00'), ('Low', '0.33'), ('0.5', '0.33'), ('0.6', '0.67'),
                                    ('2', '1.00'), ('display', '1.00'), ('-1', '0.00')),
        }
        for key, pairs in cases.items():
            for given, expected in pairs:
                values = {k: core.INI_DEFAULTS[k] for k in KEYS}
                values[key] = given
                core.normalize_hdr_levels(values)
                with self.subTest(key=key, given=given):
                    self.assertEqual(values[key], expected)

    def test_load_ini_normalizes_them(self):
        with tempfile.TemporaryDirectory() as folder:
            ini = Path(folder) / 'bbport.ini'
            ini.write_text('hdr_white_nits=210\nhdr_peak_nits=display\nhdr_highlight_boost=medium\n',
                           encoding='utf-8')
            with mock.patch.dict(os.environ, {'BB_CONFIG': str(ini)}):
                values, _ = core.load_ini()
        self.assertEqual([values[k] for k in KEYS], ['210', '0', '0.67'])

    def test_a_tuned_level_survives_load_and_save(self):
        with tempfile.TemporaryDirectory() as folder:
            ini = Path(folder) / 'bbport.ini'
            ini.write_text('hdr_white_nits=137\nhdr_peak_nits=1234\n', encoding='utf-8')
            with mock.patch.dict(os.environ, {'BB_CONFIG': str(ini)}):
                values, lines = core.load_ini()
                core.save_ini({k: values[k] for k in core.INI_DEFAULTS}, lines)
                saved = ini.read_text(encoding='utf-8').splitlines()
                again, _ = core.load_ini()
        self.assertIn('hdr_white_nits=137', saved)
        self.assertIn('hdr_peak_nits=1234', saved)
        self.assertEqual((again['hdr_white_nits'], again['hdr_peak_nits']), ('137', '1234'))

    def test_native_hdr_is_an_ini_toggle_off_by_default(self):
        self.assertEqual(backend.SETTING_FIELDS['hdr_native']['kind'], 'toggle')
        self.assertTrue(backend.SETTING_FIELDS['hdr_native']['hint'].startswith('HDR output only.'))
        self.assertIn('hdr_native', core.INI_FLAGS)
        self.assertIn('hdr_native', core.MY_SETTINGS_INI)
        self.assertIn('hdr_native_color', core.MY_SETTINGS_INI)
        self.assertEqual(core.INI_DEFAULTS['hdr_native_color'], '0.25')
        self.assertEqual(backend.SETTING_FIELDS['hdr_native_color']['kind'], 'choice')
        with tempfile.TemporaryDirectory() as folder:
            ini = Path(folder) / 'bbport.ini'
            ini.write_text('hdr=1\n', encoding='utf-8')
            with mock.patch.dict(os.environ, {'BB_CONFIG': str(ini)}):
                self.assertEqual(core.load_ini()[0]['hdr_native'], '0')
            ini.write_text('hdr=1\nhdr_native=1\n', encoding='utf-8')
            with mock.patch.dict(os.environ, {'BB_CONFIG': str(ini)}):
                self.assertEqual(core.load_ini()[0]['hdr_native'], '1')

    def test_rows_follow_hdr_output(self):
        keys = dict(backend.SETTINGS_SECTIONS['Visuals'])['HDR']
        start = keys.index('hdr')
        self.assertEqual(keys[start:start + 6], ['hdr', 'hdr_native', 'hdr_native_color', *KEYS])
        for key in KEYS:
            self.assertEqual(backend.SETTING_FIELDS[key]['kind'], 'choice')
            self.assertTrue(backend.SETTING_FIELDS[key]['hint'].startswith('HDR output only.'))


class TunedHdrInLauncherTests(unittest.TestCase):
    """The overlay writes bbport.ini after the launcher's last write."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.ini = self.root / 'bbport.ini'
        for active in (mock.patch.object(core, 'CONFIG_DIR', self.root),
                       mock.patch.object(core, 'CONFIG_FILE', self.root / 'settings.json'),
                       mock.patch.object(core, 'DATA_DIR', self.root),
                       mock.patch.dict(os.environ, {'BB_CONFIG': str(self.ini)}),
                       mock.patch.dict(core.APP_DEFAULTS, {'check_updates': False,
                                                           'game_dir': str(self.root / 'missing')})):
            active.start()
            self.addCleanup(active.stop)

    def start(self, **ini_settings):
        saved = {'ini_settings': ini_settings} if ini_settings else {}
        with mock.patch.object(core, 'load_all_saved_settings', return_value=saved):
            return backend.LauncherBackend(route={'mode': 'direct'})

    def option(self, launcher, key):
        options = launcher.live_field(backend.SETTING_FIELDS[key])['options']
        return next((o for o in options if o['value'] == launcher.value(key)), None), options

    def test_a_tuned_value_gets_its_own_option(self):
        self.ini.write_text('hdr_white_nits=137\nhdr_peak_nits=1234\nhdr_native_color=0.40\n', encoding='utf-8')
        launcher = self.start()
        offered = len(backend.SETTING_FIELDS['hdr_white_nits']['options'])
        for key, text in (('hdr_white_nits', '137 nits (custom)'), ('hdr_peak_nits', '1234 nits (custom)'),
                          ('hdr_native_color', '0.40 (custom)')):
            with self.subTest(key=key):
                option, options = self.option(launcher, key)
                self.assertEqual(option['text'], text)
                self.assertIs(options[-1], option)
        self.assertEqual(len(backend.SETTING_FIELDS['hdr_white_nits']['options']), offered)  # the table is untouched

    def test_an_offered_value_adds_no_option(self):
        self.ini.write_text('hdr_white_nits=120\nhdr_native_color=0.25\n', encoding='utf-8')
        launcher = self.start()
        for key in ('hdr_white_nits', 'hdr_native_color'):
            self.assertEqual(self.option(launcher, key)[1], backend.SETTING_FIELDS[key]['options'])

    def test_bbport_ini_wins_over_the_json_for_its_hdr_keys(self):
        self.ini.write_text('hdr_white_nits=137\nhdr_peak_nits=1234\nhdr_native=1\nhdr_native_color=0.40\n'
                            'hdr_native_start=2.50\n', encoding='utf-8')
        launcher = self.start(hdr_white_nits='120', hdr_peak_nits='1000', hdr_native='0',
                              hdr_native_color='0.25', hdr_highlight_boost='0.33', sharpness='0.10')
        self.assertEqual([launcher.ini[k] for k in sorted(core.HDR_INI_WINS)], ['1', '0.40', '1234', '137'])
        lines = self.ini.read_text(encoding='utf-8').splitlines()
        self.assertIn('hdr_white_nits=137', lines)
        self.assertIn('hdr_native_start=2.50', lines)  # not a launcher key: left as the overlay wrote it
        # Every other key still comes from the JSON.
        self.assertEqual((launcher.ini['hdr_highlight_boost'], launcher.ini['sharpness']), ('0.33', '0.10'))

    def test_the_json_fills_hdr_keys_bbport_ini_lacks(self):
        launcher = self.start(hdr_white_nits='137', hdr_native='1')  # a new folder has no bbport.ini
        self.assertEqual((launcher.ini['hdr_white_nits'], launcher.ini['hdr_native']), ('137', '1'))


if __name__ == '__main__':
    unittest.main()
