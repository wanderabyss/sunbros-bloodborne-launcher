"""Static validation of the experimental boss rematch events, lamp entries and texts."""
import os
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import boss_rematches
import enhanced_lamps
import esd
import menu_assets
from emevd import Emevd
from fromsoft import Bnd4, dcx_decompress


def event_ids(script):
    return [struct.unpack_from('<q', row)[0] for row in script.events]


class InstructionTests(unittest.TestCase):
    def test_emedf_alignment_is_explicit(self):
        self.assertEqual(boss_rematches.instruction(3, 0, 'bBBi', 0, 1, 0, 12411711)[2],
                         bytes.fromhex('00 01 00 00 3f 63 bd 00'))
        self.assertEqual(len(boss_rematches.instruction(4, 2, 'bibf', 0, 10000, 5, 0.0)[2]), 16)


class TableTests(unittest.TestCase):
    def test_every_boss_has_its_own_lamp_ids_and_text(self):
        bosses = boss_rematches.BOSSES
        self.assertEqual(len(bosses), 19)
        self.assertEqual(len({b.lamp for b in bosses}), 19)
        ids = [i for b in bosses for i in b.ids]
        self.assertEqual(len(ids), len(set(ids)))
        rows = menu_assets.read_messages()
        for boss in bosses:
            self.assertIn((boss.map, boss.talk), enhanced_lamps.INPUTS, boss.name)
            self.assertEqual(rows[boss_rematches.message_id(boss)][0], f'Rematch {boss.name}')
            self.assertTrue(menu_assets.FIRST_EVENT_ID <= boss_rematches.message_id(boss)
                            <= menu_assets.LAST_EVENT_ID)

    def test_the_cleric_beast_keeps_the_ids_its_saves_have(self):
        cleric = boss_rematches.BOSSES[0]
        self.assertEqual(cleric.ids, (12411711, 12411712, 12411990, 12411991,
                                      12411980, 12411981, 12411982))
        self.assertEqual((cleric.talk, cleric.respawn), ('t241002.esd', 2412952))
        self.assertEqual(boss_rematches.message_id(cleric), 14000337)


