#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Experimental boss rematches at the bosses' own lamps, generated from the player's 1.09 dump.

Each of the 19 bosses with a lamp of its own (the lamp its defeat lights) gets a "Rematch ..."
entry in that lamp's menu once it is defeated. Choosing it costs one Insight when the player has
any, reloads the map at the lamp and wakes the arena; winning, dying or leaving the map puts the
arena back as the save has it. The game's completed-boss and first-entry flags are never cleared:
the boss's map events read private "arena" copies of them instead, and a rematch kill skips the
first-kill rewards (item lots, trophy, progression flags).

The per-boss data (defeat flag, the lamp its defeat lights) comes from the game's own scripts,
after droogie's bbhost boss_rush plugin (GPL-3.0-or-later) and tools/mapval_lamps.py. Every edit
is checked against the expected 1.09 instruction and the input files are pinned by hash.
Gehrman, the Moon Presence and Micolash have no lamp of their own and are not offered.
"""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import struct

from emevd import Emevd
from fromsoft import dcx_compress, dcx_decompress
import enhanced_lamps
import menu_assets


INPUT_SHA256 = {
    'm22_00_00_00': '31bf4153166d8b4f56892baffeddb4bfffbaed594cd89b3b56f2e11a01099d92',
    'm23_00_00_00': '580e98e17af0da6b3d34c9aee40265b45df8e8e12daa4e8bb2b53c02819d8eaf',
    'm24_00_00_00': '4ea0c75fd46ceba5e09b6635c207a5c867d5587606158ea5741039e28d2d218a',
    'm24_01_00_00': '4341aca7efe61fd390dc90cb4996af2fd5de8ad3ac39b7e5a2e06b6681925672',
    'm24_02_00_00': '29f4ec0a0df95e5897c3808ab96339bda3b0ab99b356f2fcfb1ef8fd8c66f99d',
    'm25_00_00_00': '1351b2da78b33ae00f4c896210c25e626c37fee64df1eb4846680ba9eaa2f389',
    'm26_00_00_00': '95d168643c0ca1e96d77577be2723dc15ad6af8588e729ca6ab76cd609bc9331',
    'm27_00_00_00': '2752df4d6b12ffd6d8b5374406b52f9c19efea37ccf58447b3d51d66aa83a6d7',
    'm28_00_00_00': '0ccd4af2b87b948ad987b4f76cb2a8864e12a4b9ca29ae89388d930731f837d0',
    'm32_00_00_00': 'ff65db9ce2990d35d7ea2467f38104d2f39e2bf103b59b54cf21e08704bb1422',
    'm33_00_00_00': '9375a331f1727e6d1f89f233773af1ffdeaa1eba97f97e1122dc6fc83ee78ff4',
    'm34_00_00_00': '61cbe85daf9097619094e053edcab1233432c86619b96198845d5469e917268c',
    'm35_00_00_00': '4989dfbe383c30e65847c1abfc5d8e09adea0b6caff11320f864069566e1e628',
    'm36_00_00_00': '9ea8f27a0e5b93884b528bbab79bc7da52a890aef07ae886f777df2450583639',
    'common': '8a76ce5746747e2696d20e2f5d0695bbdb044e83a9d64a3d073b58d76f48825b',
}
FIRST_LEAVE_EVENT = 10009980
FIRST_MESSAGE = 14000337


@dataclass(frozen=True)
class Boss:
    name: str               # menu text: "Rematch <name>"
    defeated: int           # its defeat event, whose flag the game sets when it dies
    lamp: int               # the lamp its defeat lights (mapval_lamps.py's "requires" column)
    met: int = 2            # its first-meeting event: defeat + 2, + 1 in The Old Hunters
    # Flags that also mean "defeated" to its arena's events (Ludwig's fight reads 9471).
    also_defeated: tuple[int, ...] = ()
    # Ids the Cleric Beast prototype shipped with, kept so its saves stay valid.
    fixed_ids: tuple[int, ...] = ()

    @property
    def map(self) -> str:
        return f'm{self.lamp // 100000}_{self.lamp // 10000 % 10:02d}_00_00'

    @property
    def area(self) -> tuple[int, int]:
        return self.lamp // 100000, self.lamp // 10000 % 10

    @property
    def talk(self) -> str:
        """The lamp's talk script, which its warp object (lamp - 1000) names in the map."""
        return f't{self.lamp // 100000}{self.lamp // 10000 % 10}{self.lamp % 10:03d}.esd'

    @property
    def respawn(self) -> int:
        """Its ReturnPointParam row's respawn point: where resting there puts the player."""
        return self.lamp + 1000

    @property
    def first_entry(self) -> int:
        return self.defeated + self.met

    @property
    def ids(self) -> tuple[int, int, int, int, int, int, int]:
        """request, active, arena defeated, arena entry flags; start, victory, death events."""
        if self.fixed_ids:
            return self.fixed_ids
        d = self.defeated
        return d + 11, d + 12, d + 90, d + 91, d + 80, d + 81, d + 82


