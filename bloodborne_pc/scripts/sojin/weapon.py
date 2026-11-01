# SPDX-License-Identifier: GPL-2.0-or-later
"""Sojin Chikage (双刃千景, "twin-blade Chikage"), made from the player's own CUSA03173 1.09 files
at start (enhancements.py: pc_sojin_chikage, BB_PC_SOJIN).

Three weapons, as the Chikage has: Sojin Chikage, Uncanny Sojin Chikage and Lost Sojin Chikage,
each with that Chikage's stats, scaling, upgrades and gem slots, +0 to +10. Normal mode is
Chikage's katana moveset; trick mode (L1) is Blade of Mercy's twin-blade moveset with a blood hit
on every cut and three abilities (abilities.py): Blood Rhythm, Blood Crescent and Bankai. The
twin attacks keep 65 % of Blade of Mercy's motion values, so their damage per second is the
Chikage's transformed form's; the abilities give the edge. The Bath Messengers sell each at +0
for 10,000 Blood Echoes, in every range their talk script opens (the five price stages).

Files: param/gameparam (new rows only), chr/c0000.anibnd (the moveset a157.tae and six clips in
the behaviour graph), parts/wp_a_1062 and _l (the model, from the Chikage's parts) and
msg/*/item.msgbnd (names and lore, English in every language).

add_params() and add_text() put the same rows and text into another mod's files: mods.py uses
them when a player's mod (ShopEdit, a text mod, ...) replaces those files above this layer.
Lost Sojin Chikage keeps the stand-alone mod's ids (2030000+), so saves that hold it still load.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _path in (HERE, os.path.dirname(HERE)):   # these modules, then scripts/ (fromsoft, esd)
    if _path not in sys.path:
        sys.path.insert(0, _path)

import bbparam  # noqa: E402
import anibnd  # noqa: E402
from bbparam import Param, Fmg, load_paramdefs  # noqa: E402
from fromsoft import Bnd4, dcx_compress, dcx_decompress  # noqa: E402

# (name, first weapon id, the Chikage it takes stats and gem slots from, sortId of its +0)
VARIANTS = (
    ("Sojin Chikage", 2040000, 2000000, 55400),
    ("Uncanny Sojin Chikage", 2050000, 2010000, 55420),
    ("Lost Sojin Chikage", 2030000, 2020000, 55440),
)
LEVELS = range(11)
PRICE = 10000                       # Blood Echoes, at the Bath Messengers
MERCY = 4000000                     # Blade of Mercy: weapon category, motion ids, sheath points
VAR, VAR_CHIKAGE, VAR_MERCY = 2030, 200, 400          # behaviour variations
CATEGORY = 157                      # motion category: a157.tae, a slot the behaviour graph knows
ABILITY_JUDGES = {591, 396}         # Blood Crescent and Bankai shockwave bullet behaviours
RHYTHM_FIRST = 2030001              # Blood Rhythm stack 1, on every trick-mode attack
BLOOD_HIT = 6400                    # Chikage's trick-mode blood hit
BLOOD_ATTRIBUTE = 4                 # Chikage's trick-mode attack attribute
# The twin moveset's hits come about 1.5x as often as Chikage's transformed ones and Blade of
# Mercy's motion values were set for its own low attack: twin attacks keep 65 % of them.
TWIN_MV_SCALE = 0.65
TWIN_MV_FIELDS = ("atkPhysCorrection", "atkMagCorrection", "atkFireCorrection", "atkThunCorrection")
MODEL, CHIKAGE_MODEL = 1062, 1063   # 1062: a model number no weapon uses
# Model part sockets (character dummy poly; -1 hidden), per form: Hang, normal (A), trick (B).
#   0 katana: right hand in normal mode, hung at Blade of Mercy's point (400; Chikage's own 412
#     keeps Blade of Mercy's transform from switching back)   1 scabbard: at the hip
#   2 blood blade: right hand in trick mode   3 a second blood blade: left hand in trick mode
SLOTS = {0: (400, 300, -1), 1: (412, 412, 412), 2: (-1, -1, 300), 3: (-1, -1, 340)}
# Taken from the Chikage: damage, scaling, requirements, effects, upgrades, icon.
FROM_CHIKAGE = [
    "weight", "sellValue", "fixPrice", "basicPrice",
    "correctStrength", "correctAgility", "correctMagic", "correctFaith",
    "spEffectBehaviorId0", "spEffectBehaviorId1", "spEffectBehaviorId2",
    "residentSpEffectId", "residentSpEffectId1", "residentSpEffectId2",
    "materialSetId", "iconId", "durability", "durabilityMax",
    "attackBasePhysics", "attackBaseMagic", "attackBaseFire", "attackBaseThunder",
    "attackBaseStamina", "saWeaponDamage", "attackBaseRepel", "guardLevel",
    "properStrength", "properAgility", "properMagic", "properFaith",
    "isNormalAttackType", "isBlowAttackType", "isSlashAttackType", "isThrustAttackType",
    "PhysAtkMenuDispType", "repositoryCategory", "wepRegainHp", "levelSyncCorrectId",
    "correctType", "reinforceTypeId",
]
PARAMS = (("EquipParamWeapon.param", "EQUIP_PARAM_WEAPON_ST"), ("WeaponGenParam.param", "WEAPON_GEN_PARAM_ST"),
          ("ShopLineupParam.param", "SHOP_LINEUP_PARAM"), ("BehaviorParam_PC.param", "BEHAVIOR_PARAM_ST"),
          ("AtkParam_Pc.param", "ATK_PARAM_ST"), ("SpEffectParam.param", "SP_EFFECT_PARAM_ST"),
          ("Bullet.param", "BULLET_PARAM_ST"))
GAMEPARAM = "param/gameparam/gameparam.parambnd.dcx"
TALK = "script/talk/m21_00_00_00.talkesdbnd.dcx"     # the Hunter's Dream
SHOP_SCRIPT, OPEN_SHOP = "t210691.esd", (1, 22)      # the Bath Messengers; OpenRegularShop(first, last)
LORE = ("A Chikage reforged by a Cainhurst smith as a pair of blades, for a royal guard who "
        "fought with both hands.\n\nIn its normal form it is the familiar Chikage. Transformed, "
        "the scabbard parts into a second blade and both are coated in the wielder's own blood. "
        "The twin blades cut with the cursed blood of the Vilebloods, but drain the wielder's "
        "HP while drawn, and grow stronger with bloodtinge.")
WEAPON_IDS = {first + 100 * level for _n, first, _s, _o in VARIANTS for level in LEVELS}


class SojinError(ValueError):
    pass


def set_game(dvdroot):
    """The dump's dvdroot_ps4 folder, for every module that reads the game's own files."""
    bbparam.GAME = anibnd.GAME = str(dvdroot).replace("\\", "/").rstrip("/") + "/"


def _game(relative):
    with open(bbparam.GAME + relative, "rb") as f:
        return f.read()


def label(name, level):
    return name + (f" +{level}" if level else "")


def bleeds(judge):
    """Trick-mode attacks that carry the blood hit, as Chikage's own: the transform attacks and
    every trick-mode attack except close range (700) and the falling attack's landing (741)."""
    return judge in (390, 395, 930) or (400 <= judge < 800 and judge not in (700, 741))