@unittest.skipUnless(os.environ.get('BB_TEST_GAME_DIR'), 'BB_TEST_GAME_DIR not set')
class BossRematchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dvdroot = Path(os.environ['BB_TEST_GAME_DIR']) / 'dvdroot_ps4'
        cls.files = boss_rematches.make(cls.dvdroot)

    def scripts(self, name):
        relative = Path('event') / f'{name}.emevd.dcx'
        original = Emevd(dcx_decompress((self.dvdroot / relative).read_bytes()))
        modified = Emevd(dcx_decompress(self.files[relative]))
        self.assertEqual(modified.to_bytes(), dcx_decompress(self.files[relative]))
        return original, modified

    def test_generated_events_keep_permanent_progress_flags(self):
        def writes(script, flag):
            return [(event_id, bank, code, args) for event_id in event_ids(script)
                    for bank, code, args in script.event_instructions(event_id)
                    if (bank, code) == (2003, 2) and int.from_bytes(args[:4], 'little') == flag]

        maps = {}
        for boss in boss_rematches.BOSSES:
            maps.setdefault(boss.map, []).append(boss)
        self.assertEqual(sum(path.parts[0] == 'event' for path in self.files), len(maps) + 1)
        for name, bosses in maps.items():
            original, modified = self.scripts(name)
            added = [i for boss in bosses for i in boss.ids[4:]]
            self.assertEqual(len(modified.events), len(original.events) + len(added), name)
            self.assertEqual(event_ids(modified)[:len(original.events)], event_ids(original))
            permanent = [f for boss in bosses for f in (boss.defeated, boss.first_entry, *boss.also_defeated)]
            arena = [f for boss in bosses for f in boss.ids[2:4]]
            for event_id in event_ids(original):
                before = original.event_instructions(event_id)
                after = modified.event_instructions(event_id)
                if event_id == 0 or any(event_id in (b.defeated, b.first_entry) for b in bosses):
                    continue
                # Other events only read the arena views in place of the permanent flags.
                self.assertEqual(len(after), len(before), (name, event_id))
                for old, new in zip(before, after):
                    if old != new:
                        self.assertEqual(old[:2], new[:2])
                        self.assertTrue(any(f.to_bytes(4, 'little') in old[2] for f in permanent))
                        self.assertTrue(any(f.to_bytes(4, 'little') in new[2] for f in arena))
            for flag in permanent:
                self.assertEqual(writes(modified, flag), writes(original, flag), (name, flag))

            for boss in bosses:
                request, active, arena_defeated, arena_entry, start, victory, death = boss.ids
                fight = modified.event_instructions(boss.defeated)
                self.assertEqual(fight[0], boss_rematches.instruction(
                    1003, 101, 'BBBi', 0, 0, 0, arena_defeated), boss.name)
                # The rematch branch comes after the last KillBoss and before any reward.
                branch = fight.index(boss_rematches._set(arena_defeated, True))
                self.assertEqual(fight[branch + 1], boss_rematches.instruction(
                    1003, 1, 'BBBi', 2, 0, 0, active))
                kinds = [(bank, code) for bank, code, _ in fight]
                self.assertLess(max(i for i, k in enumerate(kinds) if k == (2003, 12)), branch)
                for reward in ((2003, 4), (2003, 28)):
                    self.assertTrue(all(i > branch for i, k in enumerate(kinds) if k == reward), boss.name)
                # No test of the permanent flags or "this event" is left in its two events.
                for event_id in (boss.defeated, boss.first_entry):
                    for row in modified.event_instructions(event_id):
                        self.assertFalse(boss_rematches._is_own_flag_test(*row), (boss.name, row))
                        if row[:2] != (2003, 2):
                            for flag in (boss.defeated, boss.first_entry, *boss.also_defeated):
                                self.assertNotIn(flag.to_bytes(4, 'little'), row[2], boss.name)
                entry = modified.event_instructions(boss.first_entry)
                self.assertEqual(entry.count(boss_rematches._set(arena_entry, True)), 1)
                # The start warps with the game's own instruction to the respawn point of the
                # boss's own lamp, which the vanilla map has.
                start_rows = modified.event_instructions(start)
                self.assertEqual(start_rows[-2], boss_rematches.instruction(2003, 49, 'i', boss.respawn))
                self.assertEqual(start_rows[0], boss_rematches.instruction(3, 0, 'bBBi', 0, 1, 0, request))

        original, modified = self.scripts('common')
        self.assertEqual(len(modified.events), len(original.events) + len(boss_rematches.BOSSES))
        for event_id in event_ids(original):
            before, after = original.event_instructions(event_id), modified.event_instructions(event_id)
            self.assertEqual(after[:-len(boss_rematches.BOSSES)] if event_id == 0 else after, before)
        for boss in boss_rematches.BOSSES:
            watcher = modified.event_instructions(boss_rematches._leave_event(boss))
            self.assertEqual(watcher[0], boss_rematches.instruction(3, 0, 'bBBi', 0, 1, 0, boss.ids[1]))
            self.assertEqual(watcher[2], boss_rematches.instruction(1003, 7, 'BBBB', 1, 0, *boss.area))
            self.assertEqual(watcher[-1], boss_rematches.instruction(1000, 4, 'B', 1))

    def test_lamp_choice_and_text_are_generated_together(self):
        rematches = boss_rematches.lamp_rows()
        for (map_name, script_name), digest in enhanced_lamps.INPUTS.items():
            relative = Path(f'script/talk/{map_name}.talkesdbnd.dcx')
            archive = Bnd4(dcx_decompress(self.files[relative]))
            script = esd.parse(archive.files[archive.index(script_name)])
            menu = script.group(enhanced_lamps.LAMP_MENU_GROUP)
            rematch = rematches.get((map_name, script_name))
            # Every lamp keeps Level Up and Storage; boss lamps also offer their rematch.
            self.assertEqual(len(menu.states), 14 if rematch else 11, script_name)
            if not rematch:
                continue
            defeated, request, text = rematch
            gate = script.states[script.state_in(menu, 11)]
            condition = script.conds[script.runs[gate.conds].items[0]]
            self.assertEqual(script.exprs[condition.eval].code,
                             enhanced_lamps._eq(esd.call(15, [defeated]), 1))
            listed = script.cmds[script.runs[script.states[script.state_in(menu, 12)].entry].items[0]]
            self.assertEqual([script.exprs[i].code for i in script.runs[listed.args].items][1],
                             esd.done(esd.lit(text)))
            action = script.states[script.state_in(menu, 13)]
            command = script.cmds[script.runs[action.entry].items[0]]
            self.assertEqual((command.bank, command.id), (1, 11))
            self.assertEqual([script.exprs[i].code for i in script.runs[command.args].items],
                             [esd.done(esd.lit(request)), esd.done(esd.lit(1))])
        self.assertEqual(len(rematches), 19)

        languages = sorted(path for path in self.files if path.parts[0] == 'msg')
        self.assertEqual(len(languages), 22)
        for path in languages:
            messages = Bnd4(dcx_decompress(self.files[path]))
            event_text = menu_assets.fmg_read(messages.files[
                messages.ids.index(menu_assets.EVENT_TEXT)])
            for boss in boss_rematches.BOSSES:
                self.assertEqual(event_text[boss_rematches.message_id(boss)].decode('utf-16-le'),
                                 f'Rematch {boss.name}')

    def test_unknown_event_file_fails_closed(self):
        source = self.dvdroot / 'event' / 'm34_00_00_00.emevd.dcx'
        from hashlib import sha256
        original = dcx_decompress(source.read_bytes())
        self.assertEqual(sha256(original).hexdigest(), boss_rematches.INPUT_SHA256['m34_00_00_00'])
        with self.assertRaises(boss_rematches.UnsupportedRematch):
            boss_rematches.INPUT_SHA256['m34_00_00_00'] = '0' * 64
            try:
                boss_rematches.make(self.dvdroot)
            finally:
                boss_rematches.INPUT_SHA256['m34_00_00_00'] = sha256(original).hexdigest()


if __name__ == '__main__':
    unittest.main()
