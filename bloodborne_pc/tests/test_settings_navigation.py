"""Checks that the task-based Settings hub can reach existing controls."""

from collections import Counter
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
from bbport_launcher_backend import FIELDS, LauncherBackend, SETTINGS_SECTIONS


class SettingsNavigationTests(unittest.TestCase):
    def test_every_existing_control_has_one_destination(self):
        existing = {field['key'] for fields in FIELDS.values() for field in fields}
        destinations = Counter(key for sections in SETTINGS_SECTIONS.values()
                               for _section, keys in sections for key in keys)
        self.assertEqual(set(destinations), existing)
        self.assertTrue(all(count == 1 for count in destinations.values()))

    def test_common_searches_open_the_relevant_section(self):
        backend = LauncherBackend.__new__(LauncherBackend)
        expected = {
            'DLSS': ('Visuals', 'Upscaling', 'upscaler'),
            'save folder': ('Game & Saves', 'Your data', 'user_dir'),
            'button prompts': ('Controls', 'Button prompts', ''),
            'Steam': ('System', 'Launch', ''),
        }
        for query, destination in expected.items():
            with self.subTest(query=query):
                first = backend.searchSettings(query)[0]
                self.assertEqual((first['category'], first['section'], first['key']), destination)


if __name__ == '__main__':
    unittest.main()
