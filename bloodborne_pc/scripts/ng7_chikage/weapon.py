# SPDX-License-Identifier: GPL-2.0-or-later
"""The NG+7 Sojin Chikage: three Bloodsworn weapons, for a Bloodtinge build in an NG+7 world.

The Sojin Chikage's moves, abilities and model (behaviour variation 2030, model 1062), one weapon for
each of its three, with base physical attack times 1.2 (221 at +10 against 184, the factor NG+7 puts
on enemy health and attack over NG+1) and Bloodtinge correction 1.3 times as strong (143 at +10
against 110; Strength and Skill stay). The NG+7 hammer's factors, on this weapon's own stat. Bleed,
blood loss and the HP drain stay the Sojin Chikage's. The Bath Messengers sell each at +0 beside the
Sojin Chikage, for the same price, and it is upgraded the normal way, which opens its gem slots.

It adds rows to a gameparam that already has the Sojin Chikage, which it leaves as it is, so it is
made on top of Hunter's Arsenal's files, and the NG+7 hammer's when that is on too (enhancements.py).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(HERE) not in sys.path:
    sys.path.insert(0, os.path.dirname(HERE))   # scripts/

from sojin import weapon as sojin  # noqa: E402
from bbparam import Param, Fmg, load_paramdefs  # noqa: E402
from fromsoft import dcx_compress  # noqa: E402

# (name, first weapon id, the Sojin Chikage it is made from, sortId of its +0). 2090000 is the game's.
VARIANTS = (
    ("Bloodsworn Sojin Chikage", 2080000, 2040000, 55520),
    ("Uncanny Bloodsworn Sojin", 2100000, 2050000, 55540),
    ("Lost Bloodsworn Sojin", 2110000, 2030000, 55560),
)
LEVELS = sojin.LEVELS
PHYSICAL_SCALE = 1.2                    # of the Chikage's: 110 at +0, 221 at +10
BLOODTINGE_SCALE = 1.3                  # of the Chikage's: 78 at +0, 143 at +10
LORE = ("A Sojin Chikage bound again in the blood of the royal guard who bore it, cycle upon cycle, "
        "until blade and oath could no longer be told apart.\n\n"
        "It answers the thickest Vileblood above all others.")
WEAPON_IDS = [first + 100 * level for _n, first, _s, _o in VARIANTS for level in LEVELS]
GAMEPARAM = sojin.GAMEPARAM
TALK = sojin.TALK
PRICE = sojin.PRICE
set_game = sojin.set_game
PARAMS = sojin.PARAMS[:3]               # the weapon, its gem slots and the shop


class Ng7ChikageError(ValueError):
    pass


def physical(value):
    return int(value * PHYSICAL_SCALE + 0.5)


def bloodtinge(value):
    return int(value * BLOODTINGE_SCALE + 0.5)


def _fields(w, first, source, sort, level):
    """A level's fields over its Sojin Chikage's row of that level."""
    row = source + 100 * level
    return {"attackBasePhysics": physical(w.get(row, "attackBasePhysics")),
            "correctMagic": bloodtinge(w.get(row, "correctMagic")),   # Bloodtinge, in the game's params
            "sortId": sort + level, "originEquipWep": first + max(level - 1, 0) * 100}


def _params(gp):
    defs = load_paramdefs()
    return [Param(gp.files[gp.index(name)], defs[st]) for name, st in PARAMS]


def has_weapon(param_raw):
    rows = _params(sojin._open(param_raw))[0].rows
    return any(r in rows for r in WEAPON_IDS)


def add_params(param_raw, talk_raw):
    """`param_raw` (a gameparam.parambnd.dcx with the Sojin Chikage) with the three weapons' levels
    and their shop rows added, in the ranges `talk_raw` opens."""
    if not sojin.has_weapon(param_raw):
        raise Ng7ChikageError("it needs the Sojin Chikage, from Hunter's Arsenal")
    gp = sojin._open(param_raw)
    w, g, s = _params(gp)
    sorts = {w.get(r, "sortId") for r in w.rows}
    if any(r in w.rows or r in g.rows for r in WEAPON_IDS) or \
            any(sort + level in sorts for _n, _f, _s, sort in VARIANTS for level in LEVELS):
        raise Ng7ChikageError("its weapon ids or sort ids are taken")
    for name, first, source, sort in VARIANTS:
        for level in LEVELS:
            new, row = first + 100 * level, source + 100 * level
            w.add(new, row, sojin.label(name, level))
            for field, value in _fields(w, first, source, sort, level).items():
                w.set(new, field, value)
            g.add(new, row, sojin.label(name, level))    # that Sojin Chikage's gem slots
            g.set(new, "wepParamId", new)
    sojin._add_shop_rows(s, sojin.shop_ranges(talk_raw), VARIANTS)
    for (name, _st), param in zip(PARAMS, (w, g, s)):
        gp.files[gp.index(name)] = param.to_bytes()
    return dcx_compress(gp.to_bytes(), param_raw)


def add_text(msg_raw):
    """`msg_raw` (an item.msgbnd.dcx) with the weapons' names and lore (English in every language)."""
    msg = sojin._open(msg_raw)
    ni, li = msg.index("武器名.fmg"), msg.index("武器うんちく.fmg")
    names, lore = Fmg(msg.files[ni]), Fmg(msg.files[li])
    for name, first, _source, _sort in VARIANTS:
        for level in LEVELS:
            names.entries[first + 100 * level] = sojin.label(name, level)
            lore.entries[first + 100 * level] = LORE
    msg.files[ni], msg.files[li] = names.to_bytes(), lore.to_bytes()
    return dcx_compress(msg.to_bytes(), msg_raw)


