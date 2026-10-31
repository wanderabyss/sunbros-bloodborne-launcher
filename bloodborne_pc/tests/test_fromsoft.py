from paths import ROOT
import importlib.util
import os
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location('fromsoft', ROOT / 'scripts/fromsoft.py')
fromsoft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fromsoft)

# BB_TEST_GAME_DIR=<CUSA03173>: also check the real 1.09 containers.
GAME = Path(os.environ['BB_TEST_GAME_DIR']) / 'dvdroot_ps4' if os.environ.get('BB_TEST_GAME_DIR') else None


def bnd4(files, align=0x10):
    """A unicode BND4 with 0x24-byte file headers, as Bloodborne's talk archives are."""
    count = len(files)
    names_at = 0x40 + 0x24 * count
    names = b''
    name_offsets = []
    for name, _ in files:
        name_offsets.append(names_at + len(names))
        names += name.encode('utf-16-le') + b'\0\0'
    start = names_at + len(names)
    start += -start % align
    header = bytearray(b'BND4' + b'\0' * 8 + struct.pack('<i', count) + struct.pack('<q', 0x40) +
                       b'00000000' + struct.pack('<qq', 0x24, start) + bytes([1, 0x74, 0, 0]) + b'\0' * 12)
    headers, body = b'', b''
    for (name, data), name_at in zip(files, name_offsets):
        headers += struct.pack('<4xiqqIiI', -1, len(data), len(data), start + len(body), 0, name_at)
        body += data + b'\0' * (-len(data) % align)
    return bytes(header) + headers + names + b'\0' * (start - names_at - len(names)) + body


class DcxTests(unittest.TestCase):
    def test_round_trip_and_template_header(self):
        data = bytes(range(256)) * 50
        packed = fromsoft.dcx_compress(data)
        self.assertEqual(packed[:4], b'DCX\0')
        self.assertEqual(packed[0x44:0x48], b'DCA\0')
        self.assertEqual(fromsoft.dcx_decompress(packed), data)
        again = fromsoft.dcx_compress(b'other', template=packed)
        self.assertEqual(again[:0x1c], packed[:0x1c])
        self.assertEqual(fromsoft.dcx_decompress(again), b'other')

    def test_rejects_other_formats(self):
        with self.assertRaises(fromsoft.FormatError):
            fromsoft.dcx_decompress(b'BND4' + b'\0' * 100)

    def test_damaged_files_are_format_errors(self):
        # Issue #8: a cut-short menu.msgbnd.dcx stopped the game with zlib.error.
        packed = fromsoft.dcx_compress(bytes(range(256)) * 50)
        with self.assertRaisesRegex(fromsoft.FormatError, 'truncated'):
            fromsoft.dcx_decompress(packed[:-10])
        # The header's packed size too small: zlib sees a stream that stops early.
        short = bytearray(packed)
        short[0x20:0x24] = (len(packed) - 0x4c - 10).to_bytes(4, 'big')
        with self.assertRaisesRegex(fromsoft.FormatError, 'damaged'):
            fromsoft.dcx_decompress(bytes(short))
        garbled = packed[:0x4c] + b'\xff' * (len(packed) - 0x4c)
        with self.assertRaisesRegex(fromsoft.FormatError, 'damaged'):
            fromsoft.dcx_decompress(garbled)
        with self.assertRaises(fromsoft.FormatError):
            fromsoft.dcx_decompress(packed[:0x30])

    @unittest.skipUnless(GAME, 'BB_TEST_GAME_DIR not set')
    def test_real_header_matches_a_fresh_one(self):
        real = (GAME / 'map/MapStudio/m21_00_00_00.msb.dcx').read_bytes()
        content = fromsoft.dcx_decompress(real)
        fresh = fromsoft.dcx_compress(content)
        # Everything but the compressed size, which depends on the compressor.
        self.assertEqual(fresh[:0x20] + fresh[0x24:0x4c], real[:0x20] + real[0x24:0x4c])
        self.assertEqual(fromsoft.dcx_decompress(fresh), content)


class Bnd4Tests(unittest.TestCase):
    def test_unchanged_archive_is_identical(self):
        data = bnd4([('N:\\script\\t1.esd', b'one'), ('N:\\script\\t2.esd', b'second file')])
        archive = fromsoft.Bnd4(data)
        self.assertEqual(archive.names, ['N:\\script\\t1.esd', 'N:\\script\\t2.esd'])
        self.assertEqual(archive.files, [b'one', b'second file'])
        self.assertEqual(archive.to_bytes(), data)

    def test_replacing_a_file_moves_the_rest(self):
        archive = fromsoft.Bnd4(bnd4([('a\\t1.esd', b'one'), ('a\\t2.esd', b'two')]))
        archive.files[archive.index('t1.esd')] = b'a much longer first file'
        again = fromsoft.Bnd4(archive.to_bytes())
        self.assertEqual(again.files, [b'a much longer first file', b'two'])
        self.assertEqual(again.names, archive.names)

    def test_ambiguous_name_is_refused(self):
        archive = fromsoft.Bnd4(bnd4([('a\\t1.esd', b'1'), ('b\\t1.esd', b'2')]))
        with self.assertRaises(fromsoft.FormatError):
            archive.index('t1.esd')

    @unittest.skipUnless(GAME, 'BB_TEST_GAME_DIR not set')
    def test_real_talk_archive_round_trips(self):
        data = fromsoft.dcx_decompress((GAME / 'script/talk/m24_02_00_00.talkesdbnd.dcx').read_bytes())
        archive = fromsoft.Bnd4(data)
        self.assertIn('t242307', ''.join(archive.names))
        self.assertEqual(archive.to_bytes(), data)