BOSSES = (
    Boss('Cleric Beast', 12411700, 2411952,
         fixed_ids=(12411711, 12411712, 12411990, 12411991, 12411980, 12411981, 12411982)),
    Boss('Father Gascoigne', 12411800, 2411953),
    Boss('Blood-starved Beast', 12301800, 2301951),
    Boss('Vicar Amelia', 12401800, 2401951),
    Boss('The Witch of Hemwick', 12201800, 2201951),
    Boss('Darkbeast Paarl', 12301700, 2301952),
    Boss('Shadow of Yharnam', 12701800, 2701951),
    Boss('Rom, the Vacuous Spider', 13201800, 3201952),
    Boss('The One Reborn', 12801800, 2801951),
    Boss('Martyr Logarius', 12501800, 2501952),
    Boss('Amygdala', 13301800, 3301951),
    Boss('Celestial Emissary', 12421700, 2421952),
    Boss('Ebrietas, Daughter of the Cosmos', 12421800, 2421951),
    Boss("Mergo's Wet Nurse", 12601800, 2601951),
    Boss('Ludwig, the Holy Blade', 13401800, 3401952, met=1, also_defeated=(9471,)),
    # Its usual arena flag (defeat + 90, 13501940) is one of the game's own.
    Boss('Living Failures', 13501850, 3501951, met=1,
         fixed_ids=(13501861, 13501862, 13501970, 13501971, 13501930, 13501931, 13501932)),
    Boss('Lady Maria of the Astral Clocktower', 13501800, 3501952, met=1),
    Boss('Laurence, the First Vicar', 13401850, 3401953, met=1),
    Boss('Orphan of Kos', 13601800, 3601952, met=1),
)


class UnsupportedRematch(ValueError):
    pass


def instruction(bank: int, code: int, fmt: str, *values: int | float) -> tuple[int, int, bytes]:
    """Build one EMEVD instruction argument list from the game's documented EMEDF types."""
    if len(fmt) != len(values) or any(ch not in 'bBif' for ch in fmt):
        raise ValueError('unsupported event argument format')
    args = bytearray()
    for kind, value in zip(fmt, values):
        size = 4 if kind in 'if' else 1
        args.extend(bytes(-len(args) % size))
        args.extend(struct.pack('<' + kind, value))
    args.extend(bytes(-len(args) % 4))
    return bank, code, bytes(args)


def _set(flag: int, enabled: bool) -> tuple[int, int, bytes]:
    return instruction(2003, 2, 'iB', flag, int(enabled))


def _end_if_flag_off(flag: int) -> tuple[int, int, bytes]:
    return instruction(1003, 2, 'BBBi', 0, 0, 0, flag)


def _await_flag_on(flag: int) -> tuple[int, int, bytes]:
    return instruction(3, 0, 'bBBi', 0, 1, 0, flag)


def _event_ids(script: Emevd) -> list[int]:
    return [struct.unpack_from('<q', row)[0] for row in script.events]