def twin_mv(value):
    """A twin attack's motion value (%) from Blade of Mercy's, rounded half up."""
    return int(value * TWIN_MV_SCALE + 0.5)


_MOVESET = None


def moveset():
    """(a157.tae bytes, judge map): the combined moveset with the abilities' events."""
    global _MOVESET
    if _MOVESET is None:
        from combine_moveset import build_combined
        from ability_events import add_ability_events
        tae, judges = build_combined(CATEGORY)
        _MOVESET = add_ability_events(tae), judges
    return _MOVESET


# --- the Bath Messengers' shop ------------------------------------------------------------------
def _ints(code):
    """The integer literals of an expression (esd.lit's encoding)."""
    out, i = [], 0
    while i < len(code):
        c = code[i]
        if 0x40 <= c <= 0x7F:
            out.append(c - 0x40)
            i += 1
        elif c == 0x82:
            out.append(struct.unpack_from("<i", code, i + 1)[0])
            i += 5
        else:
            i += 1
    return out


def shop_ranges(talk_raw):
    """The (first, last) shop row ranges the Bath Messengers' talk script opens."""
    import esd
    talk = Bnd4(dcx_decompress(talk_raw))
    names = [n.replace("\\", "/").rsplit("/", 1)[-1] for n in talk.names]
    if SHOP_SCRIPT not in names:
        raise SojinError(f"no {SHOP_SCRIPT} in the Hunter's Dream talk scripts")
    data = talk.files[names.index(SHOP_SCRIPT)]
    ranges = []
    try:
        script = esd.parse(data)
    except esd.EsdError:
        # A mod's script written by another tool (ShopEdit's) need not have the game's layout.
        # The arguments are still the game's expressions, each a 32-bit literal and an end
        # (0x82 n 0xa1), the first and last row side by side.
        lits = [(i, struct.unpack_from("<i", data, i + 1)[0]) for i in range(len(data) - 5)
                if data[i] == 0x82 and data[i + 5] == 0xA1]
        for (at, first), (at2, last) in zip(lits, lits[1:]):
            if at2 == at + 6 and 1000 <= first and 9 <= last - first <= 999999:
                ranges.append((first, last))
    else:
        for c in script.cmds:
            if (c.bank, c.id) == OPEN_SHOP:
                args = [_ints(script.exprs[x].code) for x in script.runs[c.args].items]
                if len(args) == 2 and all(len(a) == 1 for a in args) and args[0][0] <= args[1][0]:
                    ranges.append((args[0][0], args[1][0]))
    if not ranges:
        raise SojinError(f"{SHOP_SCRIPT} opens no shop")
    return sorted(set(ranges))


