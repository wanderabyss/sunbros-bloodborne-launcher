# SPDX-License-Identifier: GPL-2.0-or-later
"""Sojin Chikage abilities, TAE side: insert the ability events into the combined moveset a157.tae.

    new_bytes = add_ability_events(tae_bytes)        # tae_bytes = combine_moveset.build_combined(157)[0]

Inserts exactly the events of abilities.TAE_EVENTS (abilities-notes.md section 3):
  * 41100 (trick R2 finisher, attack judge 510): type 318 (12130, 0, 591, 0), frames 19-20
    -> behaviour 102030591, Blood Crescent.
  * 33300 (judge 395) and 33310 (judge 390), the transform attacks into trick mode:
    10 x type 66 (2030110 .. 2030119) frames 14-15 (HP cost bands, highest first),
    3 x type 401 (2030100, 2030101, 2030103) frames 15-18 (20 s buffs),
    type 318 (9, 0, 396, 0) frames 16-17 (shockwave), and the two FFX type 96
    (252060, 220, 0) frames 16-31 and (7119, 12130, 0) frames 17-32.
Each new event is appended to the animation's event list and gets an event group of its own, as
the game does for these types (every 318 event in the game sits in a group of type 2; 66 / 96 /
401 events sit in groups of their own type, one event per group in Blade of Mercy's animations).
The new group goes after the last group of the same type (a bullet group after the attack group,
as in a143 42620), else at the end. Original events and groups are not touched. A time already
in the animation's time table is reused (exact float), otherwise frame/30 is added.

Uses tae_write.py's reader/writer as it is. Self-test (read-only, nothing written):
    python ability_events.py
proves (1) the result re-reads with tae.py and tae_write.py, (2) every original event of every
animation is unchanged, (3) only the listed events were added, with the right frames and params,
(4) an unmodified round trip of a157.tae through this code is byte-identical.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tae_write as tw  # noqa: E402
import abilities  # noqa: E402

FPS = 30.0
# Every type-318 (bullet) event in the game is in an event group of type 2; the other ability
# event types sit in groups of their own type.
GROUP_TYPE = {318: 2, 66: 66, 67: 67, 96: 96, 401: 401}
# Attack judge each target animation must carry (a157 copies these from a113).
EXPECT_JUDGE = {41100: 510, 33300: 395, 33310: 390}
ATTACK_EVENT = 1


class AbilityEventError(ValueError):
    pass


def specs(events=None):
    """The events to insert, one per (animation, event): dicts with anim, type, group_type,
    frames, params (16 bytes), label. events defaults to abilities.TAE_EVENTS."""
    out = []
    for e in abilities.TAE_EVENTS if events is None else events:
        if GROUP_TYPE.get(e["type"]) != e["group_type"]:
            raise AbilityEventError(f"event type {e['type']}: group type {e['group_type']} is not the game's")
        for aid in e["anims"]:
            out.append({"anim": aid, "type": e["type"], "group_type": e["group_type"],
                        "frames": tuple(e["frames"]), "params": struct.pack("<4i", *e["params_ints"]),
                        "label": e["ability"]})
    return out


def _f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def _time(anim, frame):
    """frame/30 as stored: the exact value already in the animation's time table if there is one."""
    want = frame / FPS
    known = list(anim.times or []) + [x for e in anim.events for x in (e.start, e.end)]
    near = [x for x in known if abs(x - want) < 1e-4]
    return near[0] if near else _f32(want)


def _group_position(anim, gtype):
    same = [i for i, g in enumerate(anim.groups) if g.type == gtype]
    if same:
        return same[-1] + 1
    if gtype == 2:
        attack = [i for i, g in enumerate(anim.groups) if g.type == 1]
        if attack:
            return attack[-1] + 1
    return len(anim.groups)


def _attack_judges(anim):
    return [e.ints(3)[2] for e in anim.events if e.type == ATTACK_EVENT]


