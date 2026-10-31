"""bbport.ini hdr_white_nits / hdr_peak_nits / hdr_highlight_boost read by the launcher match one
of their rows' options, and the rows follow HDR output in the HDR section."""
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

    def test_hand_edited_values_become_an_option(self):
        cases = {
            'hdr_white_nits': (('250', '240'), ('display', '0'), ('-3', '0'), ('99999', '400'),
                               ('nan', '120'), ('bright', '120'), ('high', '120')),
            'hdr_peak_nits': (('700', '600'), ('display', '0'), ('1200', '1000'), ('5000', '4000')),
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
        self.assertEqual([values[k] for k in KEYS], ['200', '0', '0.67'])

    def test_rows_follow_hdr_output(self):
        keys = dict(backend.SETTINGS_SECTIONS['Visuals'])['HDR']
        start = keys.index('hdr')
        self.assertEqual(keys[start:start + 4], ['hdr', *KEYS])
        for key in KEYS:
            self.assertEqual(backend.SETTING_FIELDS[key]['kind'], 'choice')
            self.assertTrue(backend.SETTING_FIELDS[key]['hint'].startswith('HDR output only.'))


if __name__ == '__main__':
    unittest.main()