def verify(param_in, param_out):
    """Reads the made gameparam back: every other file and row is unchanged, the Sojin Chikage's among
    them, and the new rows are their sources with only the planned fields changed."""
    before, after = sojin._open(param_in), sojin._open(param_out)
    ours = {name for name, _st in PARAMS}
    for name in before.names:
        if not any(name.endswith(n) for n in ours) and before.files[before.index(name)] != after.files[after.index(name)]:
            raise Ng7ChikageError(f"{name} changed")
    (w0, g0, s0), (w, g, s) = _params(before), _params(after)
    for p0, p1 in ((w0, w), (g0, g), (s0, s)):
        if [r for r in p0.rows if p0.rows[r] != p1.rows.get(r)]:
            raise Ng7ChikageError("original rows changed")
    if set(w.rows) - set(w0.rows) != set(WEAPON_IDS) or set(g.rows) - set(g0.rows) != set(WEAPON_IDS):
        raise Ng7ChikageError("the new weapon rows are not its levels")
    sold = {s.get(r, "equipId"): s.get(r, "value") for r in s.rows if r not in s0.rows}
    for name, first, source, sort in VARIANTS:
        for level in LEVELS:
            new, row, want = first + 100 * level, source + 100 * level, _fields(w, first, source, sort, level)
            changed = {f[0] for f in w.fields if w.get(new, f[0]) != w.get(row, f[0])}
            if changed - set(want) or any(w.get(new, f) != v for f, v in want.items()):
                raise Ng7ChikageError(f"{sojin.label(name, level)} is not its Sojin Chikage's row with its planned fields")
            if g.get(new, "wepParamId") != new:
                raise Ng7ChikageError(f"{sojin.label(name, level)}'s gem row names another weapon")
        if sold.get(first) != PRICE:
            raise Ng7ChikageError(f"the shop does not sell {name} at +0 for {PRICE}")
    if set(sold) != {first for _n, first, _s, _o in VARIANTS}:
        raise Ng7ChikageError("the shop's new rows are not the three weapons at +0")


def make(dvdroot, param_raw, msgs):
    """{game path: bytes}: the gameparam and item texts given (Hunter's Arsenal's, or the NG+7
    hammer's on top of those) with the weapons."""
    set_game(dvdroot)
    files = {GAMEPARAM: add_params(param_raw, sojin._game(TALK))}
    verify(param_raw, files[GAMEPARAM])
    for lang, raw in msgs.items():
        files[f"msg/{lang}/item.msgbnd.dcx"] = add_text(raw)
    return files