def insert(t, items):
    """Insert spec items into a tae_write.TaeFile in place; returns [(anim id, event index)]."""
    added = []
    for s in items:
        a = t.anim(s["anim"])
        judge = EXPECT_JUDGE.get(s["anim"])
        if judge is not None and judge not in _attack_judges(a):
            raise AbilityEventError(f"anim {s['anim']}: no attack event with judge {judge} "
                                    f"(has {_attack_judges(a)}): not the expected animation")
        if any(e.type == s["type"] and e.params[:16] == s["params"] for e in a.events):
            raise AbilityEventError(f"anim {s['anim']}: event type {s['type']} {s['params'].hex()} already there")
        start, end = (_time(a, f) for f in s["frames"])
        a.events.append(tw.Event(start, end, s["type"], 0, s["params"]))
        idx = len(a.events) - 1
        a.groups.insert(_group_position(a, s["group_type"]), tw.EventGroup(s["group_type"], [idx]))
        added.append((s["anim"], idx))
    return added


def add_ability_events(tae_bytes, events=None):
    """Return tae_bytes with the ability events inserted (events=() inserts nothing)."""
    t = tw.read(tae_bytes)
    items = specs(events)
    if not items:
        return t.to_bytes()
    insert(t, items)
    return t.to_bytes()


# --- proof --------------------------------------------------------------------------------------

def _same_params(a, b):
    """Equal up to the trailing zero padding the writer adds or drops when an event's data moves
    between 16-byte alignments (moveset-notes.md: at most 8 bytes)."""
    n = max(len(a), len(b))
    return abs(len(a) - len(b)) in (0, 8) and a.ljust(n, b"\0") == b.ljust(n, b"\0")


def _bits(x):
    return struct.pack("<f", x)


def verify(original, new, events=None):
    """Assert proofs (1)-(3) for new = add_ability_events(original, events). Returns a summary."""
    from tae import Tae
    items = specs(events)
    # (1) both readers accept the result; the writer reproduces it exactly.
    old_t, new_t = tw.read(original), tw.read(new)
    assert new_t.to_bytes() == new, "tae_write does not reproduce the new file"
    old_v, new_v = Tae(original), Tae(new)
    assert new_t.id == old_t.id and [a.id for a in new_v.anims] == new_t.ids() == old_t.ids()
    for a_tw, a_v in zip(new_t.animations, new_v.anims):
        assert a_v.id == a_tw.id and len(a_v.events) == len(a_tw.events)
        for x, y in zip(a_tw.events, a_v.events):
            assert (x.type, _bits(x.start), _bits(x.end)) == (y.type, _bits(y.start), _bits(y.end))
            assert y.raw[:min(16, len(x.params))] == x.params[:16], (a_tw.id, x)
    # (2) every original event and group of every animation is unchanged.
    want = {}
    for s in items:
        want.setdefault(s["anim"], []).append(s)
    total = 0
    for a0, a1 in zip(old_t.animations, new_t.animations):
        assert a0.id == a1.id and repr(a0.mini) == repr(a1.mini) and bytes(a0.mini.data) == bytes(a1.mini.data)
        n0 = len(a0.events)
        for i, (x, y) in enumerate(zip(a0.events, a1.events[:n0])):
            assert (x.type, x.unk, _bits(x.start), _bits(x.end)) == (y.type, y.unk, _bits(y.start), _bits(y.end)), (a0.id, i)
            assert _same_params(x.params, y.params), (a0.id, i, x.params.hex(), y.params.hex())
        old_groups = [(g.type, g.extra, g.tail, g.indices) for g in a0.groups]
        new_groups = [(g.type, g.extra, g.tail, g.indices) for g in a1.groups]
        it = iter(new_groups)
        assert all(any(g == h for h in it) for g in old_groups), f"anim {a0.id}: an original group changed or moved out of order"
        # (3) only the listed events were added, in order, each in a new group of its own.
        added = a1.events[n0:]
        exp = want.get(a0.id, [])
        assert len(added) == len(exp), (a0.id, len(added), len(exp))
        assert len(a1.groups) - len(a0.groups) == len(exp)
        new_only = [g for g in a1.groups if (g.type, g.extra, g.tail, g.indices) not in old_groups]
        for k, (e, s) in enumerate(zip(added, exp)):
            idx = n0 + k
            assert e.type == s["type"] and e.unk == 0, (a0.id, e)
            assert e.params[:16] == s["params"] and not any(e.params[16:]), (a0.id, e.params.hex())
            for value, frame in zip((e.start, e.end), s["frames"]):
                assert abs(value - frame / FPS) < 1e-4, (a0.id, e, s["frames"])
            groups = [g for g in a1.groups if idx in g.indices]
            assert len(groups) == 1 and groups[0].indices == [idx] and groups[0].type == s["group_type"], (a0.id, idx)
            assert groups[0] in new_only
        # The game's invariant: every event is in exactly one group.
        members = sorted(i for g in a1.groups for i in g.indices)
        assert members == list(range(len(a1.events))), f"anim {a0.id}: events not each in exactly one group"
        total += len(added)
    assert total == len(items)
    return {a: len(v) for a, v in sorted(want.items())}, total


