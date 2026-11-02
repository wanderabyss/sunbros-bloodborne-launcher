# SPDX-License-Identifier: GPL-2.0-or-later
"""FLVER2 models (scripts/flver.py): with the dump (BB_TEST_GAME_DIR=<CUSA03173>), the Kirkhammer's
meshes moved onto the game's emissive glow material, checked against the edit and against a
character that ships on that material (c1040)."""
from paths import ROOT
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(ROOT / 'scripts'))
import flver  # noqa: E402
from fromsoft import Bnd4, dcx_decompress  # noqa: E402

GAME = Path(os.environ['BB_TEST_GAME_DIR']) if os.environ.get('BB_TEST_GAME_DIR') else None
MTD = 'N:\\SPRJ\\data\\Material\\mtd\\character\\C[ARSN]_em_Glow.mtd'
EMISSIVE = 'N:\\SPRJ\\data\\Model\\parts\\Weapon\\WP_A_1032\\tex\\WP_A_1032_e.tif'


@unittest.skipUnless(GAME, 'BB_TEST_GAME_DIR is not set')
class GlowTests(unittest.TestCase):
    def meshes(self, path):
        bnd = Bnd4(dcx_decompress((GAME / 'dvdroot_ps4' / path).read_bytes()))
        return [f for n, f in zip(bnd.names, bnd.files) if n.lower().endswith('.flver')]

    def test_kirkhammer_meshes_take_the_glow_material(self):
        for mesh in self.meshes('parts/wp_a_1031.partsbnd.dcx') + self.meshes('parts/wp_a_1031_l.partsbnd.dcx'):
            made = flver.glow_material(mesh, 0, MTD, EMISSIVE, 5, 1.0)
            flver.check_glow(mesh, made, 0, MTD, EMISSIVE, 5, 1.0)     # nothing else moved
            with self.assertRaises(flver.FlverError):   # a plain material only: not twice
                flver.glow_material(made, 0, MTD, EMISSIVE, 5, 1.0)

    def test_made_material_is_shaped_like_the_games_own(self):
        made = flver.Flver(flver.glow_material(self.meshes('parts/wp_a_1031.partsbnd.dcx')[2], 0, MTD, EMISSIVE, 5, 1.0))
        theirs = flver.Flver(self.meshes('chr/c1040.chrbnd.dcx')[0])
        ours, game = made.materials()[0], theirs.materials()[0]
        self.assertEqual(game['mtd'], MTD)
        self.assertEqual([made.textures()[i]['type'] for i in ours['textures']],
                         [theirs.textures()[i]['type'] for i in game['textures']])
        self.assertEqual([(g, u, p) for g, u, p in ours['gx']], [(g, u, p) for g, u, p in game['gx']])


if __name__ == '__main__':
    unittest.main()