# A flag test (IfEventFlag 3[0], Skip/End/Goto IfEventFlag 1003[1]/[2]/[101]) names its flag as
# (condition or count, state, flag type, pad, flag id); type 1 or 2 with id 0 is "this event".
FLAG_TESTS = {(3, 0), (1003, 1), (1003, 2), (1003, 101)}


def _own_flag_to(args: bytes, flag: int) -> bytes:
    return args[:2] + b'\0' + args[3:4] + struct.pack('<I', flag) + args[8:]


def _is_own_flag_test(bank: int, code: int, args: bytes) -> bool:
    return ((bank, code) in FLAG_TESTS and len(args) == 8 and args[2] in (1, 2)
            and args[4:8] == bytes(4))


def _assert_ids_available(dvdroot: Path, bosses) -> None:
    """Avoid hijacking flags or events used anywhere in the player's dump."""
    event_ids, flags = set(), set()
    for number, boss in enumerate(bosses):
        request, active, arena_defeated, arena_entry, start, victory, death = boss.ids
        event_ids |= {start, victory, death, _leave_event(boss)}
        flags |= {request, active, arena_defeated, arena_entry}
    if len(event_ids) != 4 * len(bosses) or len(flags) != 4 * len(bosses) or event_ids & flags:
        raise UnsupportedRematch('two rematches share an id')
    event_files = sorted((dvdroot / 'event').glob('*.emevd.dcx'))
    if not event_files:
        raise UnsupportedRematch('game dump has no event scripts')
    # A raw byte search is deliberately conservative: none of these may occur as an immediate
    # value anywhere in the game's event files, even in unrelated instructions.
    patterns = [struct.pack('<I', flag) for flag in flags | event_ids]
    for path in event_files:
        script = Emevd(dcx_decompress(path.read_bytes()))
        if event_ids.intersection(_event_ids(script)):
            raise UnsupportedRematch(f'{path.name}: a rematch event ID is already used')
        args = bytes(script.args)
        if any(pattern in args for pattern in patterns):
            raise UnsupportedRematch(f'{path.name}: a rematch flag is already used')


def _leave_event(boss: Boss) -> int:
    return FIRST_LEAVE_EVENT + BOSSES.index(boss)


def message_id(boss: Boss) -> int:
    return FIRST_MESSAGE + BOSSES.index(boss)