def _add_shop_rows(s, ranges):
    """Each weapon's +0 at PRICE in every range, after the range's last row."""
    rows = sorted(s.rows)
    added = []
    for first, last in ranges:
        inside = [r for r in rows if first <= r <= last]
        template = next((r for r in inside if s.get(r, "equipType") == 0), inside[0] if inside else rows[0])
        row = (max(inside) + 1) if inside else first
        if row + len(VARIANTS) - 1 > last:
            raise SojinError(f"shop range {first}..{last} is full")
        for name, weapon, _source, _sort in VARIANTS:
            s.add(row, template, f"[Bath Messengers] {name}")
            # qwcId is the flag a row waits for (the game's Uncanny and Lost weapons wait for the
            # one set when the player first finds them); -1 shows the row from the start.
            for field, value in (("equipId", weapon), ("value", PRICE), ("equipType", 0), ("eventFlag", -1),
                                 ("qwcId", -1), ("sellQuantity", -1), ("mtrlId", -1)):
                s.set(row, field, value)
            added.append(row)
            row += 1
    return added


# --- the params -----------------------------------------------------------------------------------
def _open(raw):
    return Bnd4(dcx_decompress(raw))


def add_params(param_raw, talk_raw):
    """`param_raw` (a gameparam.parambnd.dcx) with the weapons, their moveset's behaviour and
    attack rows, the abilities and the shop rows (in the ranges `talk_raw` opens) added. Rows
    that are there already are left as they are; SojinError when the ids are taken."""
    from abilities import add_abilities, TWIN_BLOOD_HIT, TWIN_DRAIN
    _tae, judges = moveset()
    defs = load_paramdefs()
    gp = _open(param_raw)
    params = {}
    for name, st in PARAMS:
        if name not in gp.names and not any(n.endswith("\\" + name) for n in gp.names):
            raise SojinError(f"{name} missing from the gameparam")
        i = gp.index(name)
        params[name] = (i, Param(gp.files[i], defs[st]))
    w, g, s = (params[n][1] for n in ("EquipParamWeapon.param", "WeaponGenParam.param", "ShopLineupParam.param"))
    b, a = params["BehaviorParam_PC.param"][1], params["AtkParam_Pc.param"][1]
    taken = sorted(r for r in WEAPON_IDS if r in w.rows or r in g.rows)
    if taken:
        raise SojinError(f"weapon ids taken: {taken[:3]}")
    if any(w.get(r, "equipModelId") == MODEL for r in w.rows):
        raise SojinError(f"model {MODEL} taken")
    if any(w.get(r, "behaviorVariationId") == VAR for r in w.rows) or \
            any(100000000 + VAR * 1000 <= r < 100000000 + VAR * 1000 + 1000 for r in b.rows) or \
            any(VAR * 1000 <= r < VAR * 1000 + 1000 for r in a.rows):
        raise SojinError(f"behaviour variation {VAR} taken")
    sorts = {w.get(r, "sortId") for r in w.rows}
    if any(sort + level in sorts for _n, _f, _s, sort in VARIANTS for level in LEVELS):
        raise SojinError("sort ids taken")

    # Behaviour variation 2030: Blade of Mercy's table (its trick mode, and rows other animations
    # use, such as the visceral attacks), then each judge the combined moveset attacks with from
    # its source: normal mode from Chikage's table, trick mode from Blade of Mercy's.
    def rows_of(var):
        return {b.get(r, "behaviorJudgeId"): r for r in b.rows if b.get(r, "variationId") == var}
    by_var = {VAR_CHIKAGE: rows_of(VAR_CHIKAGE), VAR_MERCY: rows_of(VAR_MERCY)}
    sources = dict(by_var[VAR_MERCY])
    for judge, (src_var, src_judge) in judges.items():
        sources[judge] = by_var[src_var][src_judge]
    for judge, src in sorted(sources.items()):
        if b.get(src, "refType") != 0:
            raise SojinError(f"behaviour {src} is not an attack")
        src_atk, new_atk = b.get(src, "refId"), VAR * 1000 + judge
        new = 100000000 + VAR * 1000 + judge
        b.add(new, src, "Sojin Chikage: " + b.name(src))
        b.set(new, "variationId", VAR)
        b.set(new, "behaviorJudgeId", judge)   # a renumbered source (790/795 from 395/390)
        b.set(new, "refId", new_atk)
        a.add(new_atk, src_atk, "Sojin Chikage: " + a.name(src_atk))
        if judges.get(judge, (None,))[0] == VAR_MERCY:   # a twin attack of the combined moveset
            for f in TWIN_MV_FIELDS:
                a.set(new_atk, f, twin_mv(a.get(new_atk, f)))
        if bleeds(judge):
            if a.get(new_atk, "spEffectId1") not in (-1, BLOOD_HIT):
                raise SojinError(f"attack {judge} has another spEffectId1")
            a.set(new_atk, "spEffectId1", BLOOD_HIT if judge in (790, 795) else TWIN_BLOOD_HIT)
            if judge not in (790, 795):  # transform back to normal: Chikage keeps the cut's own attribute
                a.set(new_atk, "atkAttribute", BLOOD_ATTRIBUTE)

    for name, first, source, sort in VARIANTS:
        for level in LEVELS:
            new, chik, mercy = first + level * 100, source + level * 100, MERCY + level * 100
            w.add(new, mercy, label(name, level))
            for field in FROM_CHIKAGE:
                w.set(new, field, w.get(chik, field))
            w.set(new, "residentSpEffectId", TWIN_DRAIN)   # its own trick-mode drain (Chikage's 6740 is 0.85 %/s)
            w.set(new, "behaviorVariationId", VAR)
            w.set(new, "wepmotionCategory", CATEGORY)
            w.set(new, "equipModelId", MODEL)
            for slot, (hang, form_a, form_b) in SLOTS.items():
                w.set(new, f"dmypolyId_Slot{slot}RightHang", hang)
                w.set(new, f"dmypolyId_Slot{slot}RightFormA", form_a)
                w.set(new, f"dmypolyId_Slot{slot}RightFormB", form_b)
            w.set(new, "sortId", sort + level)
            w.set(new, "originEquipWep", first + max(level - 1, 0) * 100)
            g.add(new, chik, label(name, level))           # that Chikage's gem slots
            g.set(new, "wepParamId", new)
    _add_shop_rows(s, shop_ranges(talk_raw))
    add_abilities({"SpEffectParam": params["SpEffectParam.param"][1], "Bullet": params["Bullet.param"][1],
                   "AtkParam_Pc": a, "BehaviorParam_PC": b})
    for i, p in params.values():
        gp.files[i] = p.to_bytes()
    return dcx_compress(gp.to_bytes(), param_raw)


