# SPDX-License-Identifier: GPL-2.0-or-later
"""Thunder Chariot's sky lightning: the Fishing Hamlet fishman priests' lightning spell (Bullet
405110-405116, "c4050 fishman B: lightning magic (combo)"), whose bolt falls from the sky onto a
point. Its effects live only in the Fishing Hamlet's effect bank (sfx/frpg_sfxbnd_m36), which the
game loads in that map alone, so elsewhere the bolt would show nothing.

common_bank() adds them to the bank every map loads (frpg_sfxbnd_commoneffects): the roots below
and everything they lead to in m36 that common does not already hold. An effect (fNNNNNNNNN.fxr)
names the effects and models it uses by number, so the closure follows every 32-bit value in a file
that is the number of an m36-only effect or model (sNNNNN.flver); a model names its textures
(sNNNNN[_x].tpf) by name. A wrong match only adds a file nobody uses; a missed one leaves part of
the bolt unseen, never more. Files keep their m36 names, contents and flags; each takes the next
free id of its kind in common (effects from 0, textures 100000, models 200000, as both banks number
them). m36's own copies are the same files, so the Fishing Hamlet is unchanged.

Bullet chain (weapon.py SKY): the spell's positioning dummy (405111), warning (405112, sfx 640505)
and bolt (405113, sfx 640506, hit 640507), each without attack; Thunderwright's lines do the
damage. Made from the player's own CUSA03173 1.09 files, as the weapon is."""
import re
import struct

import anibnd
from fromsoft import dcx_compress, dcx_decompress

COMMON = "sfx/frpg_sfxbnd_commoneffects.ffxbnd.dcx"
SOURCE = "sfx/frpg_sfxbnd_m36.ffxbnd.dcx"
# The spell's warning, bolt and bolt hit: what its bullets 405112 and 405113 show.
ROOTS = (640505, 640506, 640507)
# File id ranges by kind in both banks.
ID_BASE = {"fxr": 0, "tpf": 100000, "flver": 200000}

_FXR = re.compile(r"f(\d+)\.fxr$", re.I)
_RES = re.compile(r"s(\d+)(?:_[a-z]+)?\.(tpf|flver)$", re.I)


class SkyError(ValueError):
    pass


def _kind(name):
    m = _FXR.search(name)
    if m:
        return "fxr", int(m.group(1))
    m = _RES.search(name)
    if m:
        return m.group(2).lower(), int(m.group(1))
    return None, None


def _index(bnd):
    """{(kind, number): [entries]} of an effect bank."""
    out = {}
    for e in bnd.entries:
        kind, number = _kind(e.basename)
        if kind:
            out.setdefault((kind, number), []).append(e)
    return out


def _values(data):
    return {struct.unpack_from("<i", data, o)[0] for o in range(0, len(data) - 3, 4)}


def closure(source, common):
    """The entries of `source` the ROOTS need that `common` lacks (Bnd4Archives), in m36 order."""
    have, src = _index(common), _index(source)
    effects = {n for (k, n) in src if k == "fxr" and ("fxr", n) not in have}
    models = {n for (k, n) in src if k == "flver" and ("flver", n) not in have}
    textures = {n for (k, n) in src if k == "tpf" and ("tpf", n) not in have}
    missing = [r for r in ROOTS if ("fxr", r) not in src]
    if missing:
        raise SkyError(f"{SOURCE} has no effect {missing}")
    wanted, queue = set(), [("fxr", r) for r in ROOTS if r in effects]
    while queue:
        key = queue.pop()
        if key in wanted:
            continue
        wanted.add(key)
        kind, number = key
        for e in src[key]:
            if kind == "fxr":
                values = _values(e.data)
                queue += [("fxr", v) for v in values & effects] + [("flver", v) for v in values & models]
                queue += [("tpf", v) for v in values & textures]
            elif kind == "flver":
                names = {int(m) for m in re.findall(rb"s(\d{5})", e.data)}
                queue += [("tpf", v) for v in names & textures]
        if kind == "flver" and number in textures:
            queue.append(("tpf", number))
    return [e for e in source.entries if _kind(e.basename) in wanted]


def common_bank(common_raw, source_raw):
    """common_raw (the common effect bank, .dcx) with the sky lightning's files added."""
    common = anibnd.Bnd4Archive(dcx_decompress(common_raw))
    source = anibnd.Bnd4Archive(dcx_decompress(source_raw))
    add = closure(source, common)
    if not any(_kind(e.basename) == ("fxr", r) for e in add for r in ROOTS) and \
            not all(("fxr", r) in _index(common) for r in ROOTS):
        raise SkyError("the sky lightning's effects are neither in the bank nor added")
    next_id = {}
    for kind, base in ID_BASE.items():
        ids = [e.id for e in common.entries if base <= e.id < base + 100000]
        next_id[kind] = max(ids, default=base - 1) + 1
    for e in add:
        kind, _number = _kind(e.basename)
        common.add(anibnd.Entry(next_id[kind], e.name, e.data, e.flags, e.extra))
        next_id[kind] += 1
    return dcx_compress(common.to_bytes(), common_raw), add


def verify(common_in, common_out, source_raw):
    """Every file of the common bank unchanged, and every added one byte-identical to m36's."""
    before = anibnd.Bnd4Archive(dcx_decompress(common_in))
    after = anibnd.Bnd4Archive(dcx_decompress(common_out))
    source = {e.name: e.data for e in anibnd.Bnd4Archive(dcx_decompress(source_raw)).entries}
    old = {e.name: e.data for e in before.entries}
    for e in after.entries:
        if e.name in old:
            if old.pop(e.name) != e.data:
                raise SkyError(f"{e.basename} changed in the common bank")
        elif source.get(e.name) != e.data:
            raise SkyError(f"{e.basename} is not m36's")
    if old:
        raise SkyError(f"the common bank lost {sorted(old)[:3]}")
    names = {_kind(e.basename) for e in after.entries}
    if any(("fxr", r) not in names for r in ROOTS):
        raise SkyError("the common bank lacks the sky lightning")