def _boss_events(script: Emevd, boss: Boss) -> None:
    request, active, arena_defeated, arena_entry, start, victory, death = boss.ids
    defeated, first_entry = boss.defeated, boss.first_entry
    ids = _event_ids(script)
    if defeated not in ids or first_entry not in ids:
        raise UnsupportedRematch(f'{boss.name}: its defeat or first-meeting event is missing')

    # Every map event reads a private arena view of the boss and entry state. Original completion
    # flags stay intact even if the mod disappears during a rematch. Leave writes to those original
    # flags alone so first-time vanilla progression still saves normally.
    originals = [(event_id, script.event_instructions(event_id)) for event_id in ids]
    substitutions = ((defeated, arena_defeated), (first_entry, arena_entry))
    extra = {struct.pack('<I', flag): struct.pack('<I', arena_defeated) for flag in boss.also_defeated}
    for event_id, rows in originals:
        for position, (bank, code, args) in enumerate(rows):
            if (bank, code) == (2003, 2):  # SetEventFlag writes: preserve permanent game flags.
                continue
            new_args = args
            for original, arena in substitutions:
                old = struct.pack('<I', original)
                if old not in new_args:
                    continue
                # The second word in InitializeEvent names an event; it is not a flag.
                if (bank, code) == (2000, 0) and new_args[4:8] == old:
                    new_args = new_args[:8] + new_args[8:].replace(old, struct.pack('<I', arena))
                else:
                    new_args = new_args.replace(old, struct.pack('<I', arena))
            for old, arena in extra.items():
                if old in new_args:
                    if (bank, code) not in FLAG_TESTS or new_args.find(old) != 4 or new_args.count(old) != 1:
                        raise UnsupportedRematch(f'{boss.name}: an unexpected use of a defeat flag')
                    new_args = new_args[:4] + arena + new_args[8:]
            if new_args != args:
                script.replace_instruction(event_id, position, (bank, code, args),
                                           (bank, code, new_args))

    # Their own "already happened" tests read the arena views too.
    for event_id, flag in ((defeated, arena_defeated), (first_entry, arena_entry)):
        for position, row in enumerate(script.event_instructions(event_id)):
            if _is_own_flag_test(*row):
                script.replace_instruction(event_id, position, row,
                                           (row[0], row[1], _own_flag_to(row[2], flag)))
    boss_rows = script.event_instructions(defeated)
    goto = instruction(1003, 101, 'BBBi', 0, 0, 0, arena_defeated)
    if boss_rows[0] != goto:
        raise UnsupportedRematch(f'{boss.name}: its defeat event does not start with the expected test')

    # Mark the first meeting as done in the arena view where the game's own event would be done:
    # before its closing "end if the cutscene was seen" test, else at its end. The vanilla write to
    # the first-meeting flag still happens on first play.
    entry = script.event_instructions(first_entry)
    closing = [i for i, (bank, code, args) in enumerate(entry)
               if (bank, code) == (1003, 2) and args[:4] == bytes.fromhex('00010000')
               and 9300 <= struct.unpack_from('<i', args, 4)[0] < 9400]
    if len(closing) > 1:
        raise UnsupportedRematch(f'{boss.name}: its first-meeting event ends in an unknown way')
    script.insert_instructions(first_entry, closing[0] if closing else len(entry),
                               [_set(arena_entry, True)])

    # A completed rematch must not repeat first-clear item lots or trophy/progression writes.
    # KillBoss and arena cleanup remain vanilla; the private arena flag then ends the rematch.
    boss_rows = script.event_instructions(defeated)
    kills = [i for i, (bank, code, _) in enumerate(boss_rows) if (bank, code) == (2003, 12)]
    rewards = next((i for i in range(kills[-1] + 1, len(boss_rows)) if kills
                    and boss_rows[i] == instruction(2000, 2, 'i', 0)), None)
    if rewards is None or any((bank, code) in ((2003, 4), (2003, 28)) for bank, code, _ in boss_rows[:rewards]):
        raise UnsupportedRematch(f'{boss.name}: its rewards are not where expected')
    script.insert_instructions(defeated, rewards, [
        # The original event's completion writes the defeat flag only when this event ends. Map
        # events now read the arena flag, so update it on both the first kill and a rematch kill.
        _set(arena_defeated, True),
        instruction(1003, 1, 'BBBi', 2, 0, 0, active),
        _set(active, False),
        instruction(1000, 4, 'B', 0),
    ])

    # The constructor initializes arena views before starting any original map events.
    script.insert_instructions(0, 0, [
        _set(arena_defeated, False),
        _set(arena_entry, False),
        instruction(1003, 1, 'BBBi', 4, 1, 0, active),
        instruction(1003, 1, 'BBBi', 1, 0, 0, defeated),
        _set(arena_defeated, True),
        instruction(1003, 1, 'BBBi', 1, 0, 0, first_entry),
        _set(arena_entry, True),
    ])
    script.append_initialized_event(start, [
        _await_flag_on(request),
        instruction(1003, 1, 'BBBi', 2, 1, 0, defeated),
        _set(request, False),
        instruction(1000, 4, 'B', 0),
        _set(request, False),
        _set(active, True),
        _set(arena_defeated, False),
        _set(arena_entry, False),
        instruction(3, 26, 'bBb', 1, 0, 2),  # Insight > 0
        instruction(1000, 1, 'BBb', 1, 0, 1),
        instruction(2004, 8, 'iiB', 10000, 4681, 0),  # one Insight, only if positive
        instruction(1001, 0, 'f', 1.0),
        # Reload the map at the boss lamp, so the constructor sees ACTIVE and wakes the arena.
        instruction(2003, 49, 'i', boss.respawn),
        instruction(1000, 4, 'B', 1),
    ])
    script.append_initialized_event(victory, [
        _end_if_flag_off(active),
        _await_flag_on(arena_defeated),
        _set(active, False),
    ])
    script.append_initialized_event(death, [
        _end_if_flag_off(active),
        instruction(4, 2, 'bibf', 0, 10000, 5, 0.0),  # hunter HP <= 0
        _set(arena_defeated, True),
        _set(arena_entry, True),
        _set(active, False),
    ])


