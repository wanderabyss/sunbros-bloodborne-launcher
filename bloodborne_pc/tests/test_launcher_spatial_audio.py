"""The launcher's Spatial sound toggle: on by default, off reaches the game as BB_AUDIO_SPATIAL=0."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import bbport_launcher_win as core
import bbport_launcher_backend as backend


class SpatialAudioToggleTests(unittest.TestCase):
    def test_row_in_the_audio_section_on_by_default(self):
        self.assertIs(core.APP_DEFAULTS['spatial_audio'], True)
        self.assertEqual(backend.SETTING_FIELDS['spatial_audio']['kind'], 'toggle')
        keys = dict(backend.SETTINGS_SECTIONS['Game & Saves'])['Audio']
        self.assertEqual(keys, ['spatial_audio'])

    def test_only_off_reaches_the_game(self):
        on = core.game_environment({**core.APP_DEFAULTS, 'spatial_audio': True})
        self.assertNotIn('BB_AUDIO_SPATIAL', on)
        off = core.game_environment({**core.APP_DEFAULTS, 'spatial_audio': False})
        self.assertEqual(off['BB_AUDIO_SPATIAL'], '0')


if __name__ == '__main__':
    unittest.main()
