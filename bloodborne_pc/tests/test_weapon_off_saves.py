"""With a weapon switch off, only real saves are converted, never the converters' own backups."""

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bbport_run_saves', ROOT / 'run.py')
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)
sys.path.insert(0, str(ROOT / 'scripts'))
from sojin import save_tool  # noqa: E402

WEAPON = b'\x40\x8b\x1e\x00'


class SavesHoldingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.user = Path(temp.name)
        self.saves = self.user / 'savedata' / '1' / 'CUSA00207'

    def save(self, name, data=WEAPON):
        folder = self.saves / name
        folder.mkdir(parents=True)
        (folder / 'userdata0000').write_bytes(b'before' + data + b'after')
        return folder

    def test_a_real_save_with_the_weapon_is_found(self):
        real = self.save('SPRJ0005')
        self.assertEqual(run.saves_holding(self.user, [WEAPON]), [real])

    def test_a_save_without_the_weapon_is_not_found(self):
        self.save('SPRJ0005', data=b'')
        self.assertEqual(run.saves_holding(self.user, [WEAPON]), [])

    def test_backups_are_left_alone_at_any_depth(self):
        real = self.save('SPRJ0005')
        self.save('SPRJ0005 sojin-chikage backup 20261106-204502')
        self.save('SPRJ0005 thunderwright backup 20261106-204502-2')
        self.save('SPRJ0005 sojin-chikage backup 20261106-204502 ng7-hammer backup 20261106-204504')
        self.assertEqual(run.saves_holding(self.user, [WEAPON]), [real])

    def test_only_backups_hold_the_weapon(self):
        self.save('SPRJ0005', data=b'')
        self.save('SPRJ0005 ng7-chikage backup 20261106-204502')
        self.assertEqual(run.saves_holding(self.user, [WEAPON]), [])

    def test_a_backup_the_converters_really_write_is_left_alone(self):
        real = self.save('SPRJ0005')
        path = str(real / 'userdata0000')
        data = {path: (real / 'userdata0000').read_bytes()}
        for tag in ('sojin-chikage', 'thunderwright', 'ng7-hammer', 'ng7-chikage'):
            with mock.patch.object(save_tool, 'BACKUP_TAG', tag):
                first = save_tool.backup(str(real), [path], data, beside=True)
                # In the same second: -2 after the time.
                second = save_tool.backup(str(real), [path], data, beside=True)
                inner = str(Path(first) / 'userdata0000')
                nested = save_tool.backup(first, [inner], {inner: data[path]}, beside=True)
            for folder in (first, second, nested):
                self.assertTrue(Path(folder).is_dir())
        self.assertEqual(run.saves_holding(self.user, [WEAPON]), [real])

    def test_a_folder_that_only_mentions_a_backup_is_a_save(self):
        real = self.save('SPRJ0005 backup of my run')
        self.assertEqual(run.saves_holding(self.user, [WEAPON]), [real])


if __name__ == '__main__':
    unittest.main()
