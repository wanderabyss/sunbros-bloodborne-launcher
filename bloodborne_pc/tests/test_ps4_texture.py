# SPDX-License-Identifier: GPL-2.0-or-later
"""The PS4 texture converter (scripts/ps4_texture.py): tiling both ways, and with the dump
(BB_TEST_GAME_DIR=<CUSA03173>) a byte-exact round trip of the Kirkhammer's own textures."""
from paths import ROOT
import os
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(ROOT / 'scripts'))
import ps4_texture  # noqa: E402
from fromsoft import Bnd4, dcx_decompress  # noqa: E402

GAME = Path(os.environ['BB_TEST_GAME_DIR']) if os.environ.get('BB_TEST_GAME_DIR') else None


class TilingTests(unittest.TestCase):
    def test_tile_undoes_detile(self):
        rng = random.Random(7)
        for bw, bh, block in ((8, 8, 8), (16, 24, 16), (3, 5, 8), (1, 1, 8), (40, 9, 16)):
            linear = bytes(rng.randrange(256) for _ in range(bw * bh * block))
            tiled = ps4_texture.tile(linear, bw, bh, block)
            self.assertEqual(len(tiled), ps4_texture.tiled_size(bw, bh, block))
            self.assertEqual(ps4_texture.detile(tiled, bw, bh, block), linear)

    def test_blocks_inside_a_tile_are_in_morton_order(self):
        # Block (1, 0) is second, (0, 1) third, (2, 0) fifth: x0 y0 x1 y1 x2 y2.
        linear = bytes(range(64))
        tiled = ps4_texture.tile(linear, 8, 8, 1)
        self.assertEqual(tiled[:6], bytes([0, 1, 8, 9, 2, 3]))

    def test_mip_chain_size_matches_the_game(self):
        # The Kirkhammer's 2048x1024 BC1 with 12 levels is 1,400,832 bytes: the small levels
        # each take a whole 8x8-block tile.
        size = sum(ps4_texture.tiled_size(bw, bh, 8) for *_wh, bw, bh in ps4_texture.levels(2048, 1024, 12))
        self.assertEqual(size, 1400832)


@unittest.skipUnless(GAME, 'BB_TEST_GAME_DIR is not set')
class GameTests(unittest.TestCase):
    def textures(self, suffix):
        data = (GAME / 'dvdroot_ps4' / 'parts' / f'wp_a_1031{suffix}.partsbnd.dcx').read_bytes()
        return Bnd4(dcx_decompress(data)).files[0]

    def test_kirkhammer_round_trip_is_byte_exact(self):
        for suffix in ('', '_l'):
            raw = self.textures(suffix)
            tpf = ps4_texture.Ps4Tpf(raw)
            self.assertEqual([t.dxgi for t in tpf.textures], [72, 71, 72, 80])   # BC1 sRGB, BC1, BC1 sRGB, BC4
            self.assertEqual(tpf.to_bytes(), raw)
            for t in tpf.textures:   # decoded and encoded again unchanged: the same blocks
                t.set_image(t.image())
            self.assertEqual(tpf.to_bytes(), raw)

    def test_an_edit_changes_only_its_blocks(self):
        from PIL import ImageDraw
        raw = self.textures('_l')
        tpf = ps4_texture.Ps4Tpf(raw)
        t = tpf.textures[0]
        before = list(t.mips)
        im = t.image()
        ImageDraw.Draw(im).rectangle((64, 64, 71, 71), fill=(255, 0, 0, 255))
        t.set_image(im)
        again = ps4_texture.Ps4Tpf(tpf.to_bytes()).textures[0]
        self.assertEqual(again.image().getpixel((68, 68)), (255, 0, 0, 255))
        changed = [i for i in range(len(before[0]) // 8) if before[0][i * 8:i * 8 + 8] != again.mips[0][i * 8:i * 8 + 8]]
        self.assertEqual(len(changed), 4)           # the 8x8 square covers 2x2 blocks
        self.assertEqual(before[-1], again.mips[-1])    # too small a share of the last level to show

    def test_added_texture_keeps_the_others(self):
        from PIL import Image
        raw = self.textures('_l')
        tpf = ps4_texture.Ps4Tpf(raw)
        albedo = tpf.textures[0]
        glow = Image.new('RGBA', (albedo.width, albedo.height), (0, 0, 0, 255))
        glow.paste((120, 175, 255, 255), (64, 64, 128, 96))
        tpf.add_texture('WP_A_1031_e_l', albedo, glow, format_byte=0)
        again = ps4_texture.Ps4Tpf(tpf.to_bytes())
        before = ps4_texture.Ps4Tpf(raw)
        self.assertEqual([t.name for t in again.textures], [t.name for t in before.textures] + ['WP_A_1031_e_l'])
        self.assertEqual([t.mips for t in again.textures[:-1]], [t.mips for t in before.textures])
        self.assertEqual(again.textures[-1].image().getpixel((80, 80)), (123, 174, 255, 255))   # BC1's 5:6:5
        self.assertEqual(again.textures[-1].image().getpixel((10, 10)), (0, 0, 0, 255))

    def test_rename_keeps_the_layout(self):
        tpf = ps4_texture.Ps4Tpf(self.textures(''))
        tpf.rename('WP_A_1031_', 'WP_A_1032_')
        again = ps4_texture.Ps4Tpf(tpf.to_bytes())
        self.assertEqual([t.name for t in again.textures], ['WP_A_1032_a', 'WP_A_1032_n', 'WP_A_1032_r', 'WP_A_1032_s'])
        self.assertEqual(len(tpf.to_bytes()), len(self.textures('')))


if __name__ == '__main__':
    unittest.main()