def self_test():
    import combine_moveset as cm
    original, judges = cm.build_combined(157)
    built = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "Sojin Chikage", "dvdroot_ps4", "chr",
                         "c0000.anibnd.dcx")
    if os.path.exists(built):  # read only: the mod's current anibnd should hold the same a157.tae
        from bbparam import open_bnd
        _, bnd = open_bnd(built)
        names = [n.split("\\")[-1] for n in bnd.names]
        if "a157.tae" in names:
            # build.py inserts the ability events, so the built moveset is the combined one with them.
            assert bnd.files[names.index("a157.tae")] == add_ability_events(original), \
                "built a157.tae differs from add_ability_events(build_combined(157))"
            print("built anibnd's a157.tae == add_ability_events(build_combined(157))")
    # The judges the new events name exist in the combined moveset's variation (or are the abilities').
    assert 510 in judges and 390 in judges and 395 in judges
    assert abilities.CRESCENT_JUDGE not in judges and abilities.WAVE_JUDGE not in judges
    # (4) unmodified round trip through this code is byte-identical.
    assert tw.read(original).to_bytes() == original
    assert add_ability_events(original, events=()) == original
    # (1)-(3)
    new = add_ability_events(original)
    per_anim, total = verify(original, new)
    # Inserting twice is refused.
    try:
        add_ability_events(new)
        raise AssertionError("second insertion should fail")
    except AbilityEventError:
        pass
    # The ids the events name are the abilities' rows.
    rows = abilities.ability_rows()
    for s in specs():
        ints = struct.unpack("<4i", s["params"])
        if s["type"] in (66, 67, 401):
            assert ints[0] in rows["SpEffectParam"], s
        if s["type"] == 318:
            assert 100000000 + abilities.VAR * 1000 + ints[2] in rows["BehaviorParam_PC"], s
    t0, t1 = tw.read(original), tw.read(new)
    print(f"a157.tae {len(original)} -> {len(new)} bytes; added {total} events: {per_anim}")
    for aid in sorted(per_anim):
        a0, a1 = t0.anim(aid), t1.anim(aid)
        print(f"  {aid}: events {len(a0.events)} -> {len(a1.events)}, groups {len(a0.groups)} -> {len(a1.groups)}, "
              f"times {len(a0.times)} -> {len(a1.times)}")
        for e in a1.events[len(a0.events):]:
            g = next(g for g in a1.groups if a1.events.index(e) in g.indices)
            print(f"    type {e.type:3} group {g.type:3}  {e.start:.4f}-{e.end:.4f}  {struct.unpack('<4i', e.params[:16])}")
    print("ok: (1) re-reads with tae.py and tae_write.py, (2) original events/groups unchanged, "
          "(3) only the listed events added, (4) unmodified round trip byte-identical")


if __name__ == "__main__":
    self_test()
