"""bbport.ini present_upscale / present_rcas: the launcher's defaults match the game's
(gpu/shim/bbport_settings.h), hand-edited values match one of the rows' options, and the
launcher writes them back like its other keys."""
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import bbport_launcher_win as core


class PresentUpscaleSettingsTests(unittest.TestCase):
    def test_defaults_are_easu_and_no_extra_sharpening(self):
        self.assertEqual(core.INI_DEFAULTS['present_upscale'], 'easu')
        self.assertEqual(core.INI_DEFAULTS['present_rcas'], '0')
        self.assertEqual([value for value, _ in core.PRESENT_UPSCALES], ['easu', 'linear'])
        rcas = [value for value, _ in core.PRESENT_RCAS]
        self.assertEqual(rcas[0], '0')
        self.assertIn('(default)', core.PRESENT_RCAS[0][1][0])
        # Stops: each one halves RCAS's strength, so the list runs from off to strongest.
        stops = [float(value) for value in rcas[1:]]
        self.assertEqual(stops, sorted(stops, reverse=True))
        self.assertTrue(all(0 < stop <= 4 for stop in stops))

    def test_hand_edited_upscale_values(self):
        for given, expected in (('easu', 'easu'), ('linear', 'linear'), ('fsr1', 'easu'),
                                ('auto', 'easu'), ('bilinear', 'linear'), ('nearest', 'easu'),
                                ('', 'easu')):
            values = {'present_upscale': given, 'present_rcas': '0'}
            core.normalize_present_upscale(values)
            with self.subTest(given=given):
                self.assertEqual(values['present_upscale'], expected)

    def test_hand_edited_rcas_values_become_the_nearest_option(self):
        options = {value for value, _ in core.PRESENT_RCAS}
        for given, expected in (('0', '0'), ('0.0', '0'), ('off', '0'), ('-1', '0'), ('nan', '0'),
                                ('0.2', '0.25'), ('0.25', '0.25'), ('.5', '0.5'), ('0.7', '0.5'),
                                ('1', '1.0'), ('1.6', '2.0'), ('2', '2.0'), ('4', '2.0'),
                                ('9', '2.0'), ('inf', '2.0'), ('sharp', '0'), ('', '0')):
            values = {'present_upscale': 'easu', 'present_rcas': given}
            core.normalize_present_upscale(values)
            with self.subTest(given=given):
                self.assertEqual(values['present_rcas'], expected)
                self.assertIn(expected, options)

    def test_load_and_save_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            ini = Path(folder) / 'bbport.ini'
            with mock.patch.dict(os.environ, {'BB_CONFIG': str(ini)}):
                values, lines = core.load_ini()  # no file: the defaults
                self.assertEqual((values['present_upscale'], values['present_rcas']), ('easu', '0'))
                ini.write_text('pc_menu=1\npresent_upscale=bilinear\npresent_rcas=0.3\n',
                               encoding='utf-8')
                values, lines = core.load_ini()
                self.assertEqual((values['present_upscale'], values['present_rcas']),
                                 ('linear', '0.25'))
                values['present_rcas'] = '1.0'
                core.save_ini(values, lines)
                text = ini.read_text(encoding='utf-8').splitlines()
        self.assertIn('pc_menu=1', text)
        self.assertEqual(text.count('present_upscale=linear'), 1)
        self.assertEqual(text.count('present_rcas=1.0'), 1)
        self.assertEqual(sum(line.startswith('present_') for line in text), 2)


if __name__ == '__main__':
    unittest.main()
