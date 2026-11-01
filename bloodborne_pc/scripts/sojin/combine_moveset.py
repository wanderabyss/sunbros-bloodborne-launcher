# SPDX-License-Identifier: GPL-2.0-or-later
"""Sojin Chikage phase 2: one TAE that plays Chikage's moves in normal mode and Blade of Mercy's
in trick mode.

    data, judges = build_combined(157)

Animations (ids as in every weapon TAE: 30000-39999 normal mode, 40000+ trick mode):
  * normal mode 30000-34999 except 33300/33310       <- a114 (Chikage, behaviour variation 200)
  * trick mode 40000+ except 43300/43310             <- a113 (Blade of Mercy, variation 400)
  * 33300/33310 (transform attacks into trick mode)  <- a113
  * 43300/43310 (transform attacks back to normal)   <- a114
Each animation keeps all of its source's events (sounds, effects, timing, cancel windows);
only the behaviour judge of its attack events (type 1, third int) is renumbered where two
sources use the same judge for different attack rows. The new TAE has no HKX of its own: an
animation the source plays from its own HKX becomes a "standard" entry that imports that HKX
(flags byte 1 = 1, import id TTT*1000000+AAAAAA, name aTTT_AAAAAA.hkt), exactly as the game's
Rakuyo (a144) uses Chikage's a114 HKX; an animation that imports another animation of its own
TAE now imports that animation of the new TAE (as a144 does), so the remapped events are used.

judges = {judge: (source_variation, source_judge)}: behaviour row 100000000 + VAR*1000 + judge
of the new variation must copy row 100000000 + source_variation*1000 + source_judge (and its
attack row). build.py builds variation 2030 from it.

Usage: python combine_moveset.py [NNN]   (default 157) builds aNNN.tae, validates it, adds it to
a copy of c0000.anibnd in a temporary folder and reads it back; prints the judge table, the
left-out animations and which animations the behaviour graph has no clip for under aNNN.
Nothing is written outside the temporary folder.
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tae_write as tw  # noqa: E402
import anibnd  # noqa: E402

MERCY_TAE, MERCY_VAR = 113, 400
CHIKAGE_TAE, CHIKAGE_VAR = 114, 200
TRANSFORM_TO_TRICK = (33300, 33310)
TRANSFORM_TO_NORMAL = (43300, 43310)
ATTACK_EVENT = 1
# Event types that would also name a behaviour judge (bullet / common behaviours). None
# occurs in a113 or a114; the build refuses to guess if a source ever has one.
OTHER_BEHAVIOUR_EVENTS = (2, 5, 304)
# Chikage's transform-back attacks (judges 390/395 in its table) clash with Blade of Mercy's
# transform-into-trick attacks (also 390/395). They take 795/790, the numbers Blade of Mercy
# itself uses for 43300/43310, which nothing else in the combined moveset uses; build.py
# already treats 790/795 as "transform back to normal".
PREFERRED = {(CHIKAGE_VAR, 390): 795, (CHIKAGE_VAR, 395): 790}


class CombineError(ValueError):
    pass


def full_id(tae_number, anim_id):
    return tae_number * 1000000 + anim_id


def load_taes():
    return {int(n[1:].split(".")[0]): tw.read(d) for n, d in tw.game_taes().items()}


def plan(normal, trick, into_trick=None, to_normal=None):
    """[(anim id, source TAE)] for the combined moveset; TaeFile objects in."""
    into_trick = into_trick or trick
    to_normal = to_normal or normal
    out = {}
    for a in normal.animations:
        if 30000 <= a.id < 35000 and a.id not in TRANSFORM_TO_TRICK:
            out[a.id] = normal
    for a in trick.animations:
        if a.id >= 40000 and a.id not in TRANSFORM_TO_NORMAL:
            out[a.id] = trick
    for aid in TRANSFORM_TO_TRICK:
        out[aid] = into_trick
    for aid in TRANSFORM_TO_NORMAL:
        out[aid] = to_normal
    return sorted(out.items())


def _attack_judges(anim):
    return [e.ints(3)[2] for e in anim.events if e.type == ATTACK_EVENT]


def build_combined(new_tae_id=157, normal_tae=CHIKAGE_TAE, normal_var=CHIKAGE_VAR,
                   trick_tae=MERCY_TAE, trick_var=MERCY_VAR, preferred=None, taes=None,
                   report=None):
    """Bytes of the combined TAE aNNN.tae (NNN = new_tae_id; its internal id is 2000+NNN) and
    {judge: (source variation, source judge)}. `report` (a dict, optional) receives the plan,
    the renumbered judges, the HKX/import rewrites and the source animations left out."""
    if new_tae_id >= 2000:
        new_tae_id -= 2000
    taes = taes or load_taes()
    normal, trick = taes[normal_tae], taes[trick_tae]
    var_of = {normal_tae: normal_var, trick_tae: trick_var}
    tae_of = {id(normal): normal_tae, id(trick): trick_tae}
    preferred = dict(PREFERRED if preferred is None else preferred)
    placed = plan(normal, trick)
    src_of = {aid: tae_of[id(t)] for aid, t in placed}

    # Every (variation, judge) the placed animations attack with, in placement order, plus the
    # attacks of any animation they import from a source TAE that is not placed from there.
    def attacks_of(src, anim):
        for e in anim.events:
            if e.type in OTHER_BEHAVIOUR_EVENTS:
                raise CombineError(f"a{src} {anim.id}: event type {e.type} names a behaviour; not handled")
        return [(var_of[src], j) for j in _attack_judges(anim)]

    external = []
    wanted = []
    for aid, t in placed:
        src = tae_of[id(t)]
        a = t.anim(aid)
        wanted += attacks_of(src, a)
        m = a.mini
        if m.type == 1:
            itae, iaid = divmod(m.import_id, 1000000)
            if itae in var_of and src_of.get(iaid) != itae:
                # Imported events come from the source TAE itself (not renumbered).
                external.append((aid, m.import_id))
                wanted += attacks_of(itae, taes[itae].anim(iaid))

    # Judge numbers: keep each source judge's number unless another source row already took
    # it; then the preferred number, else the first free one in the same block of ten, else
    # the first free one from 0.
    taken = {}           # new judge -> (var, judge)
    remap = {}           # (var, judge) -> new judge
    keep_first = [k for k in dict.fromkeys(wanted) if k not in preferred]
    for k in keep_first:
        if k[1] not in taken:
            taken[k[1]] = k
            remap[k] = k[1]
    used_numbers = {j for _, j in wanted}
    for k in dict.fromkeys(wanted):
        if k in remap:
            continue
        candidates = [preferred[k]] if k in preferred else []
        base = k[1] - k[1] % 10
        candidates += list(range(base, base + 10)) + list(range(0, 1000))
        for c in candidates:
            # A renumbered judge must not reuse any number a source attack has in this
            # moveset, even one renumbered away (keeps the dict unambiguous to read).
            if c not in taken and (c not in used_numbers or c == k[1]):
                taken[c] = k
                remap[k] = c
                break
        else:
            raise CombineError("no free behaviour judge number")
    if any(k != (k[0], v) for k, v in remap.items()) and external:
        moved = [x for x in external if any(remap[(var_of[x[1] // 1000000], j)] != j
                                            for j in _attack_judges(taes[x[1] // 1000000].anim(x[1] % 1000000)))]
        if moved:
            raise CombineError(f"imported animations {moved} would need renumbered judges")

    out = tw.TaeFile(2000 + new_tae_id, [], normal.skeleton, normal.sib, normal.event_bank,
                     normal.flags, normal.unk48)
    rewrites = []
    for aid, t in placed:
        src = tae_of[id(t)]
        a = t.anim(aid).copy()
        var = var_of[src]
        for e in a.events:
            if e.type == ATTACK_EVENT:
                j = e.ints(3)[2]
                if remap[(var, j)] != j:
                    e.set_int(2, remap[(var, j)])
        m = a.mini
        if m.type == 0 and m.import_hkx_id == -1:
            fl = bytearray(m.flags)
            fl[1] = 1
            m.flags = bytes(fl)
            m.import_hkx_id = full_id(src, aid)
            name = f"a{src:03d}_{aid:06d}.hkt"
            if m.name not in (None, name):
                raise CombineError(f"a{src} {aid}: unexpected hkt name {m.name}")
            m.name, m.name_ptr = name, True
            rewrites.append((aid, f"own HKX of a{src} -> imports HKX {m.import_hkx_id}"))
        elif m.type == 1:
            itae, iaid = divmod(m.import_id, 1000000)
            if itae == src and src_of.get(iaid) == src:
                m.import_id = full_id(new_tae_id, iaid)
                rewrites.append((aid, f"import {full_id(itae, iaid)} -> {m.import_id} (same animation, new TAE)"))
            else:
                rewrites.append((aid, f"import {m.import_id} kept"))
        else:
            rewrites.append((aid, f"imports HKX {m.import_hkx_id} kept"))
        out.animations.append(a)
    data = out.to_bytes()
    judges = {new: k for new, k in sorted(taken.items())}
    if report is not None:
        report.update(plan=[(aid, tae_of[id(t)]) for aid, t in placed],
                      renumbered={k: v for k, v in remap.items() if k[1] != v},
                      rewrites=rewrites, external_imports=external,
                      left_out=left_out(normal, trick, normal_tae, trick_tae))
    validate(data, judges, new_tae_id, taes, normal_tae, trick_tae, var_of, remap)
    return data, judges


def left_out(normal, trick, normal_tae=CHIKAGE_TAE, trick_tae=MERCY_TAE):
    """Source animations with no place in the combined moveset (their id is taken from the
    other source, or that mode's source has no such animation)."""
    ids = {aid for aid, _ in plan(normal, trick)}
    out = []
    for tae_n, t in ((normal_tae, normal), (trick_tae, trick)):
        for a in t.animations:
            if a.id not in ids:
                out.append((tae_n, a.id, _attack_judges(a)))
    return out


def validate(data, judges, new_tae_id, taes, normal_tae, trick_tae, var_of, remap):
    """Re-read the result with tae.py (the independent reader) and tae_write, and check it."""
    from tae import Tae
    t1 = Tae(data)
    t2 = tw.read(data)
    if t1.id != 2000 + new_tae_id or t2.id != t1.id:
        raise CombineError("TAE id")
    if tw.read(data).to_bytes() != data:
        raise CombineError("result does not round-trip")
    src_of = dict(plan(taes[normal_tae], taes[trick_tae]))
    tae_of = {id(taes[normal_tae]): normal_tae, id(taes[trick_tae]): trick_tae}
    if [a.id for a in t1.anims] != sorted(src_of):
        raise CombineError("animation list")
    for a1, a2 in zip(t1.anims, t2.animations):
        src = tae_of[id(src_of[a1.id])]
        s = taes[src].anim(a1.id)
        if len(a1.events) != len(s.events) or len(a2.groups) != len(s.groups):
            raise CombineError(f"{a1.id}: event count")
        for e1, e2, se in zip(a1.events, a2.events, s.events):
            if (e1.type, e1.start, e1.end) != (se.type, se.start, se.end):
                raise CombineError(f"{a1.id}: event changed")
            p = bytearray(se.params)
            if se.type == ATTACK_EVENT:
                j = se.ints(3)[2]
                new = e1.ints(3)[2]
                if judges.get(new) != (var_of[src], j) or remap[(var_of[src], j)] != new:
                    raise CombineError(f"{a1.id}: attack {new} not in the judge table as ({var_of[src]}, {j})")
                struct.pack_into("<i", p, 8, new)
            # Parameters equal the source's (apart from the renumbered judge); a block may
            # carry 8 more padding zeros where its alignment changed.
            if e2.params.rstrip(b"\0") != bytes(p).rstrip(b"\0") or not e2.params.startswith(bytes(p).rstrip(b"\0")):
                raise CombineError(f"{a1.id}: event parameters changed")
        if [(g.type, g.indices) for g in a2.groups] != [(g.type, g.indices) for g in s.groups]:
            raise CombineError(f"{a1.id}: event groups changed")
        m = a2.mini
        if m.type == 0 and not (m.flags[1] == 1 and m.import_hkx_id // 1000000 in (normal_tae, trick_tae)
                                or s.mini.import_hkx_id != -1):
            raise CombineError(f"{a1.id}: plays no source HKX")
        if a1.mini_type != m.type:
            raise CombineError(f"{a1.id}: tae.py and tae_write disagree")
    attacks = {e.ints(3)[2] for a in t1.anims for e in a.events if e.type == ATTACK_EVENT}
    if attacks - set(judges):
        raise CombineError(f"attack judges without a source row: {sorted(attacks - set(judges))}")
    if len(set(judges.values())) != len(judges):
        raise CombineError("two judges copy the same source row")
    return True


def check_params(judges):
    """Every source row of the judge table must exist in the game's BehaviorParam_PC (else the
    game would fall back to another row there too). Returns the missing ones."""
    from bbparam import GAME, open_bnd, load_paramdefs, Param
    defs = load_paramdefs()
    _, gp = open_bnd(GAME + "param/gameparam/gameparam.parambnd.dcx")
    b = Param(gp.files[gp.index("BehaviorParam_PC.param")], defs["BEHAVIOR_PARAM_ST"])
    return [(j, src) for j, src in judges.items() if 100000000 + src[0] * 1000 + src[1] not in b.rows]


def registered_clips(tae_number):
    """Animation ids the player's behaviour graph (Behaviors/c0000.hkx in c0000.anibnd) has a
    clip generator for under TAE number `tae_number` (names aTTT_AAAAAA). A weapon category's
    animation only plays if its CustomManualSelectorGenerator lists such a clip."""
    _, bnd = anibnd.load(anibnd.GAME + "chr/c0000.anibnd.dcx")
    beh = bnd.find(id=7000500).data
    return {int(a) for t, a in re.findall(rb"a(\d{3})_(\d{6})(?![\d_])", beh) if int(t) == tae_number}


def missing_hkx(data):
    """HKX the TAE's standard entries play (own or imported) that no c0000_*.anibnd.dcx has
    (file id 1000000000 + TTT*1000000 + AAAAAA). Empty = nothing to copy."""
    t = tw.read(data)
    need = {}
    for a in t.animations:
        if a.mini.type == 0:
            src = a.mini.import_hkx_id if a.mini.import_hkx_id != -1 else full_id(t.id - 2000, a.id)
            need[anibnd.HKX_FILE_ID + src] = a.id
    have = set()
    for f in os.listdir(anibnd.GAME + "chr"):
        if f.startswith("c0000_") and f.endswith(".anibnd.dcx"):
            have.update(e.id for e in anibnd.load(anibnd.GAME + "chr/" + f)[1].entries)
    return sorted((aid, fid - anibnd.HKX_FILE_ID) for fid, aid in need.items() if fid not in have)


if __name__ == "__main__":
    import tempfile
    new = int(sys.argv[1]) if len(sys.argv) > 1 else 157
    rep = {}
    data, judges = build_combined(new, report=rep)
    print(f"a{new}.tae: {len(data)} bytes, {len(rep['plan'])} animations "
          f"({sum(1 for _, s in rep['plan'] if s == CHIKAGE_TAE)} from a114, "
          f"{sum(1 for _, s in rep['plan'] if s == MERCY_TAE)} from a113)")
    print("renumbered judges:", {f"{k[0]}:{k[1]}": v for k, v in rep["renumbered"].items()})
    print("judge table:", judges)
    print("source rows missing in BehaviorParam_PC:", check_params(judges))
    print("imports of source animations kept as such:", rep["external_imports"])
    print("left out:", rep["left_out"])
    for aid, how in rep["rewrites"]:
        if "kept" in how or "new TAE" in how:
            print("  ", aid, how)
    clips = registered_clips(new)
    missing = [aid for aid, _ in rep["plan"] if aid not in clips]
    print(f"behaviour clips registered for a{new}: {len(clips)}; combined animations without one: {missing}")
    print("HKX played by the new TAE that no c0000_*.anibnd has:", missing_hkx(data))
    _, bnd = anibnd.load(anibnd.GAME + "chr/c0000.anibnd.dcx")
    anibnd.add_tae(bnd, new, data)
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "c0000.anibnd.dcx")
        anibnd.save(bnd, p, open(anibnd.GAME + "chr/c0000.anibnd.dcx", "rb").read())
        _, back = anibnd.load(p)
        print(f"c0000.anibnd with a{new}.tae: {len(back.entries)} files, a{new}.tae read back equal:",
              back.find(f"a{new}.tae").data == data)
    print("ok")
