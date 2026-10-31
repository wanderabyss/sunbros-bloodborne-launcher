"""bbport.ini dlss5_detail / dlss5_tone read by the launcher match one of their rows' options."""
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import bbport_launcher_win as core


class Dlss5LookNormalizationTests(unittest.TestCase):
    def test_hand_edited_values_become_the_nearest_option(self):
        options = {value for value, _ in core.DLSS5_DETAILS}
        self.assertEqual(options, {value for value, _ in core.DLSS5_TONES})
        for given, expected in (('0.5', '0.50'), ('0.50', '0.50'), ('.47', '0.50'), ('1', '1.00'),
                                ('0.04', '0.00'), ('0.05', '0.10'), ('0.949', '0.90'),
                                ('2', '1.00'), ('-0.3', '0.00'), ('nan', '0.00'), ('inf', '1.00')):
            values = {'dlss5_detail': given, 'dlss5_tone': given}
            core.normalize_dlss5_look(values)
            with self.subTest(given=given):
                self.assertEqual(values, {'dlss5_detail': expected, 'dlss5_tone': expected})
                self.assertIn(expected, options)
        values = {'dlss5_detail': 'half', 'dlss5_tone': ''}
        core.normalize_dlss5_look(values)
        self.assertEqual(values, {'dlss5_detail': core.INI_DEFAULTS['dlss5_detail'],
                                  'dlss5_tone': core.INI_DEFAULTS['dlss5_tone']})

    def test_load_ini_normalizes_them(self):
        with tempfile.TemporaryDirectory() as folder:
            ini = Path(folder) / 'bbport.ini'
            ini.write_text('dlss5_detail=0.7\ndlss5_tone=0.25\n', encoding='utf-8')
            with mock.patch.dict(os.environ, {'BB_CONFIG': str(ini)}):
                values, _ = core.load_ini()
        self.assertEqual((values['dlss5_detail'], values['dlss5_tone']), ('0.70', '0.30'))


if __name__ == '__main__':
    unittest.main()
