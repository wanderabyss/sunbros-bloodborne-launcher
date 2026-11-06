# SPDX-License-Identifier: GPL-2.0-or-later
"""Thunderwright's Kirkhammer (scripts/thunderwright): its ids, the lightning's three sizes, the save
converter and, with the dump (BB_TEST_GAME_DIR=<CUSA03173>), the weapon's files, built alone and
on the Sojin Chikage's as Hunter's Arsenal does."""
from paths import ROOT
import os
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(ROOT / 'scripts'))
from thunderwright import weapon  # noqa: E402
from thunderwright import save_tool  # noqa: E402
import enhancements  # noqa: E402
from fromsoft import Bnd4, dcx_decompress  # noqa: E402

GAME = Path(os.environ['BB_TEST_GAME_DIR']) if os.environ.get('BB_TEST_GAME_DIR') else None


class WeaponTests(unittest.TestCase):
    def test_ids_and_shop(self):
        self.assertEqual(weapon.WEAPON_IDS, [2060000 + 100 * level for level in range(11)])
        self.assertEqual(weapon.PRICE, 10000)
        self.assertEqual((weapon.ARCANE_NEEDED, weapon.NO_PAPERS), (25, 0))

    def test_damage_is_split_not_added(self):
        # The Kirkhammer's 105 / 210 physical becomes 75 / 150 beside bolt 55 / 110 (4.2.18).
        self.assertEqual([weapon.physical(105), weapon.physical(210)], [75, 150])
        self.assertEqual([weapon.bolt(level) for level in (0, 1, 3, 10)], [55, 61, 72, 110])
        # Static Draw's free charge is short; Thunder Chariot's, for a bullet, keeps 10 s.
        self.assertEqual((weapon.DRAW_CHARGE_TIME, weapon.CHARGE_TIME), (4.0, 10.0))
        self.assertEqual(weapon.CHAINS['draw']['charge'], weapon.DRAW_CHARGE)

    def test_storm_and_transform_flash(self):
        # 4.2.18's Mjolnir-style look: Bolt Paper's glow (stateInfo 61) on the hammer only, and a
        # harmless bolt at the head on all four transform attacks.
        self.assertEqual((weapon.STORM_LOOK, weapon.TRICK_ONLY), (61, 2))
        self.assertIn(weapon.FLASH['judge'], weapon.OUR_JUDGES)
        self.assertEqual(len(weapon.TO_HAMMER + weapon.TO_SWORD), 4)

    def test_lightning_sizes_tell_apart(self):
        # Thunder Chariot shows a third of its strikes, the others hit unseen; only it thins them.
        self.assertEqual({name: chain.get('shown', 1) for name, chain in weapon.CHAINS.items()},
                         {'high': 3, 'medium': 1, 'small': 1, 'draw': 1})
        # small < medium < high by length, and only the high one fans out; only it takes a bullet.
        sizes = {name: (chain['fan'][0], len(chain['strikes'])) for name, chain in weapon.CHAINS.items()}
        self.assertEqual(sizes, {'high': (3, 18), 'medium': (1, 12), 'small': (1, 6), 'draw': (1, 6)})
        self.assertEqual(weapon.BULLETS_TAKEN, 1)
        self.assertEqual(len(set(weapon.OUR_JUDGES)), len(weapon.OUR_JUDGES))

    def test_hunters_arsenal_makes_both(self):
        self.assertIs(enhancements.MAKERS['pc_sojin_chikage'], enhancements.hunters_arsenal)

    def test_own_model(self):
        self.assertEqual((weapon.MODEL, weapon.KIRK_MODEL), (1032, 1031))
        self.assertEqual(weapon.PARTS, ['parts/wp_a_1032.partsbnd.dcx', 'parts/wp_a_1032_l.partsbnd.dcx'])
        # Same length, so the meshes' string offsets stay.
        self.assertEqual(len(weapon.TEX_PATH[0]), len(weapon.TEX_PATH[1]))