def has_weapon(param_raw):
    """Whether a gameparam already has the Sojin Chikage weapons."""
    defs = load_paramdefs()
    gp = _open(param_raw)
    w = Param(gp.files[gp.index("EquipParamWeapon.param")], defs["EQUIP_PARAM_WEAPON_ST"])
    return any(r in w.rows for r in WEAPON_IDS)


# --- text, model, moveset -----------------------------------------------------------------------
def add_text(msg_raw):
    """`msg_raw` (an item.msgbnd.dcx) with the weapons' names and lore (English in every
    language, so none shows a blank name)."""
    msg = _open(msg_raw)
    ni, li = msg.index("武器名.fmg"), msg.index("武器うんちく.fmg")
    names, lore = Fmg(msg.files[ni]), Fmg(msg.files[li])
    for name, first, _source, _sort in VARIANTS:
        for level in LEVELS:
            names.entries[first + level * 100] = label(name, level)
            lore.entries[first + level * 100] = LORE
    msg.files[ni], msg.files[li] = names.to_bytes(), lore.to_bytes()
    return dcx_compress(msg.to_bytes(), msg_raw)


def write_bnd4(header, entries):
    """BND4 (format 0x74, UTF-16 names, no hash table, data aligned to 16), as the game's part
    archives: header = their 0x40-byte header; entries = (flags, id, name, data)."""
    count = len(entries)
    names, name_offs = bytearray(), []
    names_at = 0x40 + count * 0x24
    for _, _, name, _ in entries:
        name_offs.append(names_at + len(names))
        names += name.encode("utf-16-le") + b"\0\0"
    headers_end = names_at + len(names)
    data_at = (headers_end + 15) & ~15
    head = bytearray(header[:0x40])
    struct.pack_into("<i", head, 0x0C, count)
    struct.pack_into("<q", head, 0x28, headers_end)
    files, body = bytearray(), bytearray()
    for (flags, fid, _, data), name_off in zip(entries, name_offs):
        while (data_at + len(body)) % 16:
            body.append(0)
        files += struct.pack("<B3xiqqIiI", flags, -1, len(data), len(data), data_at + len(body), fid, name_off)
        body += data
    return bytes(head + files + names + b"\0" * (data_at - headers_end) + body)


