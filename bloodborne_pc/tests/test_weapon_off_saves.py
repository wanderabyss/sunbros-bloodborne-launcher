"""With a weapon switch off, only real saves are converted, never the converters' own backups."""

import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bbport_run_saves', ROOT / 'run.py')
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)

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


if __name__ == '__main__':
    unittest.main()
