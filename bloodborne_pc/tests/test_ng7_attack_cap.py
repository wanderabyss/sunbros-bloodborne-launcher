# SPDX-License-Identifier: GPL-2.0-or-later
"""The NG+7 enemy attack limit (enhancements.py ng7_attack_cap): its setting and, with the dump
(BB_TEST_GAME_DIR=<CUSA03173>), a gameparam capped on top of the NG+7 hammer's."""
from paths import ROOT
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(ROOT / 'scripts'))
import enhancements  # noqa: E402
from fromsoft import Bnd4, dcx_decompress  # noqa: E402

GAME = Path(os.environ['BB_TEST_GAME_DIR']) if os.environ.get('BB_TEST_GAME_DIR') else None


class SettingTests(unittest.TestCase):
    def test_values(self):
        self.assertIsNone(enhancements.attack_cap({}, {}))
        self.assertIsNone(enhancements.attack_cap({'ng7_attack_cap': 'off'}, {}))
        self.assertIsNone(enhancements.attack_cap({'ng7_attack_cap': 'nonsense'}, {}))
        self.assertIsNone(enhancements.attack_cap({'ng7_attack_cap': '0.5'}, {}))
        self.assertIsNone(enhancements.attack_cap({'ng7_attack_cap': 'inf'}, {}))
        self.assertEqual(enhancements.attack_cap({'ng7_attack_cap': '1.5'}, {}), 1.5)
        self.assertEqual(enhancements.attack_cap({'ng7_attack_cap': '1.5'}, {'BB_PC_NG7_ATTACK_CAP': '2'}), 2.0)


@unittest.skipUnless(GAME, 'BB_TEST_GAME_DIR is not set')
class GameTests(unittest.TestCase):
    def params(self, raw):
        from bbparam import Param, load_paramdefs
        defs = load_paramdefs()
        gp = Bnd4(dcx_decompress(raw))
        return (Param(gp.files[gp.index('NpcParam.param')], defs['NPC_PARAM_ST']),
                Param(gp.files[gp.index('SpEffectParam.param')], defs['SP_EFFECT_PARAM_ST']),
                Param(gp.files[gp.index('EquipParamWeapon.param')], defs['EQUIP_PARAM_WEAPON_ST']))

    def test_capped_on_the_hammer_keeps_everything_else(self):
        from thunderwright import weapon
        relative = weapon.GAMEPARAM
        with tempfile.TemporaryDirectory() as folder:
            keys = ['pc_sojin_chikage', 'pc_ng7_hammer', 'pc_ng_plus_7']
            made = enhancements.make(GAME, folder, keys, 1.5)
            self.assertEqual([path.name for path in made], ['hunters-arsenal', 'ng7-hammer', 'ng-plus-7'])
            below = (made[1] / 'dvdroot_ps4' / relative).read_bytes()
            capped = (made[2] / 'dvdroot_ps4' / relative).read_bytes()
            self.assertTrue((made[2] / 'dvdroot_ps4' / 'event' / 'm21_00_00_00.emevd.dcx').is_file())
            # Off again: NG+7 world's layer has no gameparam, so the one below is used as it is.
            off = enhancements.make(GAME, folder, keys)
            self.assertFalse((off[2] / 'dvdroot_ps4' / relative).exists())
        npc0, effect0, _weapons0 = self.params(below)
        npc1, effect1, weapons1 = self.params(capped)
        self.assertEqual(npc0.rows, npc1.rows)
        self.assertEqual(weapons1.get(2071000, 'attackBasePhysics'), 180)
        rows = {npc1.get(r, 'GameClearSpEffectID') for r in npc1.rows} & set(effect1.rows)
        changed = 0
        for row in rows:
            for field in enhancements.ATTACK_RATES:
                was, now = effect0.get(row, field), effect1.get(row, field)
                self.assertLessEqual(now * enhancements.NG7_CYCLE, 1.5 + 1e-5)
                if was * enhancements.NG7_CYCLE <= 1.5:
                    self.assertEqual(was, now)
                else:
                    changed += 1
            self.assertEqual(effect0.get(row, 'maxHpRate'), effect1.get(row, 'maxHpRate'))
            self.assertEqual(effect0.get(row, 'haveSoulRate'), effect1.get(row, 'haveSoulRate'))
            self.assertEqual(effect0.get(row, 'physicsDiffenceRate'), effect1.get(row, 'physicsDiffenceRate'))
        self.assertGreater(changed, 0)
        self.assertEqual([r for r in effect0.rows if r not in rows and effect0.rows[r] != effect1.rows[r]], [])


if __name__ == '__main__':
    unittest.main()