def model_files():
    """Model 1062 from the Chikage's parts (1063): katana, scabbard, blood blade, and the blood
    blade again as part 3 for the left hand. Both detail levels."""
    raw = _game(f"parts/wp_a_{CHIKAGE_MODEL}.partsbnd.dcx")
    data = dcx_decompress(raw)
    src = Bnd4(data)
    entries = [(data[0x40 + i * 0x24], fid, name, f) for i, (fid, name, f) in enumerate(zip(src.ids, src.names, src.files))]
    if write_bnd4(data, entries) != data:   # the writer must rebuild the game's own archive
        raise SojinError(f"the part archive writer does not reproduce wp_a_{CHIKAGE_MODEL}")
    files = {}
    for suffix in ("", "_l"):
        raw = _game(f"parts/wp_a_{CHIKAGE_MODEL}{suffix}.partsbnd.dcx")
        data = dcx_decompress(raw)
        src = Bnd4(data)
        entries = []
        for i, (fid, name, f) in enumerate(zip(src.ids, src.names, src.files)):
            # The Chikage's part animations (ids 400+) follow its own moveset and keep the parts
            # from switching on Blade of Mercy's transform; the twin model, like Blade of
            # Mercy's, has none.
            if fid >= 400:
                continue
            flags = data[0x40 + i * 0x24]
            entries.append((flags, fid, name.replace(f"WP_A_{CHIKAGE_MODEL}", f"WP_A_{MODEL}"), f))
            if fid == 202:  # the blood blade, once more as part 3
                entries.append((flags, 203, name.replace(f"WP_A_{CHIKAGE_MODEL}_2", f"WP_A_{MODEL}_3"), f))
        entries.sort(key=lambda e: e[1])
        files[f"parts/wp_a_{MODEL}{suffix}.partsbnd.dcx"] = dcx_compress(write_bnd4(data, entries), raw)
    return files