def _common_events(script: Emevd, bosses) -> None:
    ids = _event_ids(script)
    for boss in bosses:
        _request, active, arena_defeated, arena_entry, *_ = boss.ids
        if _leave_event(boss) in ids:
            raise UnsupportedRematch('rematch event id already exists')
        area, block = boss.area
        script.append_initialized_event(_leave_event(boss), [
            _await_flag_on(active),
            instruction(1001, 0, 'f', 3.0),
            instruction(1003, 7, 'BBBB', 1, 0, area, block),  # outside the boss's map
            instruction(1000, 4, 'B', 1),  # still in its map: check again later
            _set(arena_defeated, True),
            _set(arena_entry, True),
            _set(active, False),
            instruction(1000, 4, 'B', 1),
        ])


def lamp_rows(bosses=BOSSES) -> dict[tuple[str, str], tuple[int, int, int]]:
    """{(map, lamp talk script): (defeat flag, request flag, menu text)} for enhanced_lamps."""
    return {(boss.map, boss.talk): (boss.defeated, boss.ids[0], message_id(boss)) for boss in bosses}


def make(dvdroot: Path, bosses=BOSSES, before=None) -> dict[Path, bytes]:
    """Return event, talk, and text assets; fail closed on any unknown game version.
    before: {map name: rewrite} - another layer's rewrite of that verified event file, which the
    rematch edits then go on top of (the two invaders' maidens)."""
    before = before or {}
    _assert_ids_available(dvdroot, bosses)
    files = {}
    by_map = {}
    for boss in bosses:
        layout = dcx_decompress((dvdroot / 'map' / 'MapStudio' / f'{boss.map}.msb.dcx').read_bytes())
        if struct.pack('<i', boss.respawn) not in layout:
            raise UnsupportedRematch(f'{boss.name}: its lamp respawn point is missing from the map')
        by_map.setdefault(boss.map, []).append(boss)
    edits = [(name, lambda script, group=group: [_boss_events(script, boss) for boss in group])
             for name, group in by_map.items()]
    edits.append(('common', lambda script: _common_events(script, bosses)))
    for name, edit in edits:
        relative = Path('event') / f'{name}.emevd.dcx'
        original = (dvdroot / relative).read_bytes()
        unpacked = dcx_decompress(original)
        if hashlib.sha256(unpacked).hexdigest() != INPUT_SHA256[name]:
            raise UnsupportedRematch(f'{relative}: not the supported CUSA03173 1.09 event file')
        if name in before:
            unpacked = before[name](unpacked)
        script = Emevd(unpacked)
        edit(script)
        result = script.to_bytes()
        if Emevd(result).to_bytes() != result:
            raise UnsupportedRematch(f'{relative}: generated event file did not round-trip')
        files[relative] = dcx_compress(result, template=original)

    # The lamps' own composition, with each boss lamp's rematch entry in its menu.
    files.update(enhanced_lamps.make(dvdroot, rematches=lamp_rows(bosses)))

    # Use the same full message rows as the PC menu layer, so either generated layer yields
    # identical message bundles if both are active. No authored game assets are distributed.
    rows = menu_assets.read_messages()
    for boss in bosses:
        if rows.get(message_id(boss), ('',))[0] != f'Rematch {boss.name}':
            raise UnsupportedRematch(f'{boss.name}: its rematch message is missing')
    message_path = Path('msg')
    languages = sorted(p.name for p in (dvdroot / message_path).iterdir()
                       if (p / menu_assets.MESSAGE_FILE).is_file())
    if not languages:
        raise UnsupportedRematch('game dump has no message languages')
    for language in languages:
        relative = message_path / language / menu_assets.MESSAGE_FILE
        files[relative] = menu_assets.build_menu_messages((dvdroot / relative).read_bytes(), rows)
    return files