class Bxf4Tests(unittest.TestCase):
    def test_header_round_trips_and_entries_read(self):
        from texture_fixtures import bxf4
        import io
        bhd, bdt = bxf4([('a.tpf.dcx', b'first'), ('b.tpf.dcx', b'second entry')])
        archive = fromsoft.Bxf4(bhd)
        self.assertEqual(archive.names, ['a.tpf.dcx', 'b.tpf.dcx'])
        self.assertEqual(archive.header(list(zip(archive.offsets, archive.sizes))), bhd)
        self.assertEqual(archive.read(io.BytesIO(bdt), 1), b'second entry')
        self.assertEqual(archive.index(), {'a.tpf.dcx': 0, 'b.tpf.dcx': 1})
        self.assertEqual(fromsoft.Bxf4.data_header(bdt), bdt[:0x30])

    def test_new_places_keep_everything_else(self):
        from texture_fixtures import bxf4
        bhd, _ = bxf4([('a.tpf.dcx', b'first'), ('b.tpf.dcx', b'second')])
        archive = fromsoft.Bxf4(bhd)
        moved = fromsoft.Bxf4(archive.header([(0x100, 3), (0x30, 9)]))
        self.assertEqual((moved.names, moved.ids), (archive.names, archive.ids))
        self.assertEqual((moved.offsets, moved.sizes), ([0x100, 0x30], [3, 9]))
        self.assertEqual(moved.in_data_order(), [1, 0])

    def test_damaged_and_unsupported_headers(self):
        from texture_fixtures import bxf4
        import io
        bhd, bdt = bxf4([('a.tpf.dcx', b'first')])
        for bad in (b'BND4' + bhd[4:], bhd[:0x50], bhd[:9] + b'\1' + bhd[10:]):
            with self.assertRaises(fromsoft.FormatError):
                fromsoft.Bxf4(bad)
        compressed = bytearray(bhd)
        compressed[0x40] |= 1
        with self.assertRaises(fromsoft.FormatError):
            fromsoft.Bxf4(bytes(compressed))
        with self.assertRaises(fromsoft.FormatError):
            fromsoft.Bxf4(bhd).read(io.BytesIO(bdt[:-2]), 0)
        with self.assertRaises(fromsoft.FormatError):
            fromsoft.Bxf4.data_header(b'BHF4' + bdt[4:])

    @unittest.skipUnless(GAME, 'BB_TEST_GAME_DIR not set')
    def test_real_map_textures_round_trip(self):
        archive = fromsoft.Bxf4((GAME / 'map/m21/m21_0000.tpfbhd').read_bytes())
        self.assertEqual(archive.header(list(zip(archive.offsets, archive.sizes))),
                         (GAME / 'map/m21/m21_0000.tpfbhd').read_bytes())
        with open(GAME / 'map/m21/m21_0000.tpfbdt', 'rb') as bdt:
            textures = fromsoft.Tpf(archive.read(bdt, 0)).textures
        self.assertEqual(len(textures), 1)


class TpfTests(unittest.TestCase):
    def test_textures_and_head(self):
        from texture_fixtures import tpf
        data = tpf(['wall_a', 'wall_n'], b'pixels')
        textures = fromsoft.Tpf(data).textures
        self.assertEqual([t['name'] for t in textures], ['wall_a', 'wall_n'])
        self.assertEqual((textures[0]['width'], textures[0]['size']), (64, 6))
        packed = fromsoft.dcx_compress(data + b'\0' * 200000)
        self.assertEqual([t['name'] for t in fromsoft.Tpf.head(packed).textures], ['wall_a', 'wall_n'])
        self.assertEqual(fromsoft.Tpf.head(packed).platform, 'PS4')

    def test_damaged(self):
        from texture_fixtures import tpf
        with self.assertRaises(fromsoft.FormatError):
            fromsoft.Tpf(b'TPF\0' + b'\0' * 4)
        with self.assertRaises(fromsoft.FormatError):
            fromsoft.Tpf(tpf(['a'])[:-3])


if __name__ == '__main__':
    unittest.main()