def anibnd_file():
    """The player's animation archive with the moveset a157.tae and its six behaviour clips."""
    from behavior_graph import patch_behavior
    tae, _judges = moveset()
    araw = _game("chr/c0000.anibnd.dcx")
    abnd = anibnd.Bnd4Archive(dcx_decompress(araw))
    if abnd.find(name=f"a{CATEGORY}.tae") is not None:
        raise SojinError(f"moveset slot a{CATEGORY} taken")
    anibnd.add_tae(abnd, CATEGORY, tae)
    data = patch_behavior(abnd.to_bytes())
    return dcx_compress(data, araw)


def make(dvdroot):
    """{game path: bytes} of every file, made from the dump at `dvdroot`."""
    set_game(dvdroot)
    if os.path.exists(bbparam.GAME + f"parts/wp_a_{MODEL}.partsbnd.dcx"):
        raise SojinError(f"the game has a wp_a_{MODEL}")
    files = model_files()
    files[GAMEPARAM] = add_params(_game(GAMEPARAM), _game(TALK))
    files["chr/c0000.anibnd.dcx"] = anibnd_file()
    for lang in sorted(os.listdir(bbparam.GAME + "msg")):
        relative = f"msg/{lang}/item.msgbnd.dcx"
        if os.path.exists(bbparam.GAME + relative):
            files[relative] = add_text(_game(relative))
    verify(files, _game(GAMEPARAM))
    return files


