"""The launcher lists a save's characters, not the copies in the converters' backup folders."""

import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bbport_character_test', ROOT / 'launcher' / 'bbport_character.py')
character = importlib.util.module_from_spec(spec)
spec.loader.exec_module(character)
sys.path.insert(0, str(ROOT / 'scripts'))
from sojin import save_tool  # noqa: E402

STAMP = '20261106-204502'
# Every kind save_tool.is_backup_folder knows: another converter's, a second one in the same second,
# and a backup of a backup.
BACKUPS = (save_tool.backup_folder_name('SPRJ0005', STAMP),
           f'SPRJ0005 thunderwright backup {STAMP}',
           f'SPRJ0005 sojin-chikage backup {STAMP}-2',
           save_tool.backup_folder_name(save_tool.backup_folder_name('SPRJ0005', STAMP), STAMP))


def save_bytes(name, level):
    """A character slot from_save_file reads as valid: the offsets are the ones it parses."""
    data = bytearray(0x20000)
    base = 0x1000
    data[base + 1:base + 1 + 2 * len(name)] = name.encode('utf-16le')
    data[base - 23:base - 19] = level.to_bytes(4, 'little')
    data[base - 103] = 10  # vitality
    data[base + 469:base + 473] = b'\x40\xf0\xff\xff'  # the inventory marker
    return bytes(data)


class BackupFolderTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.user = Path(temp.name)
        self.title = self.user / 'savedata' / '1' / 'CUSA00207'

    def save(self, folder, slot, name, level):
        path = self.title / folder / f'userdata000{slot}'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(save_bytes(name, level))
        return path

    def real_save_with_backups(self):
        self.save('SPRJ0005', 0, 'Hunter', 40)
        self.save('SPRJ0005', 1, 'Second', 12)
        return [self.save(folder, 0, 'Old copy', 5) for folder in BACKUPS]

    def names(self, *args):
        return sorted(c['name'] for c in character.get_characters(*args))

    def test_only_the_real_saves_characters_are_listed(self):
        self.real_save_with_backups()
        self.assertEqual(self.names(self.user), ['Hunter', 'Second'])

    def test_a_backup_is_not_listed_from_any_folder_the_user_can_pick(self):
        self.real_save_with_backups()
        for folder in (self.user / 'savedata', self.title):
            with self.subTest(folder=folder):
                self.assertEqual(self.names(folder), ['Hunter', 'Second'])

    def test_a_backup_changed_last_does_not_become_the_profile(self):
        """refresh_profile_data shows the first character, and the newest file comes first."""
        for path in self.real_save_with_backups():
            path.touch()
        self.assertIn(character.get_characters(str(self.user))[0]['name'], ('Hunter', 'Second'))

    def test_a_save_with_backup_in_a_different_name_is_still_a_save(self):
        self.save('SPRJ0005 backup', 0, 'Kept', 7)
        self.assertEqual(self.names(self.user), ['Kept'])

    def test_listing_leaves_the_backups_in_place(self):
        backups = self.real_save_with_backups()
        before = [path.read_bytes() for path in backups]
        character.get_characters(str(self.user))
        self.assertEqual([path.read_bytes() for path in backups], before)

    def test_the_rule_is_the_converters_own(self):
        """Whatever the converter comes to treat as a backup, the launcher treats as one too."""
        self.save('SPRJ0005', 0, 'Hunter', 40)
        self.save('SPRJ0006', 0, 'Other', 9)
        fake = types.SimpleNamespace(is_backup_folder=lambda name: name == 'SPRJ0006')
        with mock.patch.object(character, '_converter_save_tool', return_value=fake):
            self.assertEqual(self.names(self.user), ['Hunter'])

    def test_it_works_where_sojin_is_the_packaged_launchers_bundled_package(self):
        """In the frozen launcher `sojin` is the bundled package, with weapon but no save_tool, and
        `from sojin.save_tool import ...` raises ModuleNotFoundError (seen in Bloodborne.exe 4.4.1).
        The callers swallow that, so a profile would just go empty."""
        self.real_save_with_backups()
        bundled = types.ModuleType('sojin')
        bundled.__path__ = []
        with mock.patch.dict(sys.modules, {'sojin': bundled}):
            sys.modules.pop('sojin.save_tool', None)
            self.assertEqual(self.names(self.user), ['Hunter', 'Second'])

    def test_the_converter_file_is_found_from_a_module_in_the_packaged_folder(self):
        """The bundled module's __file__ is _internal/bbport_character.py, and scripts/ is beside _internal."""
        with mock.patch.object(character, '__file__', str(ROOT / '_internal' / 'bbport_character.py')):
            self.assertTrue(character._converter_save_tool().is_backup_folder(BACKUPS[0]))


if __name__ == '__main__':
    unittest.main()
