# SPDX-License-Identifier: GPL-2.0-or-later
"""Sojin Chikage (scripts/sojin): the save converter's ids, the shop ranges and, with the dump
(BB_TEST_GAME_DIR=<CUSA03173>), the weapon's files and their merge into another gameparam."""
from paths import ROOT
import os
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(ROOT / 'scripts'))
from sojin import save_tool, weapon  # noqa: E402
import enhancements  # noqa: E402

GAME = Path(os.environ['BB_TEST_GAME_DIR']) if os.environ.get('BB_TEST_GAME_DIR') else None


class SaveToolTests(unittest.TestCase):
    def test_every_weapon_becomes_its_own_chikage(self):
        self.assertEqual(save_tool.target(2040000), 2000000)    # Sojin Chikage -> Chikage
        self.assertEqual(save_tool.target(2050300), 2010300)    # Uncanny +3 -> Uncanny Chikage +3
        self.assertEqual(save_tool.target(2031000), 2021000)    # Lost +10 -> Lost Chikage +10
        self.assertEqual(set(save_tool.SOJIN), weapon.WEAPON_IDS)
        self.assertEqual(save_tool.target_sort(2050300), 55203)

    def test_only_exact_weapon_ids_count(self):
        # A save holds 2050495 in unrelated data: it is not a weapon id and must not block a conversion.
        data = b'\0' * 8 + struct.pack('<I', 2050495) + b'\0' * 4 + struct.pack('<I', 2050100) + b'\0' * 4
        self.assertEqual(save_tool.find_values(data), [16])

    def test_sort_parts_of_old_and_new_ids(self):
        # 55400 + level: the stand-alone mod's Lost Sojin Chikage, now Sojin Chikage's.
        for sort in (55400, 55410, 55420, 55440, 55450):
            self.assertIn(save_tool.sort_part(sort), save_tool.SOJIN_SORT_PARTS)


class FeatureTests(unittest.TestCase):
    def test_switch_and_maker(self):
        self.assertEqual(enhancements.FEATURES['pc_sojin_chikage'][:2], ('BB_PC_SOJIN', 'sojin-chikage'))
        self.assertIn('pc_sojin_chikage', enhancements.MAKERS)
        self.assertEqual(enhancements.enabled({}, {'BB_PC_SOJIN': '1'}), ['pc_sojin_chikage'])
        self.assertNotIn('pc_sojin_chikage', enhancements.enabled({}, {}))

    def test_the_three_weapons(self):
        self.assertEqual([v[0] for v in weapon.VARIANTS],
                         ['Sojin Chikage', 'Uncanny Sojin Chikage', 'Lost Sojin Chikage'])
        self.assertEqual(weapon.PRICE, 10000)
        self.assertEqual(len(weapon.WEAPON_IDS), 33)
        self.assertIn(2030000, weapon.WEAPON_IDS)    # the stand-alone mod's ids stay


@unittest.skipUnless(GAME, 'BB_TEST_GAME_DIR is not set')
class GameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dvdroot = GAME / 'dvdroot_ps4'
        weapon.set_game(cls.dvdroot)

    def test_the_game_shop_has_five_price_stages(self):
        talk = (self.dvdroot / weapon.TALK).read_bytes()
        self.assertEqual(weapon.shop_ranges(talk), [(100000 + 10000 * k, 109999 + 10000 * k) for k in range(5)])

    def test_files_are_made_and_checked(self):
        files = weapon.make(self.dvdroot)   # make() runs verify() on what it made
        self.assertIn(weapon.GAMEPARAM, files)
        self.assertIn('chr/c0000.anibnd.dcx', files)
        self.assertIn('msg/engus/item.msgbnd.dcx', files)
        self.assertTrue(weapon.has_weapon(files[weapon.GAMEPARAM]))
        self.assertFalse(weapon.has_weapon((self.dvdroot / weapon.GAMEPARAM).read_bytes()))
        with self.assertRaises(weapon.SojinError):   # rows that are there already are never doubled
            weapon.add_params(files[weapon.GAMEPARAM], (self.dvdroot / weapon.TALK).read_bytes())


if __name__ == '__main__':
    unittest.main()