# --- checks -----------------------------------------------------------------------------------------
def verify(files, base_param):
    """Reads the made files back and checks every new row against its sources; SojinError if
    anything differs."""
    def check(ok, what):
        if not ok:
            raise SojinError(f"check failed: {what}")
    from abilities import TWIN_BLOOD_HIT, TWIN_DRAIN
    tae, judges = moveset()
    defs = load_paramdefs()
    gp, orig = _open(files[GAMEPARAM]), _open(base_param)
    P = lambda bnd, n, st: Param(bnd.files[bnd.index(n)], defs[st])   # noqa: E731
    for n, st in PARAMS:
        new, old = P(gp, n, st), P(orig, n, st)
        check(all(new.rows[r] == old.rows[r] and new.names[r] == old.names[r] for r in old.rows), f"{n}: existing rows kept")
    changed = {n.rsplit("\\", 1)[-1] for n, x, y in zip(gp.names, gp.files, orig.files) if x != y}
    check(changed == {n for n, _st in PARAMS}, f"only the expected params changed ({sorted(changed)})")
    w0, w = P(orig, *PARAMS[0]), P(gp, *PARAMS[0])
    g, s = P(gp, *PARAMS[1]), P(gp, *PARAMS[2])
    b, a, a0 = P(gp, *PARAMS[3]), P(gp, *PARAMS[4]), P(orig, *PARAMS[4])
    for name, first, source, sort in VARIANTS:
        for level in LEVELS:
            new, chik = first + level * 100, source + level * 100
            for field in FROM_CHIKAGE:
                if field != "residentSpEffectId":
                    check(w.get(new, field) == w0.get(chik, field), f"{new} {field}")
            check(w.get(new, "residentSpEffectId") == TWIN_DRAIN, f"{new} drain")
            for field in ("weaponCategory", "wepmotionBothHandId", "wepmotionOneHandId"):
                check(w.get(new, field) == w0.get(MERCY + level * 100, field), f"{new} {field}")
            check(w.get(new, "behaviorVariationId") == VAR and w.get(new, "equipModelId") == MODEL, f"{new} moveset")
            check(w.get(new, "wepmotionCategory") == CATEGORY and w.get(new, "sortId") == sort + level, f"{new} sort")
            check(g.get(new, "wepParamId") == new, f"{new} gem slots")
        shop = [r for r in s.rows if s.get(r, "equipId") == first and s.get(r, "equipType") == 0]
        check(shop and all(s.get(r, "value") == PRICE and s.get(r, "qwcId") == -1 and s.get(r, "eventFlag") == -1
                           for r in shop), f"{name} in the shop at {PRICE}, shown from the start")
    mine = [r for r in b.rows if b.get(r, "variationId") == VAR]
    mercy = {b.get(r, "behaviorJudgeId") for r in b.rows if b.get(r, "variationId") == VAR_MERCY}
    check({b.get(r, "behaviorJudgeId") for r in mine} == mercy | set(judges) | ABILITY_JUDGES, "judge set")
    bl = P(gp, *PARAMS[6])
    for judge, (src_var, src_judge) in judges.items():   # each judge's hits are its source's
        new_atk, src_atk = VAR * 1000 + judge, src_var * 1000 + src_judge
        for h in range(4):
            for k in (1, 2):
                f = f"hit{h}_DmyPoly{k}"
                check(a.get(new_atk, f) == a0.get(src_atk, f), f"attack {judge} {f}")
        for f in TWIN_MV_FIELDS:
            want = twin_mv(a0.get(src_atk, f)) if src_var == VAR_MERCY else a0.get(src_atk, f)
            check(a.get(new_atk, f) == want, f"attack {judge} {f}")
    for r in mine:
        j, atk = b.get(r, "behaviorJudgeId"), b.get(r, "refId")
        if j in ABILITY_JUDGES:
            check(b.get(r, "refType") == 1 and atk in bl.rows, f"ability {j}")
            continue
        check(atk == VAR * 1000 + j and atk in a.rows, f"behaviour {j}")
        check((a.get(atk, "spEffectId1") in (BLOOD_HIT, TWIN_BLOOD_HIT)) == bleeds(j), f"blood hit {j}")
        if bleeds(j):
            check(a.get(atk, "spEffectId1") == (BLOOD_HIT if j in (790, 795) else TWIN_BLOOD_HIT), f"blood hit {j}")
        check((a.get(atk, "spEffectId0") == RHYTHM_FIRST) == bleeds(j), f"Blood Rhythm hook {j}")
    for suffix in ("", "_l"):
        m = Bnd4(dcx_decompress(files[f"parts/wp_a_{MODEL}{suffix}.partsbnd.dcx"]))
        c = Bnd4(dcx_decompress(_game(f"parts/wp_a_{CHIKAGE_MODEL}{suffix}.partsbnd.dcx")))
        check(m.ids == sorted([i for i in c.ids if i < 400] + [203]), f"model {suffix} parts")
        check(m.files[m.ids.index(203)] == c.files[c.ids.index(202)], f"model {suffix} part 3")
        check(all(m.files[m.ids.index(i)] == c.files[c.ids.index(i)] for i in c.ids if i < 400), f"model {suffix} copy")
    mb = anibnd.Bnd4Archive(dcx_decompress(files["chr/c0000.anibnd.dcx"]))
    ob = anibnd.Bnd4Archive(dcx_decompress(_game("chr/c0000.anibnd.dcx")))
    entry = mb.find(name=f"a{CATEGORY}.tae")
    check(entry is not None and entry.data == tae, "a157.tae")
    others = [e.name.rsplit("\\", 1)[-1] for e in ob.entries if (mb.find(id=e.id) is None or mb.find(id=e.id).data != e.data)]
    check(sorted(others) == ["c0000.hkx"] * 3 and len(mb.entries) == len(ob.entries) + 1, "anibnd changes")
    from tae import Tae
    check(318 in {e.type for an in Tae(entry.data).anims if an.id == 41100 for e in an.events}, "Blood Crescent event")
    for relative, data in files.items():
        if relative.endswith("item.msgbnd.dcx"):
            msg = _open(data)
            names = Fmg(msg.files[msg.index("武器名.fmg")]).entries
            check(all(names.get(first + 1000) == label(name, 10) for name, first, _s, _o in VARIANTS), relative)


if __name__ == "__main__":
    import argparse
    import time
    parser = argparse.ArgumentParser(description="Make the Sojin Chikage files from a dump into a folder.")
    parser.add_argument("game", help="the game folder (with dvdroot_ps4)")
    parser.add_argument("out", help="output folder (gets dvdroot_ps4/...)")
    args = parser.parse_args()
    start = time.time()
    made = make(os.path.join(args.game, "dvdroot_ps4"))
    for rel, blob in sorted(made.items()):
        path = os.path.join(args.out, "dvdroot_ps4", rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(blob)
    print(f"{len(made)} files in {time.time() - start:.1f} s, checked")
