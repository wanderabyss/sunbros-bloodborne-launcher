# SPDX-License-Identifier: GPL-2.0-or-later
"""The NG+7 hammer: the Stormforged Kirkhammer, for a 99 Arcane build in an NG+7 world.

Thunderwright's Kirkhammer's moves, lightning, effects and model (behaviour variation 2060, model
1032) on the Kirkhammer's rows, with its base attack times 1.2 (180 physical + 132 bolt at +10 against
150 + 110, the factor NG+7 puts on enemy health and attack over NG+1) and Arcane correction 1.3 times
as strong (130 at +10; Strength stays 100). It needs what Thunderwright's Kirkhammer needs. The Bath
Messengers sell it at +0 beside that weapon, for the same price, and it is upgraded the normal way.
There are three, as that weapon has: each has its Kirkhammer's gem slots, which is all that differs.

It has to be upgraded: a character's save holds each weapon's open gem slots, and a weapon obtained
directly at +10 has them closed, whatever its WeaponGenParam row says.

It adds rows to a gameparam that already has Thunderwright's Kirkhammer, which it leaves as it is, so
it is made on top of Hunter's Arsenal's files (enhancements.py).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(HERE) not in sys.path:
    sys.path.insert(0, os.path.dirname(HERE))   # scripts/

from thunderwright import weapon as thunderwright  # noqa: E402
from bbparam import Param, Fmg, load_paramdefs  # noqa: E402
from fromsoft import dcx_compress  # noqa: E402

# (name, first weapon id, the Kirkhammer it takes stats and gem slots from, sortId of its +0)
VARIANTS = (
    ("Stormforged Kirkhammer", 2070000, 8000000, 55480),
    ("Uncanny Stormforged Hammer", 2140000, 8010000, 55640),
    ("Lost Stormforged Hammer", 2150000, 8020000, 55660),
)
LEVELS = thunderwright.LEVELS
BOLT_BASE, BOLT_STEP = 66, 6.6          # 66 at +0, 132 at +10
PHYSICAL_SCALE = 180 / 210              # of the Kirkhammer's: 90 at +0, 180 at +10
ARCANE_SCALE = 1.3                      # of the Kirkhammer's Strength correction: 78 at +0, 130 at +10
LORE = ("A Thunderwright's Kirkhammer left upon the crag for a second winter, until the stone would "
        "take no more of the storm.\n\n"
        "It answers the faithful of the old hymns above all others.")
WEAPON_IDS = [first + 100 * level for _n, first, _s, _o in VARIANTS for level in LEVELS]
GAMEPARAM = thunderwright.GAMEPARAM
TALK = thunderwright.TALK
set_game = thunderwright.set_game
PARAMS = (("EquipParamWeapon.param", "EQUIP_PARAM_WEAPON_ST"), ("WeaponGenParam.param", "WEAPON_GEN_PARAM_ST"),
          ("ShopLineupParam.param", "SHOP_LINEUP_PARAM"))


class Ng7HammerError(ValueError):
    pass


def label(name, level):
    return name + (f" +{level}" if level else "")


def physical(kirk_physical):
    return int(kirk_physical * PHYSICAL_SCALE + 0.5)


def bolt(level):
    return int(BOLT_BASE + BOLT_STEP * level + 0.5)


def arcane_scaling(kirk_strength):
    return int(kirk_strength * ARCANE_SCALE + 0.5)


def _fields(w, first, source, sort, level):
    """A level's fields over its Kirkhammer's row of that level."""
    t, row = thunderwright, source + 100 * level
    return {"equipModelId": t.MODEL, "behaviorVariationId": t.VAR,
            "attackBasePhysics": physical(w.get(row, "attackBasePhysics")), "attackBaseThunder": bolt(level),
            "correctFaith": arcane_scaling(w.get(row, "correctStrength")), "correctAgility": t.NO_SKILL_SCALING,
            "properFaith": t.ARCANE_NEEDED, "isEnhance": t.NO_PAPERS, "residentSpEffectId1": t.HAMMER_EFFECT,
            "residentSpEffectId2": t.STORM_EFFECT, "isAttributeWep": 0, "sortId": sort + level,
            "originEquipWep": first + max(level - 1, 0) * 100}


def _params(gp):
    defs = load_paramdefs()
    return [Param(gp.files[gp.index(name)], defs[st]) for name, st in PARAMS]


def has_weapon(param_raw):
    rows = _params(thunderwright._open(param_raw))[0].rows
    return any(r in rows for r in WEAPON_IDS)


def add_params(param_raw, talk_raw):
    """`param_raw` (a gameparam.parambnd.dcx with Thunderwright's Kirkhammer) with the three weapons'
    levels and their shop rows added, in the ranges `talk_raw` opens."""
    from sojin.weapon import shop_ranges
    if not thunderwright.has_weapon(param_raw):
        raise Ng7HammerError("it needs Thunderwright's Kirkhammer, from Hunter's Arsenal")
    gp = thunderwright._open(param_raw)
    w, g, s = _params(gp)
    sorts = {w.get(r, "sortId") for r in w.rows}
    if any(r in w.rows or r in g.rows for r in WEAPON_IDS) or \
            any(sort + level in sorts for _n, _f, _s, sort in VARIANTS for level in LEVELS):
        raise Ng7HammerError("its weapon ids or sort ids are taken")
    for name, first, source, sort in VARIANTS:
        for level in LEVELS:
            new, row = first + 100 * level, source + 100 * level
            w.add(new, row, label(name, level))
            for field, value in _fields(w, first, source, sort, level).items():
                w.set(new, field, value)
            g.add(new, row, label(name, level))    # that Kirkhammer's gem slots
            g.set(new, "wepParamId", new)
    thunderwright._shop_rows(s, sorted(shop_ranges(talk_raw)), VARIANTS)
    for (name, _st), param in zip(PARAMS, (w, g, s)):
        gp.files[gp.index(name)] = param.to_bytes()
    return dcx_compress(gp.to_bytes(), param_raw)


def add_text(msg_raw):
    """`msg_raw` (an item.msgbnd.dcx) with the weapons' names and lore (English in every language)."""
    msg = thunderwright._open(msg_raw)
    ni, li = msg.index("武器名.fmg"), msg.index("武器うんちく.fmg")
    names, lore = Fmg(msg.files[ni]), Fmg(msg.files[li])
    for name, first, _source, _sort in VARIANTS:
        for level in LEVELS:
            names.entries[first + 100 * level] = label(name, level)
            lore.entries[first + 100 * level] = LORE
    msg.files[ni], msg.files[li] = names.to_bytes(), lore.to_bytes()
    return dcx_compress(msg.to_bytes(), msg_raw)


def verify(param_in, param_out):
    """Reads the made gameparam back: every other file and row is unchanged, Thunderwright's Kirkhammer
    among them, and the new rows are their sources with only the planned fields changed."""
    before, after = thunderwright._open(param_in), thunderwright._open(param_out)
    ours = {name for name, _st in PARAMS}
    for name in before.names:
        if not any(name.endswith(n) for n in ours) and before.files[before.index(name)] != after.files[after.index(name)]:
            raise Ng7HammerError(f"{name} changed")
    (w0, g0, s0), (w, g, s) = _params(before), _params(after)
    for p0, p1 in ((w0, w), (g0, g), (s0, s)):
        if [r for r in p0.rows if p0.rows[r] != p1.rows.get(r)]:
            raise Ng7HammerError("original rows changed")
    if set(w.rows) - set(w0.rows) != set(WEAPON_IDS) or set(g.rows) - set(g0.rows) != set(WEAPON_IDS):
        raise Ng7HammerError("the new weapon rows are not its levels")
    sold = {s.get(r, "equipId"): s.get(r, "value") for r in s.rows if r not in s0.rows}
    for name, first, source, sort in VARIANTS:
        for level in LEVELS:
            new, row, want = first + 100 * level, source + 100 * level, _fields(w, first, source, sort, level)
            changed = {f[0] for f in w.fields if w.get(new, f[0]) != w.get(row, f[0])}
            if changed - set(want) or any(w.get(new, f) != v for f, v in want.items()):
                raise Ng7HammerError(f"{label(name, level)} is not its Kirkhammer's row with its planned fields")
            if g.get(new, "wepParamId") != new:
                raise Ng7HammerError(f"{label(name, level)}'s gem row names another weapon")
        if sold.get(first) != thunderwright.PRICE:
            raise Ng7HammerError(f"the shop does not sell {name} at +0 for {thunderwright.PRICE}")
    if set(sold) != {first for _n, first, _s, _o in VARIANTS}:
        raise Ng7HammerError("the shop's new rows are not the three weapons at +0")


def make(dvdroot, param_raw, msgs):
    """{game path: bytes}: the gameparam and item texts given (Hunter's Arsenal's) with the weapon."""
    set_game(dvdroot)
    files = {GAMEPARAM: add_params(param_raw, thunderwright._game(TALK))}
    verify(param_raw, files[GAMEPARAM])
    for lang, raw in msgs.items():
        files[f"msg/{lang}/item.msgbnd.dcx"] = add_text(raw)
    return files
