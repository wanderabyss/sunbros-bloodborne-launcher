from paths import ROOT  # noqa: F401  (puts scripts/ on the path)
import os
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

import game_check


def dcx(payload, packed=None):
    """A DFLT .dcx file as the game's (sizes big-endian, zlib data at 0x4C)."""
    packed = zlib.compress(payload) if packed is None else packed
    header = bytearray(0x4C)
    header[0:4], header[0x18:0x1C], header[0x24:0x28], header[0x28:0x2C] = (
        b'DCX\0', b'DCS\0', b'DCP\0', b'DFLT')
    struct.pack_into('>II', header, 0x1C, len(payload), len(packed))
    header[0x44:0x48] = b'DCA\0'
    return bytes(header) + packed


class GameCheckTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.game = Path(directory.name)
        self.folder = self.game / game_check.CHECKED_FOLDER
        self.folder.mkdir(parents=True)

    def test_intact_shaders_pass(self):
        (self.folder / 'gxshader.shaderbnd.dcx').write_bytes(dcx(bytes(range(256)) * 64))
        self.assertEqual(game_check.broken_files(self.game), [])

    def test_damaged_shaders(self):
        # As LibOrbisPkg on .NET 6+: part of the data replaced by stale bytes.
        packed = bytearray(zlib.compress(os.urandom(4096)))
        packed[len(packed) // 2:] = packed[:len(packed) - len(packed) // 2]
        (self.folder / 'gxshader.shaderbnd.dcx').write_bytes(dcx(os.urandom(4096), bytes(packed)))
        broken = game_check.broken_files(self.game)
        self.assertEqual(broken, [f'{game_check.CHECKED_FOLDER}/gxshader.shaderbnd.dcx'])
        self.assertIn('gxshader.shaderbnd.dcx', game_check.explain(broken))

    def test_wrong_size_is_damaged(self):
        data = bytearray(dcx(b'x' * 100))
        struct.pack_into('>I', data, 0x1C, 101)
        self.assertTrue(game_check.dcx_broken(self._write(data)))

    def test_other_compressions_are_not_checked(self):
        data = bytearray(dcx(b'x' * 100))
        data[0x28:0x2C] = b'KRAK'
        self.assertFalse(game_check.dcx_broken(self._write(data[:0x50])))

    def test_script_lists_every_damaged_file(self):
        (self.folder / 'good.dcx').write_bytes(dcx(b'good' * 100))
        (self.folder / 'bad.dcx').write_bytes(dcx(b'bad' * 100, b'not zlib data'))
        self.assertEqual(game_check.main(['game_check.py', str(self.game)]), 1)

    def test_unreadable_file_does_not_stop_the_game(self):
        from unittest import mock
        (self.folder / 'locked.dcx').write_bytes(dcx(b'x' * 100))
        with mock.patch.object(Path, 'read_bytes', side_effect=PermissionError('locked')):
            self.assertEqual(game_check.broken_files(self.game), [])

    def _write(self, data):
        path = self.folder / 'file.dcx'
        path.write_bytes(bytes(data))
        return path


class MissingFilesTests(unittest.TestCase):
    def test_emptied_dump_is_reported_and_complete_one_passes(self):
        # A delete through an overlay's junctions left the folders and eboot.bin, nothing else.
        with tempfile.TemporaryDirectory() as directory:
            game = Path(directory)
            for folder in ('sce_module', 'sce_sys', 'dvdroot_ps4/chr', 'dvdroot_ps4/map/m21'):
                (game / folder).mkdir(parents=True)
            (game / 'eboot.bin').write_bytes(b'game')
            missing = game_check.missing_files(game)
            self.assertEqual(missing[:4], ['sce_module/libc.prx', 'sce_module/libSceFios2.prx',
                                           'sce_sys/param.sfo', 'dvdroot_ps4/chr (empty)'])
            self.assertIn('dvdroot_ps4/sound', missing)
            text = game_check.explain_missing(game, missing)
            self.assertIn('sce_module/libc.prx', text)
            self.assertIn(f'{len(missing) - 3} more', text)
            for name in (*game_check.REQUIRED_FILES,
                         *(f'{folder}/x/file.dcx' for folder in game_check.REQUIRED_CONTENT)):
                (game / name).parent.mkdir(parents=True, exist_ok=True)
                (game / name).write_bytes(b'data')
            self.assertEqual(game_check.missing_files(game), [])


if __name__ == '__main__':
    unittest.main()
