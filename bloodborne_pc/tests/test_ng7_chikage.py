# SPDX-License-Identifier: GPL-2.0-or-later
"""The NG+7 Sojin Chikage (scripts/ng7_chikage): its switch, stats and save converter and, with the
dump (BB_TEST_GAME_DIR=<CUSA03173>), the weapons made on Hunter's Arsenal and on the NG+7 hammer."""
from paths import ROOT
import importlib
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(ROOT / 'scripts'))
from ng7_chikage import weapon  # noqa: E402
from ng7_chikage import save_tool  # noqa: E402
from ng7_hammer import weapon as hammer  # noqa: E402
from sojin import weapon as sojin  # noqa: E402
import enhancements  # noqa: E402
from fromsoft import Bnd4, dcx_decompress  # noqa: E402

GAME = Path(os.environ['BB_TEST_GAME_DIR']) if os.environ.get('BB_TEST_GAME_DIR') else None


class SwitchTests(unittest.TestCase):
    def test_entry(self):
        self.assertEqual(enhancements.FEATURES['pc_ng7_chikage'][:2], ('BB_PC_NG7_CHIKAGE', 'ng7-chikage'))
        self.assertIs(enhancements.MAKERS['pc_ng7_chikage'], enhancements.ng7_chikage)
        self.assertNotIn('pc_ng7_chikage', enhancements.enabled({}, {}))

    def test_it_brings_hunters_arsenal_and_layers_above_it(self):
        self.assertEqual(enhancements.enabled({}, {'BB_PC_NG7_CHIKAGE': '1'}), ['pc_sojin_chikage', 'pc_ng7_chikage'])
        self.assertEqual(enhancements.enabled({}, {'BB_PC_NG7_CHIKAGE': '1', 'BB_PC_NG7_HAMMER': '1'}),
                         ['pc_sojin_chikage', 'pc_ng7_hammer', 'pc_ng7_chikage'])

    def test_it_is_remade_when_the_hammer_changes(self):
        self.assertEqual(enhancements.COMBINED['pc_ng7_chikage'], ('pc_ng7_hammer',))


class WeaponTests(unittest.TestCase):
    def test_every_level(self):
        self.assertEqual(len(weapon.WEAPON_IDS), 33)
        self.assertEqual(weapon.physical(92), 110)
        self.assertEqual(weapon.physical(184), 221)
        self.assertEqual(weapon.bloodtinge(60), 78)
        self.assertEqual(weapon.bloodtinge(110), 143)

    def test_ids_are_its_own(self):
        self.assertFalse(set(weapon.WEAPON_IDS) & sojin.WEAPON_IDS)
        self.assertFalse(set(weapon.WEAPON_IDS) & set(hammer.WEAPON_IDS))

    def test_save_tool_agrees(self):
        self.assertEqual([family[0] for family in save_tool.FAMILIES], [v[1] for v in weapon.VARIANTS])
        self.assertEqual(save_tool.SORTS, tuple(v[3] for v in weapon.VARIANTS))
        converter = save_tool.use()
        try:
            self.assertEqual(converter.target(2081000), 2001000)
            self.assertEqual(converter.target(2100300), 2010300)
            self.assertEqual(converter.target(2111000), 2021000)
            self.assertEqual(converter.target_sort(2081000), 55110)
            self.assertEqual(set(converter.SOJIN), set(weapon.WEAPON_IDS))
        finally:
            # The converter's tables are module-level: put the Sojin Chikage's back for other tests.
            importlib.reload(converter)


@unittest.skipUnless(GAME, 'BB_TEST_GAME_DIR is not set')
class GameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dvdroot = GAME / 'dvdroot_ps4'
        cls.alone = {p.as_posix(): d for p, d in enhancements.ng7_chikage(cls.dvdroot, ['pc_ng7_chikage']).items()}

    def test_made_on_hunters_arsenal(self):
        files = self.alone
        self.assertTrue(weapon.has_weapon(files[weapon.GAMEPARAM]))
        self.assertTrue(sojin.has_weapon(files[weapon.GAMEPARAM]))
        self.assertFalse(hammer.has_weapon(files[weapon.GAMEPARAM]))
        self.assertTrue(all(r == weapon.GAMEPARAM or r.endswith('/item.msgbnd.dcx') for r in files))
        from bbparam import Param, load_paramdefs
        gp = Bnd4(dcx_decompress(files[weapon.GAMEPARAM]))
        defs = load_paramdefs()
        w = Param(gp.files[gp.index('EquipParamWeapon.param')], defs['EQUIP_PARAM_WEAPON_ST'])
        fields = ('attackBasePhysics', 'correctStrength', 'correctAgility', 'correctMagic', 'behaviorVariationId', 'equipModelId')
        for first, source in ((2080000, 2040000), (2100000, 2050000), (2110000, 2030000)):
            self.assertEqual(tuple(w.get(first, f) for f in fields), (110, 15, 45, 78, 2030, 1062))
            self.assertEqual(tuple(w.get(first + 1000, f) for f in fields), (221, 25, 65, 143, 2030, 1062))
            self.assertEqual(tuple(w.get(source + 1000, f) for f in fields), (184, 25, 65, 110, 2030, 1062))
            # Each level upgrades from the one before, with the same materials as the Chikage's.
            for level in range(1, 11):
                self.assertEqual(w.get(first + 100 * level, 'originEquipWep'), first + 100 * (level - 1))
                self.assertEqual(w.get(first + 100 * level, 'materialSetId'), w.get(source + 100 * level, 'materialSetId'))
        # Sold at +0 only: a weapon obtained at +10 has its gem slots closed in the save.
        s = Param(gp.files[gp.index('ShopLineupParam.param')], defs['SHOP_LINEUP_PARAM'])
        sold = {s.get(r, 'equipId') for r in s.rows}
        self.assertLessEqual({2040000, 2080000, 2100000, 2110000}, sold)
        self.assertNotIn(2081000, sold)
        g = Param(gp.files[gp.index('WeaponGenParam.param')], defs['WEAPON_GEN_PARAM_ST'])
        self.assertEqual(g.get(2111000, 'gemSlotType_2'), g.get(2021000, 'gemSlotType_2'))

    def test_keeps_the_hammer_when_both_are_on(self):
        files = enhancements.ng7_chikage(self.dvdroot, ['pc_ng7_hammer', 'pc_ng7_chikage'])
        param = files[Path(weapon.GAMEPARAM)]
        self.assertTrue(weapon.has_weapon(param))
        self.assertTrue(hammer.has_weapon(param))


if __name__ == '__main__':
    unittest.main()
