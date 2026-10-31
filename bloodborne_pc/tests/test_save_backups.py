"""Save backups (launcher/bbport_save_backups.py): backup, list, restore, prune and delete."""
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import bbport_save_backups as backups

SLOT = 'savedata/1/CUSA00207/SPRJ0005'


def write_saves(root, marker='one'):
    folder = Path(root) / SLOT
    folder.mkdir(parents=True, exist_ok=True)
    for index in range(3):
        (folder / f'userdata000{index}').write_bytes(f'{marker}-{index}'.encode() * (100 + index))
    (folder / 'backup0000').write_bytes(b'b' * 10)


def read_saves(root):
    folder = Path(root) / 'savedata'
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob('*') if p.is_file()}


class SaveBackupTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        write_saves(self.root)

    def test_backup_zips_savedata_with_a_manifest(self):
        info = backups.create_backup(self.root, 'Before Amygdala', summary='Hunter Lv 40',
                                     now=datetime(2026, 10, 28, 12, 30, 5))
        path = self.root / 'save-backups' / '20261028-123005 - Before Amygdala.zip'
        self.assertEqual(info['name'], path.name)
        self.assertTrue(path.is_file())
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            names = archive.namelist()
        self.assertEqual(manifest['kind'], 'manual')
        self.assertEqual(manifest['files'], 4)
        self.assertEqual(manifest['bytes'], backups.folder_stats(self.root / 'savedata')[1])
        self.assertEqual(manifest['summary'], 'Hunter Lv 40')
        self.assertIn(f'{SLOT}/userdata0000', names)
        self.assertEqual(info['date'], '2026-10-28 12:30')
        self.assertEqual(list((self.root / 'save-backups').glob('.*')), [])

    def test_label_is_cleaned_and_names_never_collide(self):
        now = datetime(2026, 1, 2, 3, 4, 5)
        first = backups.create_backup(self.root, 'a/b:c*?', now=now)
        second = backups.create_backup(self.root, 'a/b:c*?', now=now)
        self.assertEqual(first['name'], '20260102-030405 - abc.zip')
        self.assertEqual(second['name'], '20260102-030405 - abc (2).zip')

    def test_no_saves_is_an_error_and_leaves_nothing(self):
        empty = self.root / 'empty'
        empty.mkdir()
        with self.assertRaises(backups.BackupError):
            backups.create_backup(empty)
        self.assertFalse((empty / 'save-backups').exists() and any((empty / 'save-backups').iterdir()))

    def test_failed_write_leaves_no_partial_zip(self):
        with mock.patch.object(backups.zipfile.ZipFile, 'writestr', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                backups.create_backup(self.root)
        self.assertEqual(list((self.root / 'save-backups').iterdir()), [])

    def test_list_is_newest_first_and_marks_unreadable_zips(self):
        base = datetime(2026, 10, 1)
        backups.create_backup(self.root, 'old', now=base)
        backups.create_backup(self.root, 'new', kind='auto', now=base + timedelta(days=1))
        (self.root / 'save-backups' / 'junk.zip').write_bytes(b'not a zip')
        listed = backups.list_backups(self.root)
        valid = [info for info in listed if info['valid']]
        self.assertEqual([info['label'] for info in valid], ['new', 'old'])
        self.assertEqual(valid[0]['kind'], 'auto')
        self.assertEqual([info['name'] for info in listed if not info['valid']], ['junk.zip'])

    def test_prune_keeps_the_newest_automatic_backups_and_every_manual_one(self):
        base = datetime(2026, 10, 1)
        for day in range(13):
            backups.create_backup(self.root, kind='auto', now=base + timedelta(days=day))
        backups.create_backup(self.root, 'mine', now=base - timedelta(days=5))
        backups.create_backup(self.root, 'before restore', kind='safety', now=base - timedelta(days=4))
        removed = backups.prune_auto(self.root, keep=10)
        self.assertEqual(len(removed), 3)
        listed = backups.list_backups(self.root)
        autos = [info for info in listed if info['kind'] == 'auto']
        self.assertEqual(len(autos), 10)
        self.assertEqual(autos[-1]['created'], (base + timedelta(days=3)).isoformat())
        self.assertEqual({info['kind'] for info in listed}, {'auto', 'manual', 'safety'})

    def test_delete_only_accepts_backup_names(self):
        info = backups.create_backup(self.root)
        for bad in ('../savedata', '..\\x.zip', 'savedata', '', '.hidden.zip', 'missing.zip'):
            with self.subTest(name=bad), self.assertRaises(backups.BackupError):
                backups.delete_backup(self.root, bad)
        backups.delete_backup(self.root, info['name'])
        self.assertEqual(backups.list_backups(self.root), [])

    def test_restore_replaces_savedata_and_backs_up_the_current_saves_first(self):
        original = read_saves(self.root)
        info = backups.create_backup(self.root, 'good', now=datetime(2026, 10, 1))
        write_saves(self.root, 'changed')
        (self.root / SLOT / 'extra').write_bytes(b'new file')
        changed = read_saves(self.root)
        safety = backups.restore_backup(self.root, info['name'])
        self.assertEqual(read_saves(self.root), original)
        self.assertEqual(safety['kind'], 'safety')
        self.assertEqual(safety['label'], 'before restore')
        # The safety backup holds the saves from just before, and restores them.
        backups.restore_backup(self.root, safety['name'])
        self.assertEqual(read_saves(self.root), changed)
        leftovers = [p.name for p in self.root.iterdir() if p.name.startswith('savedata.')]
        self.assertEqual(leftovers, [])

    def test_restore_into_a_missing_savedata(self):
        info = backups.create_backup(self.root)
        original = read_saves(self.root)
        import shutil
        shutil.rmtree(self.root / 'savedata')
        self.assertIsNone(backups.restore_backup(self.root, info['name']))
        self.assertEqual(read_saves(self.root), original)

    def test_failed_check_after_swap_puts_the_previous_saves_back(self):
        info = backups.create_backup(self.root)
        write_saves(self.root, 'current')
        current = read_saves(self.root)

        def corrupt(live):
            (live / SLOT / 'userdata0000').write_bytes(b'x')
        with self.assertRaises(backups.BackupError):
            backups.restore_backup(self.root, info['name'], _after_swap=corrupt)
        self.assertEqual(read_saves(self.root), current)
        self.assertEqual([p.name for p in self.root.iterdir() if p.name.startswith('savedata.')], [])

    def test_rollback_uses_the_safety_backup_when_the_old_folder_cannot_return(self):
        info = backups.create_backup(self.root)
        write_saves(self.root, 'current')
        current = read_saves(self.root)
        real_replace = os.replace

        def fail_on_return(src, dst):
            if Path(src).name.startswith('savedata.previous-'):
                raise OSError('locked')
            return real_replace(src, dst)

        def corrupt(live):
            (live / SLOT / 'userdata0001').unlink()
        with mock.patch.object(backups.os, 'replace', side_effect=fail_on_return):
            with self.assertRaises(backups.BackupError):
                backups.restore_backup(self.root, info['name'], _after_swap=corrupt)
        self.assertEqual(read_saves(self.root), current)

    def test_a_damaged_backup_never_touches_the_live_saves(self):
        info = backups.create_backup(self.root)
        path = Path(info['path'])
        data = bytearray(path.read_bytes())
        data[60:80] = b'\0' * 20  # inside the first entry's compressed data
        path.write_bytes(bytes(data))
        before = read_saves(self.root)
        with self.assertRaises(backups.BackupError):
            backups.restore_backup(self.root, info['name'])
        self.assertEqual(read_saves(self.root), before)

    def test_restore_refuses_entries_outside_savedata(self):
        folder = self.root / 'save-backups'
        folder.mkdir()
        with zipfile.ZipFile(folder / 'evil.zip', 'w') as archive:
            archive.writestr('savedata/../../escape', b'x')
            archive.writestr('manifest.json', json.dumps({'files': 1, 'bytes': 1}))
        before = read_saves(self.root)
        with self.assertRaises(backups.BackupError):
            backups.restore_backup(self.root, 'evil.zip')
        self.assertFalse((self.root.parent / 'escape').exists())
        self.assertEqual(read_saves(self.root), before)

    def test_character_summary(self):
        chars = [{'name': 'A', 'level': 10}, {'name': 'B', 'level': 0}, {'name': 'C', 'level': 3},
                 {'name': 'D', 'level': 4}]
        self.assertEqual(backups.character_summary(chars), 'A Lv 10, B, C Lv 3 (+1)')
        self.assertEqual(backups.character_summary([]), '')


if __name__ == '__main__':
    unittest.main()
