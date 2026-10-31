"""Static validation of the experimental lamp patch against a real 1.09 dump."""
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import enhanced_lamps
import esd
from fromsoft import Bnd4, dcx_decompress


@unittest.skipUnless(os.environ.get('BB_TEST_GAME_DIR'), 'BB_TEST_GAME_DIR not set')
class LampPrototypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dvdroot = Path(os.environ['BB_TEST_GAME_DIR']) / 'dvdroot_ps4'
        cls.outputs = enhanced_lamps.make(cls.dvdroot)

    def test_only_target_scripts_change_and_every_output_round_trips(self):
        self.assertEqual(len(enhanced_lamps.INPUTS), 46)
        self.assertEqual(len(enhanced_lamps.CHALICE_INPUTS), 10)
        self.assertEqual(len(self.outputs), 16)
        changed = 0
        for path, packed in self.outputs.items():
            before = Bnd4(dcx_decompress((self.dvdroot / path).read_bytes()))
            after = Bnd4(dcx_decompress(packed))
            self.assertEqual(before.names, after.names)
            target = {name for map_name, name in (enhanced_lamps.INPUTS |
                                                    enhanced_lamps.CHALICE_INPUTS)
                      if map_name == path.name.split('.')[0]}
            for name, old_data, new_data in zip(before.names, before.files, after.files):
                short = name.replace('\\', '/').rsplit('/', 1)[-1]
                if short in target:
                    self.assertNotEqual(old_data, new_data)
                    script = esd.parse(new_data)
                    menu = script.group(enhanced_lamps.LAMP_MENU_GROUP)
                    self.assertIsNotNone(menu)
                    active = script.group(enhanced_lamps.ACTIVE_GROUP)
                    chalice = path.name.startswith('m29_')
                    active_state = 5 if chalice else enhanced_lamps.ACTIVE_STATE
                    follow_state = 4 if chalice else 5
                    warp_args = 2 if chalice else 3
                    site = script.states[script.state_in(active, active_state)]
                    call = script.cmds[script.runs[site.entry].items[0]]
                    self.assertEqual((call.bank, call.id), (6, enhanced_lamps.LAMP_MENU_GROUP))
                    options = script.states[script.state_in(menu, 1)]
                    menu_commands = [script.cmds[x].id for x in script.runs[options.entry].items]
                    self.assertEqual(menu_commands, [20, 19])
                    self.assertEqual([script.cmds[x].id for x in script.runs[
                        script.states[script.state_in(menu, 7)].entry].items], [19])
                    self.assertEqual([script.cmds[x].id for x in script.runs[
                        script.states[script.state_in(menu, 8)].entry].items], [19])
                    self.assertEqual([script.cmds[x].id for x in script.runs[
                        script.states[script.state_in(menu, 9)].entry].items], [10])
                    choice_state = script.states[script.state_in(menu, 9)]
                    choice_cmd = script.cmds[script.runs[choice_state.entry].items[0]]
                    self.assertEqual([script.exprs[x].code for x in script.runs[choice_cmd.args].items],
                                     [esd.done(esd.lit(0))] * 3)
                    gate = script.conds[script.runs[options.conds].items[0]]
                    self.assertEqual(script.exprs[gate.eval].code,
                                     enhanced_lamps._eq(esd.call(15, [6700]), 1))
                    storage_gate = script.states[script.state_in(menu, 10)]
                    storage_condition = script.conds[script.runs[storage_gate.conds].items[0]]
                    self.assertEqual(script.exprs[storage_condition.eval].code,
                                     enhanced_lamps._eq(esd.call(15, [6701]), 1))
                    warp = script.states[script.state_in(menu, 4)]
                    warp_call = script.cmds[script.runs[warp.entry].items[0]]
                    self.assertEqual((warp_call.bank, warp_call.id),
                                     (6, enhanced_lamps.VANILLA_WARP_GROUP))
                    self.assertEqual([script.exprs[x].code for x in script.runs[warp_call.args].items],
                                     [esd.done(bytes((0x40 + i, 0xb8))) for i in range(warp_args)])
                    original = esd.parse(old_data)
                    original_active = original.group(enhanced_lamps.ACTIVE_GROUP)
                    original_warp = original.states[original.state_in(original_active,
                                                                      active_state)]
                    original_conditions = [original.exprs[original.conds[c].eval].code
                                           for c in original.runs[original_warp.conds].items]
                    patched_conditions = [script.exprs[script.conds[c].eval].code
                                          for c in script.runs[warp.conds].items]
                    self.assertEqual(patched_conditions, original_conditions)
                    restart = script.states[script.state_in(menu, 5)]
                    original_follow = original.states[original.state_in(original_active,
                                                                        follow_state)]
                    self.assertEqual([(script.cmds[c].bank, script.cmds[c].id)
                                      for c in script.runs[restart.entry].items],
                                     [(original.cmds[c].bank, original.cmds[c].id)
                                      for c in original.runs[original_follow.entry].items])
                    end = script.states[script.state_in(menu, 6)]
                    self.assertEqual(script.conds[script.runs[end.conds].items[0]].target, -1)
                    self.assertEqual(esd.serialize(script), new_data)
                    changed += 1
                else:
                    self.assertEqual(old_data, new_data)
        self.assertEqual(changed, 56)

    def test_modified_source_is_rejected(self):
        (map_name, script_name), digest = next(iter(enhanced_lamps.INPUTS.items()))
        packed = (self.dvdroot / 'script' / 'talk' / f'{map_name}.talkesdbnd.dcx').read_bytes()
        archive = Bnd4(dcx_decompress(packed))
        script = archive.files[archive.index(script_name)]
        with self.assertRaises(enhanced_lamps.UnsupportedLamp):
            enhanced_lamps.add_lamp_menu(script + b'changed', digest)


if __name__ == '__main__':
    unittest.main()