class RuneIronTests(unittest.TestCase):
    def test_the_whole_elder_futhark(self):
        from thunderwright import rune_iron
        self.assertEqual(len(rune_iron.FUTHARK), 24)
        self.assertEqual(set(rune_iron.FUTHARK), set(rune_iron.RUNES))
        self.assertTrue(set(rune_iron.THUNRAZ) <= set(rune_iron.RUNES))
        for name, strokes in rune_iron.RUNES.items():
            for stroke in strokes:   # inside the rune's box: 1 tall, 0.6 wide
                self.assertTrue(all(0 <= x <= 0.6 and 0 <= y <= 1 for x, y in stroke), name)

    def test_design_stays_on_the_hammer_head(self):
        from thunderwright import rune_iron
        inlay, faces = rune_iron.design()
        top = round(rune_iron.HEAD_TOP * rune_iron.DESIGN[1])
        self.assertIsNone(inlay.crop((0, 0, rune_iron.DESIGN[0], top)).getbbox())
        self.assertIsNone(faces.crop((0, 0, rune_iron.DESIGN[0], top)).getbbox())
        self.assertIsNotNone(inlay.getbbox())
        self.assertEqual({rune_iron.role(n) for n in ('WP_A_1031_a', 'WP_A_1031_n_l', 'WP_A_1031_r', 'WP_A_1031_s_l')},
                         {'_a', '_n', '_r', '_s'})


class SaveToolTests(unittest.TestCase):
    def test_every_level_becomes_the_kirkhammer(self):
        converter = save_tool.use()
        try:
            self.assertEqual(converter.target(2060000), 8000000)
            self.assertEqual(converter.target(2061000), 8001000)     # +10 -> Kirkhammer +10
            self.assertEqual(converter.target_sort(2060300), 45103)
            self.assertEqual(set(converter.SOJIN), set(weapon.WEAPON_IDS))
            data = b'\0' * 8 + struct.pack('<I', 2060050) + b'\0' * 4 + struct.pack('<I', 2060200) + b'\0' * 4
            self.assertEqual(converter.find_values(data), [16])     # 2060050 is not a weapon id
        finally:
            # The converter's tables are module-level: put the Sojin Chikage's back for other tests.
            import importlib
            importlib.reload(converter)


@unittest.skipUnless(GAME, 'BB_TEST_GAME_DIR is not set')
class GameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dvdroot = GAME / 'dvdroot_ps4'
        weapon.set_game(cls.dvdroot)

    def test_files_are_made_and_checked(self):
        files = weapon.make(self.dvdroot)   # make() runs verify() on what it made
        self.assertEqual({weapon.GAMEPARAM, weapon.ANIBND} - set(files), set())
        self.assertTrue(weapon.has_weapon(files[weapon.GAMEPARAM]))
        self.assertFalse(weapon.has_weapon((self.dvdroot / weapon.GAMEPARAM).read_bytes()))
        with self.assertRaises(weapon.ThunderwrightError):   # the lightning is never added twice
            weapon.anibnd_file(files[weapon.ANIBND])
        # The sky lightning's effects join the common bank, checked against m36's copies.
        from thunderwright import sky
        self.assertIn(sky.COMMON, files)
        sky.verify((self.dvdroot / sky.COMMON).read_bytes(), files[sky.COMMON], (self.dvdroot / sky.SOURCE).read_bytes())
        # Its own rune-iron model (make() ran verify_model() on it); the Kirkhammer's is not touched.
        self.assertEqual(set(weapon.PARTS) - set(files), set())
        self.assertFalse(any('wp_a_1031' in relative for relative in files))
        from bbparam import Param, load_paramdefs
        gp = Bnd4(dcx_decompress(files[weapon.GAMEPARAM]))
        w = Param(gp.files[gp.index('EquipParamWeapon.param')], load_paramdefs()['EQUIP_PARAM_WEAPON_ST'])
        self.assertEqual({w.get(r, 'equipModelId') for r in weapon.WEAPON_IDS}, {weapon.MODEL})
        kirkhammer = [r for r in w.rows if 8000000 <= r < 8030000]
        self.assertEqual({w.get(r, 'equipModelId') for r in kirkhammer}, {weapon.KIRK_MODEL})

    def test_plain_model_copy_is_the_kirkhammer(self):
        files = weapon.model_files(rune_iron=False)
        weapon.verify_model(files, rune_iron=False)    # every texel, mesh and animation the same
        with self.assertRaises(weapon.ThunderwrightError):   # and it is not taken for rune-iron
            weapon.verify_model(files)

    def test_hunters_arsenal_has_both_weapons(self):
        from sojin import weapon as sojin
        files = {path.as_posix(): data for path, data in enhancements.hunters_arsenal(self.dvdroot).items()}
        self.assertTrue(sojin.has_weapon(files[weapon.GAMEPARAM]))
        self.assertTrue(weapon.has_weapon(files[weapon.GAMEPARAM]))
        self.assertIn('parts/wp_a_1062.partsbnd.dcx', files)    # the Sojin Chikage's model stays
        self.assertIn('parts/wp_a_1032.partsbnd.dcx', files)    # and Thunderwright's


if __name__ == '__main__':
    unittest.main()
