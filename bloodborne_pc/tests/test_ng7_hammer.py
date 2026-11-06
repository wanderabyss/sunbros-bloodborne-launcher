# SPDX-License-Identifier: GPL-2.0-or-later
"""The NG+7 hammer (scripts/ng7_hammer): its switch, stats and save converter and, with the dump
(BB_TEST_GAME_DIR=<CUSA03173>), the weapon made on Hunter's Arsenal with Thunderwright's left alone."""
from paths import ROOT
import importlib
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(ROOT / 'scripts'))
from ng7_hammer import weapon  # noqa: E402
from ng7_hammer import save_tool  # noqa: E402
from thunderwright import weapon as thunderwright  # noqa: E402
import enhancements  # noqa: E402
from fromsoft import Bnd4, dcx_decompress  # noqa: E402

GAME = Path(os.environ['BB_TEST_GAME_DIR']) if os.environ.get('BB_TEST_GAME_DIR') else None


class SwitchTests(unittest.TestCase):
    def test_entry(self):
        self.assertEqual(enhancements.FEATURES['pc_ng7_hammer'][:2], ('BB_PC_NG7_HAMMER', 'ng7-hammer'))
        self.assertIs(enhancements.MAKERS['pc_ng7_hammer'], enhancements.ng7_hammer)
        self.assertNotIn('pc_ng7_hammer', enhancements.enabled({}, {}))

    def test_it_brings_hunters_arsenal_and_layers_above_it(self):
        self.assertEqual(enhancements.enabled({}, {'BB_PC_NG7_HAMMER': '1'}), ['pc_sojin_chikage', 'pc_ng7_hammer'])
        self.assertEqual(enhancements.enabled({'pc_ng7_hammer': '1', 'pc_sojin_chikage': '1'}, {}),
                         ['pc_sojin_chikage', 'pc_ng7_hammer'])


class WeaponTests(unittest.TestCase):
    def test_every_level(self):
        self.assertEqual(weapon.WEAPON_IDS, [first + 100 * level for first in (2070000, 2140000, 2150000)
                                             for level in range(11)])
        kirk_physical = (105, 115, 125, 135, 145, 155, 165, 175, 185, 195, 210)
        self.assertEqual([weapon.physical(k) for k in kirk_physical], [90, 99, 107, 116, 124, 133, 141, 150, 159, 167, 180])
        self.assertEqual([weapon.bolt(level) for level in range(11)], [66, 73, 79, 86, 92, 99, 106, 112, 119, 125, 132])
        kirk_strength = (60, 64, 68, 72, 76, 80, 84, 88, 92, 96, 100)
        self.assertEqual([weapon.arcane_scaling(s) for s in kirk_strength], [78, 83, 88, 94, 99, 104, 109, 114, 120, 125, 130])

    def test_thunderwright_keeps_its_stats(self):
        self.assertEqual((thunderwright.physical(210), thunderwright.bolt(10)), (150, 110))
        self.assertFalse(set(weapon.WEAPON_IDS) & set(thunderwright.WEAPON_IDS))

    def test_save_tool_agrees(self):
        self.assertEqual([family[0] for family in save_tool.FAMILIES], [v[1] for v in weapon.VARIANTS])
        self.assertEqual([family[1] for family in save_tool.FAMILIES], [v[2] for v in weapon.VARIANTS])
        self.assertEqual(save_tool.SORTS, tuple(v[3] for v in weapon.VARIANTS))
        converter = save_tool.use()
        try:
            self.assertEqual(converter.target(2071000), 8001000)
            self.assertEqual(converter.target(2070300), 8000300)
            self.assertEqual(converter.target_sort(2071000), 45110)
            self.assertEqual(converter.target(2141000), 8011000)
            self.assertEqual(converter.target(2151000), 8021000)
            self.assertEqual(set(converter.SOJIN), set(weapon.WEAPON_IDS))
            self.assertEqual(converter.SOJIN_SORT_PARTS[converter.sort_part(55490)], 10)
        finally:
            # The converter's tables are module-level: put the Sojin Chikage's back for other tests.
            importlib.reload(converter)


@unittest.skipUnless(GAME, 'BB_TEST_GAME_DIR is not set')
class GameTests(unittest.TestCase):
    def test_made_on_hunters_arsenal(self):
        dvdroot = GAME / 'dvdroot_ps4'
        files = {path.as_posix(): data for path, data in enhancements.ng7_hammer(dvdroot).items()}
        self.assertTrue(weapon.has_weapon(files[weapon.GAMEPARAM]))
        self.assertTrue(thunderwright.has_weapon(files[weapon.GAMEPARAM]))
        self.assertFalse(weapon.has_weapon((dvdroot / weapon.GAMEPARAM).read_bytes()))
        self.assertTrue(all(r == weapon.GAMEPARAM or r.endswith('/item.msgbnd.dcx') for r in files))
        self.assertTrue(any(r.endswith('/item.msgbnd.dcx') for r in files))
        from bbparam import Param, load_paramdefs
        gp = Bnd4(dcx_decompress(files[weapon.GAMEPARAM]))
        defs = load_paramdefs()
        w = Param(gp.files[gp.index('EquipParamWeapon.param')], defs['EQUIP_PARAM_WEAPON_ST'])
        fields = ('attackBasePhysics', 'attackBaseThunder', 'correctStrength', 'correctFaith', 'properFaith')
        self.assertEqual(tuple(w.get(2070000, f) for f in fields), (90, 66, 60, 78, 25))
        self.assertEqual(tuple(w.get(2071000, f) for f in fields), (180, 132, 100, 130, 25))
        self.assertEqual(tuple(w.get(2061000, f) for f in fields), (150, 110, 100, 100, 25))
        # Each level upgrades from the one before, with the same materials as the Kirkhammer's.
        for level in range(1, 11):
            row = 2070000 + 100 * level
            self.assertEqual(w.get(row, 'originEquipWep'), row - 100)
            self.assertEqual(w.get(row, 'materialSetId'), w.get(8000000 + 100 * level, 'materialSetId'))
        # Sold at +0 only: a weapon obtained at +10 has its gem slots closed in the save.
        s = Param(gp.files[gp.index('ShopLineupParam.param')], defs['SHOP_LINEUP_PARAM'])
        sold = {s.get(r, 'equipId') for r in s.rows}
        self.assertLessEqual({2060000, 2070000}, sold)
        self.assertNotIn(2071000, sold)
        g = Param(gp.files[gp.index('WeaponGenParam.param')], defs['WEAPON_GEN_PARAM_ST'])
        slots = lambda row: [g.get(row, f'gemSlotType_{i}') for i in range(3)]  # noqa: E731
        for first, want in ((2070000, [1, 2, 1]), (2140000, [1, 4, 1]), (2150000, [1, 2, 4])):
            self.assertEqual(tuple(w.get(first + 1000, f) for f in fields), (180, 132, 100, 130, 25))
            self.assertEqual(slots(first + 1000), want)
            self.assertIn(first, sold)
            self.assertNotIn(first + 1000, sold)


if __name__ == '__main__':
    unittest.main()
