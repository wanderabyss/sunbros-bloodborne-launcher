# SPDX-License-Identifier: GPL-2.0-or-later
"""Thunderwright's Kirkhammer: a Kirkhammer charged with bolt in both forms, the hammer most, whose
blows send lightning along the ground. Made from the player's own CUSA03173 1.09 files.

It scales with Strength and Arcane: Arcane as strongly as Strength (the Kirkhammer's Strength
correction at each level), no Skill. Its damage is split, not added: PHYSICAL_SCALE of the
Kirkhammer's physical and a bolt base of bolt(level) (150 + 110 at +10, as Ludwig's Holy Blade
splits 200 + 50, against the Kirkhammer's 210). Sword mode is
the Kirkhammer's sword moveset, its physical untouched and SWORD_BOLT_SCALE of each motion value
added as bolt. Hammer mode keeps HAMMER_PHYS_SCALE of the Kirkhammer's physical motion values and
the full bolt on top; the hammer crackles with the charged Tonitrus's lightning, wrapped in Bolt
Paper's storm as well (STORM_EFFECT), and hits as bolt (special attribute 6, as the Tonitrus and Bolt
Paper). The Bath Messengers sell it at +0 for 10,000
Blood Echoes. There are three, as the Kirkhammer has: each has that Kirkhammer's gem slots, which is
all that differs (normal: Radial, Triangle, Radial; Uncanny: Radial, Waning, Radial; Lost: Radial,
Triangle, Waning, at +10).

The lightning: lines of Tiny Tonitrus's strikes sent along the ground from the hammer head (each
enemy is hit once by each line), in three sizes told apart by length and number of lines:
  - small: every R1-type hammer hit and both transform attacks (R1 then L1, either way);
  - medium, twice as long: every R2-type hammer hit and a part-charged R2 (42620);
  - high, Thunder Chariot: the fully charged R2 slam (42630, and its follow-up 42660), the tool's
    full length in three lines.
Thunder Chariot takes one Quicksilver Bullet (the uncharged and part-charged R2 are free) and
charges the wielder with the charged Tonitrus's own effect (bolt x1.7 +40) for CHARGE_TIME
seconds; the transform back to the sword (Static Draw) charges the wielder too, for free and for
DRAW_CHARGE_TIME seconds only. Both transforms (into the hammer and Static Draw) also flash with a
Tiny Tonitrus bolt at the hammer head (FLASH), which only shows. Thunder Chariot's SKY chain is the
Fishing Hamlet fishman priests' lightning (sky.py), its warning and bolt now unseen: the slam whited out
the picture with them. Thunder Chariot shows a third of its strikes and no launcher effect. Each
line's share of the weapon's bolt attack power is its `bolt` below.

It plays the Kirkhammer's own motion category (48, a105.tae): the action script (c0000.hks) switches
category-specific moves, the hammer's charged R2 among them, on lists of motion categories, and a
new category (159 was tried) is in none of them, so its charged R2 never starts. The lightning
events go into a105 itself and name behaviour judges (931, 951, 961, 971, 981) that only this weapon's
variation (2060) has; the Kirkhammer's variation (800) has no such rows, so for it the events do
nothing.

Files: param/gameparam (new rows only), chr/c0000.anibnd (a105.tae with the lightning events),
msg/*/item.msgbnd (names and lore, English in every language) and parts/wp_a_1032 and _l: its own
model, the Kirkhammer's (1031) mesh with the stone block made rune-iron (rune_iron.py), so the plain
Kirkhammer keeps its look. Only the texture names change in the copy (WP_A_1031_* to WP_A_1032_*,
in the texture archive and the meshes' texture paths), so the two never share a loaded texture;
bone and mesh names stay, as the part animations bind to them.

add_params(), add_text() and anibnd_file() add to whatever copy of those files they are given (a
player's mod, or one that already holds the Sojin Chikage's a157), as the Sojin Chikage does.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _path in (os.path.join(os.path.dirname(HERE), "sojin"), os.path.dirname(HERE)):  # tools, then scripts/
    if _path not in sys.path:
        sys.path.insert(0, _path)

import bbparam  # noqa: E402
import anibnd  # noqa: E402
import tae_write as tw  # noqa: E402
import ability_events as ae  # noqa: E402
from bbparam import Param, Fmg, load_paramdefs  # noqa: E402
from fromsoft import Bnd4, dcx_compress, dcx_decompress  # noqa: E402
from thunderwright import sky  # noqa: E402

NAME = "Thunderwright's Kirkhammer"
# (name, first weapon id, the Kirkhammer it takes stats and gem slots from, sortId of its +0)
VARIANTS = (
    (NAME, 2060000, 8000000, 55460),    # after the three Sojin Chikage weapons (55400 / 55420 / 55440)
    ("Uncanny Thunderwright Hammer", 2120000, 8010000, 55580),
    ("Lost Thunderwright Hammer", 2130000, 8020000, 55620),   # 55600-55610 are the game's
)
MODEL, KIRK_MODEL = 1032, 1031      # 1032: a model number no weapon uses
LEVELS = range(11)
PRICE = 10000                       # Blood Echoes, at the Bath Messengers
VAR, KIRK_VAR = 2060, 800           # behaviour variations
KIRK_TAE = 105                      # the Kirkhammer's motion category 48 plays a105.tae
# Physical: this share of the Kirkhammer's at each level (75 at +0, 150 at +10, of 105 / 210). Bolt
# base: BOLT_BASE + BOLT_STEP a level, rounded half up (55 at +0, 110 at +10); scaled by Arcane. 4.2.17
# kept the whole physical and added bolt 90 / 180 on top, about 1.7 times the Kirkhammer's attack.
PHYSICAL_SCALE = 150 / 210
BOLT_BASE, BOLT_STEP = 55, 5.5


def physical(kirk_physical):
    return int(kirk_physical * PHYSICAL_SCALE + 0.5)


def bolt(level):
    return int(BOLT_BASE + BOLT_STEP * level + 0.5)


# Strength / Arcane weapon: Arcane correction = the Kirkhammer's Strength correction at each level
# (60 at +0 .. 100 at +10, the Strength one is kept), Skill correction 0. It needs Arcane 25, so
# it is an Arcane build's weapon: below 25 the game's unmet-requirement penalty cuts its attack (4.2.17's
# 12 let almost any build add the full bolt to the Kirkhammer's physical; the Holy Moonlight Sword,
# Arcane-scaled as strongly, needs 14; the Tonitrus, bolt 40, none); Strength 16 and Skill 10 stay
# the Kirkhammer's.
NO_SKILL_SCALING, ARCANE_NEEDED = 0, 25
# No papers: isEnhance 0, as every game weapon with a built-in element (the Kirkhammer has 1).
NO_PAPERS = 0
# Hammer hits keep this much of the Kirkhammer's physical motion value; the full bolt comes on top.
HAMMER_PHYS_SCALE = 0.76
# Sword hits keep all their physical and carry this much of the motion value as bolt.
SWORD_BOLT_SCALE = 0.5
# The hammer-mode effect: a copy of the Tonitrus's resident 6033 (no attack fields), valid in trick
# mode only (as the Chikage's 6740), with the charged Tonitrus's look (stateInfo 30: sfx 7210 at the
# weapon's dummy 206, which the hammer part has) and bolt hits (special attribute 6, as the
# Tonitrus and Bolt Paper's 2220).
HAMMER_EFFECT, HAMMER_EFFECT_SRC = 2060001, 6033
HAMMER_LOOK, BOLT_SP_ATTRIBUTE, TRICK_ONLY = 30, 6, 2
# The storm on the hammer: a second trick-mode effect, again a copy of 6033 with nothing but a look,
# showing Bolt Paper's glow (stateInfo 61: sfx 502 at dummy 206, as Bolt Paper's own 2220) over the
# charged crackle (30). In the weapon's free resident slot 2. Not 151 ("bolt enhancement", the
# unused 3955's): its sfx 22724 is in none of 1.09's effect banks, so it would show nothing.
STORM_EFFECT, STORM_LOOK = 2060005, 61
# The charge: the charged Tonitrus's own effect (6032: bolt x1.7 +40, the 7210 look, in either
# form), for CHARGE_TIME seconds and without its durability cost. Static Draw's is the same effect
# for DRAW_CHARGE_TIME seconds: it is free, so it is short (10 s in 4.2.17, every transform back).
STORED_CHARGE, CHARGED_TONITRUS, CHARGE_TIME = 2060002, 6032, 10.0
DRAW_CHARGE, DRAW_CHARGE_TIME = 2060004, 4.0
# Thunder Chariot's price, then its charge: a copy of the Tonitrus's 6030 (0.1 s, then replaced by
# its charge 6032) that takes a Quicksilver Bullet (addBulletNum -1, as the final boss's 8053 takes
# the player's) and is replaced by STORED_CHARGE. An unseen bullet of its own puts it on the
# wielder, once a slam (the slam's launcher fans out into three).
BULLET_COST, TONITRUS_CHARGING, BULLETS_TAKEN = 2060003, 6030, 1
COST = dict(judge=981, bullet=2060070, name="Thunder Chariot: Quicksilver Bullet")
# The transform flash: Tiny Tonitrus's launcher made a bolt on the spot - no flight, no attack, no
# follow-up - that ends at once and shows the strikes' own hit effect (bullet 428's sfxId_Hit) at the
# hammer head, at the transform's impact.
FLASH = dict(judge=991, bullet=2060080, name="Transform flash", strike=428, life=0.05)
# Thunder Chariot's sky lightning (sky.py): the fishman priests' spell from its positioning dummy
# (rises ~2 m) through its warning glow to the falling bolt, copied without attack and ending there
# (the spell's damage bullets 405114+ are left out). Fired from the hammer head with the high line.
SKY = dict(judge=993, bullets=(2060090, 2060091, 2060092), sources=(405111, 405112, 405113),
           name="Thunder Chariot: sky lightning")
# Where the lightning starts: the assembled hammer is model part 2 (dmypolyId_Slot2RightFormB) and
# its dummy 100 sits in the stone head. The Holy Moonlight Sword fires its waves from 12130 the same way.
HEAD = 12100
LAUNCHER = 410
HMS_WAVE_BEHAVIOUR, HMS_WAVE_ATTACK, TINY_TONITRUS_ATTACK = 102600591, 2600591, 24000
TONITRUS_BURST_ATTACK = 1300190     # the Tonitrus's charge crackle: light knockback, no stagger
FEEL = ("knockbackDist", "dmgLevel")                        # from each line's `feel` row
MATERIAL = ("atkMaterial", "defMaterial", "defSfxMaterial")  # every bolt hit: Tiny Tonitrus's
# The lines: Tiny Tonitrus's launcher 410 and the last len(strikes) of its strikes 411..428 (the
# tool's own line is all 18), each kind its own copies. fan = (lines, first line's angle, degrees
# between lines), as the Blunderbuss's pellets (5, -12, 6) and the game's rings of lightning and
# fire (one shared hit list); radius = each strike's hit radius (Tiny Tonitrus's: 0.3 m); feel =
# the attack row whose knockback and stagger it has (the small ones do not break a combo); charge =
# an effect the launcher puts on the wielder; shown = every how many strikes keeps its effects, the
# rest still hit, unseen (the fan's lines share these rows). Thunder Chariot's flash fills the
# picture otherwise; of its effects the sky bolt's did the most (_sky_fields), then the launcher's.
CHAINS = {
    "high": dict(judge=931, launcher=2060010, strikes=tuple(range(411, 429)), atk=2060931, bolt=150,
                 fan=(3, -20, 20), radius=1.0, feel=TINY_TONITRUS_ATTACK, shown=3, name="Thunder Chariot"),
    "medium": dict(judge=961, launcher=2060050, strikes=tuple(range(417, 429)), atk=2060961, bolt=80,
                   fan=(1, 0, 0), radius=0.8, feel=TINY_TONITRUS_ATTACK, name="Thunderclap"),
    "small": dict(judge=951, launcher=2060030, strikes=tuple(range(423, 429)), atk=2060951, bolt=50,
                  fan=(1, 0, 0), radius=0.6, feel=TONITRUS_BURST_ATTACK, name="Thunderstrike"),
    "draw": dict(judge=971, launcher=2060040, strikes=tuple(range(423, 429)), atk=2060971, bolt=50,
                 fan=(1, 0, 0), radius=0.6, feel=TONITRUS_BURST_ATTACK, charge=DRAW_CHARGE,
                 name="Static Draw"),
}
# Which line each hammer animation sends at its impact, by the Kirkhammer's own attack names:
# "small" (R1, and its rolling, backstep, dash and unsheathing forms) the small one, "large" (R2,
# its backstep and dash forms, the leap, the plunge's landing) the medium one.
SMALL_ANIMS = (40000, 40010, 40100, 40200, 40300, 42100, 42200, 42220, 42230, 42240, 42500, 42800, 42810)
MEDIUM_ANIMS = (41000, 41010, 41100, 41200, 41300, 42150, 42300, 42420, 42550)
TO_HAMMER, TO_SWORD = (33300, 33310), (43300, 43310)   # transform attacks: small, Static Draw
FALLING = (42400, 42410)            # the plunge's fall: no line (its landing, 42420, has one)
# (animation, attack judge the line follows, line): the charged R2 set, as the Holy Moonlight
# Sword's waves (a143 42620 / 42630 / 42660, type 318 on the last frame of the swing's attack).
CHARGE_EVENTS = ((42630, 930, "high"), (42660, 940, "high"), (42620, 910, "medium"))
SHOCK_WAVES = range(596, 600)       # the Kirkhammer's impact hits (shock wave DL1-3), as the head lands
ATTACK_EVENT, BULLET_EVENT = 1, 318
FPS = 30
PARAMS = (("EquipParamWeapon.param", "EQUIP_PARAM_WEAPON_ST"), ("WeaponGenParam.param", "WEAPON_GEN_PARAM_ST"),
          ("ShopLineupParam.param", "SHOP_LINEUP_PARAM"), ("BehaviorParam_PC.param", "BEHAVIOR_PARAM_ST"),
          ("AtkParam_Pc.param", "ATK_PARAM_ST"), ("SpEffectParam.param", "SP_EFFECT_PARAM_ST"),
          ("Bullet.param", "BULLET_PARAM_ST"))
GAMEPARAM = "param/gameparam/gameparam.parambnd.dcx"
TALK = "script/talk/m21_00_00_00.talkesdbnd.dcx"     # the Hunter's Dream
ANIBND = "chr/c0000.anibnd.dcx"
PARTS = [f"parts/wp_a_{MODEL}{suffix}.partsbnd.dcx" for suffix in ("", "_l")]
LORE = ("A Kirkhammer reforged in the far north, where the Healing Church raised its kirk on older "
        "stones. The smith, remembered only as Véurr, left the stone block on the crag where "
        "lightning fell most often, through a whole winter of storms.\n\n"
        "Even the blade hums with it. Seat the blade in the hammer and the stone wakes: every blow "
        "sends bolt running along the ground, and brought down with all one's strength, the thunder "
        "rolls on ahead, as the northern hymns told of the old god's chariot, and the storm stays "
        "with its wielder a while. Draw the blade again, and it carries the storm away with it.")
WEAPON_IDS = [first + 100 * level for _n, first, _s, _o in VARIANTS for level in LEVELS]
OUR_JUDGES = tuple(chain["judge"] for chain in CHAINS.values()) + (COST["judge"], FLASH["judge"], SKY["judge"])


class ThunderwrightError(ValueError):
    pass


def set_game(dvdroot):
    """The dump's dvdroot_ps4 folder, for every module that reads the game's own files."""
    bbparam.GAME = anibnd.GAME = str(dvdroot).replace("\\", "/").rstrip("/") + "/"


def _game(relative):
    with open(bbparam.GAME + relative, "rb") as f:
        return f.read()


def label(name, level):
    return name + (f" +{level}" if level else "")


def chain_bullets(chain):
    """The strike bullets of a chain, in order (the launcher's HitBulletID is the first)."""
    return [chain["launcher"] + 1 + k for k in range(len(chain["strikes"]))]


# --- the moveset ------------------------------------------------------------------------------------
def _attack_judges(anim):
    return [e.ints(3)[2] for e in anim.events if e.type == ATTACK_EVENT]


def judge_groups(tae):
    """(sword judges, hammer judges) of a105, by which form lands the hit: normal-mode animations
    are the sword's and trick-mode ones the hammer's, except the transform attacks, where the form
    being drawn lands it (into hammer mode: the hammer; back to sword mode: the sword)."""
    sword, hammer = set(), set()
    for a in tae.animations:
        if a.id in TO_HAMMER:
            hammer.update(_attack_judges(a))
        elif a.id in TO_SWORD or a.id < 40000:
            sword.update(_attack_judges(a))
        else:
            hammer.update(_attack_judges(a))
    if sword & hammer:
        raise ThunderwrightError(f"judges in both forms: {sorted(sword & hammer)}")
    return sword, hammer


def impact_frame(anim):
    """The frame a hammer animation lands: its shock wave's start, else the end of its last swing."""
    attacks = [e for e in anim.events if e.type == ATTACK_EVENT]
    if not attacks:
        raise ThunderwrightError(f"a{KIRK_TAE} {anim.id} has no hit")
    waves = [e for e in attacks if e.ints(3)[2] in SHOCK_WAVES]
    if waves:
        return round(min(e.start for e in waves) * FPS)
    return round(max(e.end for e in attacks) * FPS)


def _bullet_event(aid, frame, judge, name):
    return {"anim": aid, "type": BULLET_EVENT, "group_type": 2, "frames": (frame, frame + 1),
            "params": struct.pack("<4i", HEAD, 0, judge, 0), "label": name}


def lightning_events(tae):
    """The lightning events for a105 (ability_events.insert items), type 318 from the hammer head:
    on the charged R2 set, the last frame of the slam's own attack (as the Holy Moonlight Sword's
    waves), Thunder Chariot's with its bullet cost beside it; on every other hammer animation with
    a hit but the plunge's fall, its impact. Exactly one line per animation."""
    items, costs = [], []
    for aid, judge, line in CHARGE_EVENTS:
        a = tae.anim(aid)
        attack = [e for e in a.events if e.type == ATTACK_EVENT and e.ints(3)[2] == judge]
        if len(attack) != 1:
            raise ThunderwrightError(f"a{KIRK_TAE} {aid}: no single attack with judge {judge}")
        frame = round(attack[0].end * FPS)
        items.append(_bullet_event(aid, frame, CHAINS[line]["judge"], CHAINS[line]["name"]))
        if line == "high":
            costs.append(_bullet_event(aid, frame, COST["judge"], COST["name"]))
            costs.append(_bullet_event(aid, frame, SKY["judge"], SKY["name"]))
    for aids, line in ((SMALL_ANIMS + TO_HAMMER, "small"), (MEDIUM_ANIMS, "medium"), (TO_SWORD, "draw")):
        for aid in aids:
            items.append(_bullet_event(aid, impact_frame(tae.anim(aid)), CHAINS[line]["judge"], CHAINS[line]["name"]))
    for aid in TO_HAMMER + TO_SWORD:
        costs.append(_bullet_event(aid, impact_frame(tae.anim(aid)), FLASH["judge"], FLASH["name"]))
    sent = [item["anim"] for item in items]
    hammer = {a.id for a in tae.animations if _attack_judges(a) and (a.id in TO_HAMMER or 40000 <= a.id < 50000)}
    if len(sent) != len(set(sent)) or set(sent) != hammer - set(FALLING):
        raise ThunderwrightError(f"a{KIRK_TAE}: lines on {sorted(sent)}, hammer animations {sorted(hammer)}")
    return items + costs


def _a105(anibnd_raw):
    bnd = anibnd.Bnd4Archive(dcx_decompress(anibnd_raw) if anibnd_raw[:4] == b"DCX\0" else anibnd_raw)
    entry = bnd.find(name=f"a{KIRK_TAE}.tae")
    if entry is None:
        raise ThunderwrightError(f"no a{KIRK_TAE}.tae in the animation archive")
    return bnd, entry


def moveset(anibnd_raw):
    """(a105.tae bytes with the lightning events, the a105.tae bytes given, the inserted items)."""
    _bnd, entry = _a105(anibnd_raw)
    tae = tw.read(entry.data)
    if any(e.type == BULLET_EVENT and e.ints(3)[2] in OUR_JUDGES for a in tae.animations for e in a.events):
        raise ThunderwrightError(f"a{KIRK_TAE} already has the lightning events")
    items = lightning_events(tae)
    ae.insert(tae, items)
    return tae.to_bytes(), entry.data, items


def anibnd_file(anibnd_raw):
    """`anibnd_raw` (a c0000.anibnd.dcx, the game's or one with the Sojin Chikage's a157 in) with
    the lightning events in a105.tae; nothing else in the archive changes."""
    bnd, entry = _a105(anibnd_raw)
    entry.data, _src, _items = moveset(anibnd_raw)
    return dcx_compress(bnd.to_bytes(), anibnd_raw)


# --- the params ---------------------------------------------------------------------------------------
def _open(raw):
    return Bnd4(dcx_decompress(raw))


def _shop_rows(s, ranges, variants=VARIANTS):
    """Each weapon's +0 at PRICE in every range, after the range's last row (the Sojin Chikage, if
    it is added later, goes after these)."""
    rows = sorted(s.rows)
    added = []
    for first, last in ranges:
        inside = [r for r in rows if first <= r <= last]
        template = next((r for r in inside if s.get(r, "equipType") == 0), inside[0] if inside else rows[0])
        row = (max(inside) + 1) if inside else first
        if row + len(variants) - 1 > last:
            raise ThunderwrightError(f"shop range {first}..{last} is full")
        for name, weapon, _source, _sort in variants:
            s.add(row, template, f"[Bath Messengers] {name}")
            # qwcId -1 shows the row from the start (a copied vanilla qwcId would hide it).
            for field, value in (("equipId", weapon), ("value", PRICE), ("equipType", 0), ("eventFlag", -1),
                                 ("qwcId", -1), ("sellQuantity", -1), ("mtrlId", -1)):
                s.set(row, field, value)
            added.append(row)
            row += 1
    return added


def _check_free(w, g, b, a, sp, bu):
    taken = [r for r in WEAPON_IDS if r in w.rows or r in g.rows]
    if taken:
        raise ThunderwrightError(f"weapon ids taken: {taken[:3]}")
    if any(w.get(r, "behaviorVariationId") == VAR for r in w.rows):
        raise ThunderwrightError(f"behaviour variation {VAR} taken")
    blocks = ((b, 100000000 + VAR * 1000), (a, VAR * 1000), (sp, HAMMER_EFFECT - 1), (bu, CHAINS["high"]["launcher"] - 10))
    for p, start in blocks:
        hit = [r for r in p.rows if start <= r < start + 1000]
        if hit:
            raise ThunderwrightError(f"ids taken: {hit[:3]}")
    sorts = {w.get(r, "sortId") for r in w.rows}
    if any(sort + level in sorts for _n, _f, _s, sort in VARIANTS for level in LEVELS):
        raise ThunderwrightError("sort ids taken")


def _bolt_attack(a, row, bolt, feel, name):
    """An attack row for a bullet (a bullet carries its own; nothing passes from the one that fired
    it): the Holy Moonlight wave's, which scales from the firing weapon, with only bolt at `bolt` %,
    hitting as bolt, pushing and staggering as attack row `feel`, sounding as Tiny Tonitrus."""
    a.add(row, HMS_WAVE_ATTACK, f"{NAME}: {name} {bolt} %")
    for field in ("atkPhysCorrection", "atkMagCorrection", "atkFireCorrection"):
        a.set(row, field, 0)
    a.set(row, "atkThunCorrection", bolt)
    a.set(row, "spAttribute", BOLT_SP_ATTRIBUTE)
    for field in FEEL:
        a.set(row, field, a.get(feel, field))
    for field in MATERIAL:
        a.set(row, field, a.get(TINY_TONITRUS_ATTACK, field))


def _flash_fields(bu):
    """(field, value) of the transform flash over Tiny Tonitrus's launcher."""
    return (("atkId_Bullet", -1), ("sfxId_Bullet", -1), ("HitBulletID", -1), ("spEffectIDForShooter", -1),
            ("sfxId_Hit", bu.get(FLASH["strike"], "sfxId_Hit")), ("life", FLASH["life"]),
            ("initVellocity", 0.0), ("maxVellocity", 0.0), ("minVellocity", 0.0), ("homingAngle", 0))


def _sky_fields(k):
    """(field, value) of sky bullet k over its source: no attack, linked inside the copy, ends at the bolt."""
    after = SKY["bullets"][k + 1] if k + 1 < len(SKY["bullets"]) else -1
    # The warning and the bolt unseen: with them the charged slam was a white column over a quarter
    # of the screen in the game's own picture, HDR or not (near-white 33% of it at worst, 9% without).
    unseen = (("sfxId_Bullet", -1), ("sfxId_Hit", -1)) if k >= 1 else ()
    return (("atkId_Bullet", -1), ("HitBulletID", after)) + unseen


def _bullet_behaviour(b, judge, bullet, name):
    """Behaviour judge `judge` of variation 2060 fires `bullet` (the Holy Moonlight wave's row: no cost)."""
    row = 100000000 + VAR * 1000 + judge
    b.add(row, HMS_WAVE_BEHAVIOUR, f"{NAME}: {name}")
    b.set(row, "variationId", VAR)
    b.set(row, "behaviorJudgeId", judge)
    b.set(row, "refType", 1)
    b.set(row, "refId", bullet)


def add_params(param_raw, talk_raw, anibnd_raw):
    """`param_raw` (a gameparam.parambnd.dcx) with the weapon, its behaviour variation, the
    lightning, the hammer-mode effect, the charge and the shop rows (in the ranges `talk_raw`
    opens; with a list of talk scripts, every range any of them opens, so the shop has it with or
    without a shop mod) added. The damage split follows the moveset in `anibnd_raw` (its a105.tae)."""
    from sojin.weapon import shop_ranges
    defs = load_paramdefs()
    gp = _open(param_raw)
    params = {}
    for name, st in PARAMS:
        i = gp.index(name)
        params[name.split(".")[0]] = (i, Param(gp.files[i], defs[st]))
    w, g, s, b, a, sp, bu = (params[k][1] for k in ("EquipParamWeapon", "WeaponGenParam", "ShopLineupParam",
                                                    "BehaviorParam_PC", "AtkParam_Pc", "SpEffectParam", "Bullet"))
    _check_free(w, g, b, a, sp, bu)
    _tae, src, _items = moveset(anibnd_raw)
    sword, hammer = judge_groups(tw.read(src))

    # Variation 2060: every row of the Kirkhammer's 800, its attack row split by form.
    kirk_rows = {b.get(r, "behaviorJudgeId"): r for r in b.rows if b.get(r, "variationId") == KIRK_VAR}
    for judge in OUR_JUDGES:
        if judge in kirk_rows:
            raise ThunderwrightError(f"judge {judge} is the Kirkhammer's")
    for judge, src_row in sorted(kirk_rows.items()):
        new = 100000000 + VAR * 1000 + judge
        b.add(new, src_row, f"{NAME}: " + b.name(src_row))
        b.set(new, "variationId", VAR)
        if b.get(src_row, "refType") != 0:
            continue
        src_atk, new_atk = b.get(src_row, "refId"), VAR * 1000 + judge
        a.add(new_atk, src_atk, f"{NAME}: " + a.name(src_atk))
        b.set(new, "refId", new_atk)
        if judge in hammer:
            a.set(new_atk, "atkPhysCorrection", round(a.get(src_atk, "atkPhysCorrection") * HAMMER_PHYS_SCALE))
        else:   # the sword's, and rows a105 never uses
            a.set(new_atk, "atkThunCorrection", round(a.get(src_atk, "atkThunCorrection") * SWORD_BOLT_SCALE))

    # The lines: per kind a launcher (fanned out into its lines) and its strikes, re-linked inside
    # the new block, every one on that kind's attack row.
    for chain in CHAINS.values():
        strikes = chain_bullets(chain)
        lines, first, step = chain["fan"]
        bu.add(chain["launcher"], LAUNCHER, f"{chain['name']}: launcher")
        bu.set(chain["launcher"], "HitBulletID", strikes[0])
        bu.set(chain["launcher"], "atkId_Bullet", chain["atk"])
        if chain.get("shown", 1) > 1:   # thinned: the launcher unseen too (near-white 9% to 4% at worst)
            bu.set(chain["launcher"], "sfxId_Bullet", -1)
        if lines > 1:   # the lines keep their angles: no homing on the lock-on target
            for field, value in (("numShoot", lines), ("shootAngle", first), ("shootAngleInterval", step),
                                 ("homingAngle", 0)):
                bu.set(chain["launcher"], field, value)
        if "charge" in chain:
            bu.set(chain["launcher"], "spEffectIDForShooter", chain["charge"])
        for k, (new, src_row) in enumerate(zip(strikes, chain["strikes"])):
            bu.add(new, src_row, f"{chain['name']}: strike {k + 1}")
            bu.set(new, "HitBulletID", strikes[k + 1] if k + 1 < len(strikes) else -1)
            bu.set(new, "atkId_Bullet", chain["atk"])
            bu.set(new, "hitRadius", chain["radius"])
            if k % chain.get("shown", 1):
                bu.set(new, "sfxId_Bullet", -1)
                bu.set(new, "sfxId_Hit", -1)
        _bolt_attack(a, chain["atk"], chain["bolt"], chain["feel"], chain["name"])
        _bullet_behaviour(b, chain["judge"], chain["launcher"], chain["name"])
    # Thunder Chariot's bullet cost: Tiny Tonitrus's launcher with nothing to see, hit or follow.
    bu.add(COST["bullet"], LAUNCHER, COST["name"])
    for field, value in (("atkId_Bullet", -1), ("sfxId_Bullet", -1), ("HitBulletID", -1),
                         ("spEffectIDForShooter", BULLET_COST)):
        bu.set(COST["bullet"], field, value)
    _bullet_behaviour(b, COST["judge"], COST["bullet"], COST["name"])
    bu.add(FLASH["bullet"], LAUNCHER, FLASH["name"])
    for field, value in _flash_fields(bu):
        bu.set(FLASH["bullet"], field, value)
    _bullet_behaviour(b, FLASH["judge"], FLASH["bullet"], FLASH["name"])
    for k, (new, src_row) in enumerate(zip(SKY["bullets"], SKY["sources"])):
        bu.add(new, src_row, f"{SKY['name']} {k + 1}")
        for field, value in _sky_fields(k):
            bu.set(new, field, value)
    _bullet_behaviour(b, SKY["judge"], SKY["bullets"][0], SKY["name"])
    sp.add(BULLET_COST, TONITRUS_CHARGING, f"{NAME}: Thunder Chariot's Quicksilver Bullet")
    sp.set(BULLET_COST, "addBulletNum", -BULLETS_TAKEN)
    sp.set(BULLET_COST, "replaceSpEffectId", STORED_CHARGE)

    sp.add(HAMMER_EFFECT, HAMMER_EFFECT_SRC, f"{NAME}: hammer mode")
    sp.set(HAMMER_EFFECT, "validCond_PCWeponState", TRICK_ONLY)
    sp.set(HAMMER_EFFECT, "stateInfo", HAMMER_LOOK)
    sp.set(HAMMER_EFFECT, "spAttribute", BOLT_SP_ATTRIBUTE)
    sp.add(STORM_EFFECT, HAMMER_EFFECT_SRC, f"{NAME}: the hammer's storm")
    sp.set(STORM_EFFECT, "validCond_PCWeponState", TRICK_ONLY)
    sp.set(STORM_EFFECT, "stateInfo", STORM_LOOK)
    sp.add(STORED_CHARGE, CHARGED_TONITRUS, f"{NAME}: charge")
    sp.set(STORED_CHARGE, "effectEndurance", CHARGE_TIME)
    sp.set(STORED_CHARGE, "maxDurability", 0)
    sp.add(DRAW_CHARGE, CHARGED_TONITRUS, f"{NAME}: Static Draw's charge")
    sp.set(DRAW_CHARGE, "effectEndurance", DRAW_CHARGE_TIME)
    sp.set(DRAW_CHARGE, "maxDurability", 0)

    for name, first, source, sort in VARIANTS:
        for level in LEVELS:
            new, src_row = first + 100 * level, source + 100 * level
            w.add(new, src_row, label(name, level))   # the Kirkhammer's motion category and requirements
            w.set(new, "equipModelId", MODEL)
            w.set(new, "behaviorVariationId", VAR)
            w.set(new, "attackBasePhysics", physical(w.get(src_row, "attackBasePhysics")))
            w.set(new, "attackBaseThunder", bolt(level))
            w.set(new, "correctFaith", w.get(src_row, "correctStrength"))    # Arcane as strong as Strength
            w.set(new, "correctAgility", NO_SKILL_SCALING)
            w.set(new, "properFaith", ARCANE_NEEDED)
            w.set(new, "isEnhance", NO_PAPERS)
            w.set(new, "residentSpEffectId1", HAMMER_EFFECT)    # the Kirkhammer's 6050 stays in slot 0
            w.set(new, "residentSpEffectId2", STORM_EFFECT)
            w.set(new, "isAttributeWep", 0)     # as every game weapon with a built-in element
            w.set(new, "sortId", sort + level)
            w.set(new, "originEquipWep", first + max(level - 1, 0) * 100)
            g.add(new, src_row, label(name, level))   # that Kirkhammer's gem slots
            g.set(new, "wepParamId", new)
    talks = talk_raw if isinstance(talk_raw, (list, tuple)) else [talk_raw]
    _shop_rows(s, sorted({r for talk in talks for r in shop_ranges(talk)}))
    for i, p in params.values():
        gp.files[i] = p.to_bytes()
    return dcx_compress(gp.to_bytes(), param_raw)


def has_weapon(param_raw):
    defs = load_paramdefs()
    gp = _open(param_raw)
    w = Param(gp.files[gp.index("EquipParamWeapon.param")], defs["EQUIP_PARAM_WEAPON_ST"])
    return any(r in w.rows for r in WEAPON_IDS)


def add_text(msg_raw):
    """`msg_raw` (an item.msgbnd.dcx) with the weapon's names and lore (English in every language)."""
    msg = _open(msg_raw)
    ni, li = msg.index("武器名.fmg"), msg.index("武器うんちく.fmg")
    names, lore = Fmg(msg.files[ni]), Fmg(msg.files[li])
    for name, first, _source, _sort in VARIANTS:
        for level in LEVELS:
            names.entries[first + level * 100] = label(name, level)
            lore.entries[first + level * 100] = LORE
    msg.files[ni], msg.files[li] = names.to_bytes(), lore.to_bytes()
    return dcx_compress(msg.to_bytes(), msg_raw)


# --- checks -------------------------------------------------------------------------------------------
def _close(x, y):
    return abs(x - y) < 1e-5


def verify(param_in, param_out, anibnd_in, anibnd_out):
    """Reads the made files back against their inputs; ThunderwrightError if anything differs from
    the plan. Every original row and archive file is byte-identical; the new rows are their
    sources with only the planned fields changed; a105 is the given one plus the lightning events."""
    defs = load_paramdefs()
    before, after = _open(param_in), _open(param_out)
    p0 = {n.split(".")[0]: Param(before.files[before.index(n)], defs[st]) for n, st in PARAMS}
    p1 = {n.split(".")[0]: Param(after.files[after.index(n)], defs[st]) for n, st in PARAMS}
    for key in p0:
        changed = [r for r in p0[key].rows if p0[key].rows[r] != p1[key].rows.get(r)]
        if changed:
            raise ThunderwrightError(f"{key}: original rows changed: {changed[:3]}")
    for name in before.names:
        if not any(name.endswith(n) for n, _st in PARAMS) and before.files[before.index(name)] != after.files[after.index(name)]:
            raise ThunderwrightError(f"{name} changed")
    w, b, a, sp, bu = (p1[k] for k in ("EquipParamWeapon", "BehaviorParam_PC", "AtkParam_Pc", "SpEffectParam", "Bullet"))

    def diff(p, new, src):
        return {f[0] for f in p.fields if p.get(new, f[0]) != p.get(src, f[0])}

    _tae, src_tae, items = moveset(anibnd_in)
    sword, hammer = judge_groups(tw.read(src_tae))
    for judge in sword | hammer:
        row = 100000000 + KIRK_VAR * 1000 + judge
        if row not in b.rows:
            continue    # a105 names it, variation 800 has no row (52600/52603's 450: never played)
        new_atk, src_atk = VAR * 1000 + judge, b.get(row, "refId")
        want = {"atkPhysCorrection"} if judge in hammer else {"atkThunCorrection"}
        got = diff(a, new_atk, src_atk)
        if not got <= want:
            raise ThunderwrightError(f"attack {new_atk}: {sorted(got)} changed")
        if judge in sword and a.get(new_atk, "atkThunCorrection") != round(a.get(src_atk, "atkThunCorrection") * SWORD_BOLT_SCALE):
            raise ThunderwrightError(f"sword attack {new_atk} is not at {SWORD_BOLT_SCALE} bolt")

    bullets = []
    for chain in CHAINS.values():
        seen, r = [], bu.get(chain["launcher"], "HitBulletID")
        while r != -1:
            seen.append(r)
            if bu.get(r, "atkId_Bullet") != chain["atk"] or not _close(bu.get(r, "hitRadius"), chain["radius"]):
                raise ThunderwrightError(f"bullet {r} is not on attack {chain['atk']} at {chain['radius']} m")
            r = bu.get(r, "HitBulletID")
        if seen != chain_bullets(chain):
            raise ThunderwrightError(f"chain {chain['judge']} walks {seen}")
        lines, first, step = chain["fan"]
        fan = (bu.get(chain["launcher"], "numShoot"), bu.get(chain["launcher"], "shootAngle"),
               bu.get(chain["launcher"], "shootAngleInterval"))
        if fan != ((lines, first, step) if lines > 1 else (1, 0, 0)):
            raise ThunderwrightError(f"launcher {chain['launcher']} fans {fan}")
        planned = {"HitBulletID", "atkId_Bullet"} | ({"sfxId_Bullet"} if chain.get("shown", 1) > 1 else set()) | ({"numShoot", "shootAngle", "shootAngleInterval", "homingAngle"} if lines > 1 else set())
        planned |= {"spEffectIDForShooter"} if "charge" in chain else set()
        if not diff(bu, chain["launcher"], LAUNCHER) <= planned:
            raise ThunderwrightError(f"launcher {chain['launcher']}: {sorted(diff(bu, chain['launcher'], LAUNCHER))} changed")
        if bu.get(chain["launcher"], "spEffectIDForShooter") != chain.get("charge", bu.get(LAUNCHER, "spEffectIDForShooter")):
            raise ThunderwrightError(f"launcher {chain['launcher']} charges the wrong effect")
        for k, (new, src_row) in enumerate(zip(seen, chain["strikes"])):
            hidden = k % chain.get("shown", 1) != 0
            if hidden and (bu.get(new, "sfxId_Bullet"), bu.get(new, "sfxId_Hit")) != (-1, -1):
                raise ThunderwrightError(f"strike {new} still shows its effects")
            if not diff(bu, new, src_row) <= {"HitBulletID", "atkId_Bullet", "hitRadius"} | (
                    {"sfxId_Bullet", "sfxId_Hit"} if hidden else set()):
                raise ThunderwrightError(f"strike {new}: {sorted(diff(bu, new, src_row))} changed")
        row = chain["atk"]
        if a.get(row, "atkPhysCorrection") or a.get(row, "atkThunCorrection") != chain["bolt"]:
            raise ThunderwrightError(f"attack {row} is not bolt-only at {chain['bolt']} %")
        got = diff(a, row, HMS_WAVE_ATTACK)
        if not got <= {"atkMagCorrection", "atkFireCorrection", "atkThunCorrection", "spAttribute", *FEEL, *MATERIAL} \
                or any(a.get(row, f) != a.get(chain["feel"], f) for f in FEEL):
            raise ThunderwrightError(f"attack {row}: {sorted(got)} changed")
        beh = 100000000 + VAR * 1000 + chain["judge"]
        if (b.get(beh, "refType"), b.get(beh, "refId"), b.get(beh, "stamina")) != (1, chain["launcher"], 0):
            raise ThunderwrightError(f"behaviour {beh} does not fire {chain['launcher']} for free")
        for var in (KIRK_VAR, 0):
            if 100000000 + var * 1000 + chain["judge"] in b.rows:
                raise ThunderwrightError(f"variation {var} has behaviour judge {chain['judge']}: its a105 would fire it")
        bullets += [chain["launcher"], *seen]
    r = COST["bullet"]
    if diff(bu, r, LAUNCHER) - {"atkId_Bullet", "sfxId_Bullet", "HitBulletID", "spEffectIDForShooter"} or \
            (bu.get(r, "atkId_Bullet"), bu.get(r, "sfxId_Bullet"), bu.get(r, "HitBulletID"),
             bu.get(r, "spEffectIDForShooter"), bu.get(r, "numShoot")) != (-1, -1, -1, BULLET_COST, 1):
        raise ThunderwrightError(f"bullet-cost bullet {r} is not an unseen, harmless single bullet")
    beh = 100000000 + VAR * 1000 + COST["judge"]
    if (b.get(beh, "refType"), b.get(beh, "refId"), b.get(beh, "stamina")) != (1, r, 0):
        raise ThunderwrightError(f"behaviour {beh} does not fire {r}")
    for var in (KIRK_VAR, 0):
        if 100000000 + var * 1000 + COST["judge"] in b.rows:
            raise ThunderwrightError(f"variation {var} has behaviour judge {COST['judge']}")
    if diff(sp, BULLET_COST, TONITRUS_CHARGING) != {"addBulletNum", "replaceSpEffectId"} or \
            (sp.get(BULLET_COST, "addBulletNum"), sp.get(BULLET_COST, "replaceSpEffectId")) != (-BULLETS_TAKEN, STORED_CHARGE):
        raise ThunderwrightError("the bullet cost differs from 6030 beyond taking a bullet and charging")
    bullets.append(r)
    r = FLASH["bullet"]
    want = dict(_flash_fields(bu))
    if diff(bu, r, LAUNCHER) - set(want) or any(bu.get(r, f) != v and not (isinstance(v, float) and _close(bu.get(r, f), v))
                                              for f, v in want.items()):
        raise ThunderwrightError(f"flash bullet {r} is not a harmless bolt on the spot")
    beh = 100000000 + VAR * 1000 + FLASH["judge"]
    if (b.get(beh, "refType"), b.get(beh, "refId"), b.get(beh, "stamina")) != (1, r, 0):
        raise ThunderwrightError(f"behaviour {beh} does not fire {r}")
    for var in (KIRK_VAR, 0):
        if 100000000 + var * 1000 + FLASH["judge"] in b.rows:
            raise ThunderwrightError(f"variation {var} has behaviour judge {FLASH['judge']}")
    bullets.append(r)
    for k, (new, src_row) in enumerate(zip(SKY["bullets"], SKY["sources"])):
        want = dict(_sky_fields(k))
        if diff(bu, new, src_row) - set(want) or any(bu.get(new, f) != v for f, v in want.items()):
            raise ThunderwrightError(f"sky bullet {new} is not the fishman's {src_row} without attack")
        bullets.append(new)
    beh = 100000000 + VAR * 1000 + SKY["judge"]
    if (b.get(beh, "refType"), b.get(beh, "refId"), b.get(beh, "stamina")) != (1, SKY["bullets"][0], 0):
        raise ThunderwrightError(f"behaviour {beh} does not fire {SKY['bullets'][0]}")
    for var in (KIRK_VAR, 0):
        if 100000000 + var * 1000 + SKY["judge"] in b.rows:
            raise ThunderwrightError(f"variation {var} has behaviour judge {SKY['judge']}")
    if len(bullets) != len(set(bullets)):
        raise ThunderwrightError("the lines share bullets")
    if diff(sp, HAMMER_EFFECT, HAMMER_EFFECT_SRC) != {"validCond_PCWeponState", "stateInfo", "spAttribute"}:
        raise ThunderwrightError("hammer-mode effect differs from 6033 beyond its three fields")
    if diff(sp, STORM_EFFECT, HAMMER_EFFECT_SRC) != {"validCond_PCWeponState", "stateInfo"} or             (sp.get(STORM_EFFECT, "validCond_PCWeponState"), sp.get(STORM_EFFECT, "stateInfo")) != (TRICK_ONLY, STORM_LOOK):
        raise ThunderwrightError("the storm effect differs from 6033 beyond its look in trick mode")
    if diff(sp, STORED_CHARGE, CHARGED_TONITRUS) != {"effectEndurance", "maxDurability"} or not _close(sp.get(STORED_CHARGE, "effectEndurance"), CHARGE_TIME):
        raise ThunderwrightError("the charge differs from 6032 beyond its time and durability")
    if diff(sp, DRAW_CHARGE, CHARGED_TONITRUS) != {"effectEndurance", "maxDurability"} or not _close(sp.get(DRAW_CHARGE, "effectEndurance"), DRAW_CHARGE_TIME):
        raise ThunderwrightError("Static Draw's charge differs from 6032 beyond its time and durability")
    for level, new, src_row in ((level, first + 100 * level, source + 100 * level)
                                for _n, first, source, _o in VARIANTS for level in LEVELS):
        got = diff(w, new, src_row)
        planned = {"equipModelId", "behaviorVariationId", "attackBasePhysics", "attackBaseThunder", "correctFaith", "correctAgility", "properFaith",
                   "isEnhance", "residentSpEffectId1", "residentSpEffectId2", "isAttributeWep", "sortId", "originEquipWep"}
        if not got <= planned:
            raise ThunderwrightError(f"weapon +{level}: {sorted(got - planned)} changed")
        if (w.get(new, "properFaith"), w.get(new, "isEnhance")) != (ARCANE_NEEDED, NO_PAPERS):
            raise ThunderwrightError(f"weapon +{level} does not need Arcane {ARCANE_NEEDED} or takes papers")
        if (w.get(new, "correctFaith"), w.get(new, "correctAgility")) != (w.get(src_row, "correctStrength"), 0):
            raise ThunderwrightError(f"weapon +{level} does not scale with Strength and Arcane alone")
        if (w.get(new, "residentSpEffectId1"), w.get(new, "residentSpEffectId2")) != (HAMMER_EFFECT, STORM_EFFECT):
            raise ThunderwrightError(f"weapon +{level} lacks the hammer's look or storm")
        if w.get(new, "attackBaseThunder") != bolt(level):
            raise ThunderwrightError(f"weapon +{level} bolt is {w.get(new, 'attackBaseThunder')}")
        if w.get(new, "attackBasePhysics") != physical(w.get(src_row, "attackBasePhysics")):
            raise ThunderwrightError(f"weapon +{level} physical is {w.get(new, 'attackBasePhysics')}")
        if w.get(new, "equipModelId") != MODEL:
            raise ThunderwrightError(f"weapon +{level} is not model {MODEL}")
    if any(w.get(r, "equipModelId") == MODEL for r in p0["EquipParamWeapon"].rows):
        raise ThunderwrightError(f"model {MODEL} taken")

    # The archive: only a105 changed, by exactly the lightning events.
    b0 = anibnd.Bnd4Archive(dcx_decompress(anibnd_in))
    b1 = anibnd.Bnd4Archive(dcx_decompress(anibnd_out))
    if [e.name for e in b0.entries] != [e.name for e in b1.entries]:
        raise ThunderwrightError("the animation archive's file list changed")
    for e0, e1 in zip(b0.entries, b1.entries):
        if e0.name.endswith(f"a{KIRK_TAE}.tae"):
            continue
        if e0.data != e1.data:
            raise ThunderwrightError(f"{e0.name} changed")
    made = tw.read(b1.find(name=f"a{KIRK_TAE}.tae").data)
    src = tw.read(src_tae)
    want = {}
    for item in items:
        want.setdefault(item["anim"], []).append((item["type"], item["params"]))
    for x, y in zip(src.animations, made.animations):
        if x.id != y.id or x.mini.data != y.mini.data:
            raise ThunderwrightError("a105's animation list changed")
        old, new = y.events[:len(x.events)], y.events[len(x.events):]
        if len(old) != len(x.events) or any(e.type != f.type or e.start != f.start or e.end != f.end or
                                            not ae._same_params(e.params, f.params) for e, f in zip(old, x.events)):
            raise ThunderwrightError(f"a105 {x.id}: its own events changed")
        if sorted((e.type, e.params[:16]) for e in new) != sorted(want.get(x.id, [])):
            raise ThunderwrightError(f"a105 {x.id}: added {[(e.type, e.ints(4)) for e in new]}")
    if len(made.animations) != len(src.animations):
        raise ThunderwrightError("a105 has more or fewer animations")


# --- the model --------------------------------------------------------------------------------------
TEX_PATH = (f"\\tex\\WP_A_{KIRK_MODEL}_".encode("utf-16-le"), f"\\tex\\WP_A_{MODEL}_".encode("utf-16-le"))
TEXTURES = 4    # _a, _n, _r, _s: each mesh names all four
# The glowing runes: the meshes move onto the game's own emissive glow material (what the
# Kirkhammer's P[Weapon]_[ARSN]_NoCM material draws, plus an emissive texture and bloom; characters
# such as c1040 use it), with an emissive texture after the detail normal map, as the game's own
# glow materials list it, and a lower glow scale than c1040's.
GLOW_MTD = "N:\\SPRJ\\data\\Material\\mtd\\character\\C[ARSN]_em_Glow.mtd"
GLOW_SLOT, GLOW_SCALE = 5, 0.5   # c1040's 1.0 was too bright on the runes; c1210 uses 0.2


def _parts(suffix):
    """(raw, data, [(flags, id, name, file)]) of the Kirkhammer's part archive."""
    raw = _game(f"parts/wp_a_{KIRK_MODEL}{suffix}.partsbnd.dcx")
    data = dcx_decompress(raw)
    src = Bnd4(data)
    return raw, data, [(data[0x40 + i * 0x24], fid, name, f) for i, (fid, name, f) in enumerate(zip(src.ids, src.names, src.files))]


def _emissive_path(mesh):
    """The emissive texture's path for a mesh: its albedo's, _a as _e (_a_l as _e_l)."""
    from thunderwright import rune_iron as rune
    import flver
    albedo = next(t["path"] for t in flver.Flver(mesh).textures() if t["type"] == "g_DiffuseTexture")
    folder, file = albedo.rsplit("\\", 1)
    stem, ext = file.rsplit(".", 1)
    return f"{folder}\\{rune.emissive_name(stem)}.{ext}"


def model_files(rune_iron=True):
    """Model 1032 from the Kirkhammer's parts (1031), both detail levels: the same meshes, part
    animations and collision, its textures renamed and (rune_iron) made rune-iron, its runes lit
    through the glow material and an emissive texture of their own."""
    from sojin.weapon import write_bnd4
    from ps4_texture import Ps4Tpf
    from thunderwright import rune_iron as rune
    import flver
    files = {}
    for suffix, relative in zip(("", "_l"), PARTS):
        raw, data, entries = _parts(suffix)
        if write_bnd4(data, entries) != data:   # the writer must rebuild the game's own archive
            raise ThunderwrightError(f"the part archive writer does not reproduce wp_a_{KIRK_MODEL}{suffix}")
        made = []
        for flags, fid, name, f in entries:
            low = name.lower()
            if low.endswith(".tpf"):
                tpf = Ps4Tpf(f)
                if rune_iron:
                    rune.retexture(tpf)
                tpf.rename(f"WP_A_{KIRK_MODEL}_", f"WP_A_{MODEL}_")
                f = tpf.to_bytes()
            elif low.endswith(".flver"):
                if f.count(TEX_PATH[0]) != TEXTURES:
                    raise ThunderwrightError(f"{name} does not name the {TEXTURES} Kirkhammer textures")
                f = f.replace(*TEX_PATH)
                if rune_iron:
                    f = flver.glow_material(f, 0, GLOW_MTD, _emissive_path(f), GLOW_SLOT, GLOW_SCALE)
            made.append((flags, fid, name.replace(f"WP_A_{KIRK_MODEL}", f"WP_A_{MODEL}"), f))
        files[relative] = dcx_compress(write_bnd4(data, made), raw)
    return files


def verify_model(files, rune_iron=True):
    """The made model against the Kirkhammer's: the same parts; meshes differing only in their
    texture paths and (rune_iron) the glow material; textures renamed, of the same formats and
    sizes; the sword's half of each texture untouched and the rest changed, and the emissive
    texture dark there (rune_iron), or every texel the same (not)."""
    from ps4_texture import Ps4Tpf
    from thunderwright import rune_iron as rune
    import flver
    for suffix, relative in zip(("", "_l"), PARTS):
        _raw, _data, src = _parts(suffix)
        m = Bnd4(dcx_decompress(files[relative]))
        if m.ids != [fid for _f, fid, _n, _d in src]:
            raise ThunderwrightError(f"wp_a_{MODEL}{suffix}: parts {m.ids}")
        for (_f, fid, name, old), new_name, new in zip(src, m.names, m.files):
            if new_name != name.replace(f"WP_A_{KIRK_MODEL}", f"WP_A_{MODEL}"):
                raise ThunderwrightError(f"wp_a_{MODEL}{suffix} part {fid} is named {new_name}")
            low = name.lower()
            if low.endswith(".flver"):
                renamed = old.replace(*TEX_PATH)
                if not rune_iron:
                    if new != renamed or new.count(TEX_PATH[1]) != TEXTURES:
                        raise ThunderwrightError(f"{new_name}: changed beyond its texture paths")
                    continue
                try:
                    flver.check_glow(renamed, new, 0, GLOW_MTD, _emissive_path(renamed), GLOW_SLOT, GLOW_SCALE)
                except flver.FlverError as error:
                    raise ThunderwrightError(f"{new_name}: {error}") from None
            elif low.endswith(".tpf"):
                a, b = Ps4Tpf(old), Ps4Tpf(new)
                if len(b.textures) != len(a.textures) + rune_iron:
                    raise ThunderwrightError(f"{new_name}: {len(b.textures)} textures")
                if rune_iron:
                    albedo = next(t for t in b.textures if rune.role(t.name) == "_a")
                    glow = b.textures[-1]
                    top = round(rune.HEAD_TOP * glow.height) // 4 * 4
                    if glow.name != rune.emissive_name(albedo.name) or \
                            (glow.dxgi, glow.width, glow.height, glow.mipmaps) != (albedo.dxgi, albedo.width, albedo.height, albedo.mipmaps):
                        raise ThunderwrightError(f"{glow.name}: not an emissive texture shaped like {albedo.name}")
                    if glow.image().convert("RGB").crop((0, 0, glow.width, top)).getbbox() or \
                            not glow.image().convert("RGB").getbbox():
                        raise ThunderwrightError(f"{glow.name}: lit outside the hammer head, or not at all")
                for x, y in zip(a.textures, b.textures):
                    if y.name != x.name.replace(f"WP_A_{KIRK_MODEL}_", f"WP_A_{MODEL}_") or \
                            (x.dxgi, x.width, x.height, x.mipmaps, x.size) != (y.dxgi, y.width, y.height, y.mipmaps, y.size):
                        raise ThunderwrightError(f"{y.name}: not {x.name} renamed")
                    if not rune_iron:
                        if x.mips != y.mips:
                            raise ThunderwrightError(f"{y.name}: its texels changed")
                        continue
                    top = round(rune.HEAD_TOP * x.height) // 4 * 4    # whole blocks above the head
                    if x.mips[0][:top // 4 * (x.width // 4) * x.block] != y.mips[0][:top // 4 * (x.width // 4) * x.block]:
                        raise ThunderwrightError(f"{y.name}: the sword's half changed")
                    if x.mips[0] == y.mips[0]:
                        raise ThunderwrightError(f"{y.name}: not made rune-iron")
            elif new != old:
                raise ThunderwrightError(f"{new_name} changed")


def make(dvdroot, param_raw=None, talk_raw=None, anibnd_raw=None, msgs=None):
    """{game path: bytes} of every file. Each input defaults to the dump's own file; pass a mod's
    (ShopEdit's gameparam and talk script, an animation archive with the Sojin Chikage's a157) to
    build on it. msgs: {language: item.msgbnd bytes} (default: every language in the dump)."""
    set_game(dvdroot)
    param_raw = param_raw or _game(GAMEPARAM)
    talk_raw = talk_raw or _game(TALK)
    anibnd_raw = anibnd_raw or _game(ANIBND)
    for relative in PARTS:
        if os.path.exists(bbparam.GAME + relative):
            raise ThunderwrightError(f"the game has a {relative}")
    files = {GAMEPARAM: add_params(param_raw, talk_raw, anibnd_raw), ANIBND: anibnd_file(anibnd_raw)}
    files.update(model_files())
    if msgs is None:
        msgs = {}
        for lang in sorted(os.listdir(bbparam.GAME + "msg")):
            relative = f"msg/{lang}/item.msgbnd.dcx"
            if os.path.exists(bbparam.GAME + relative):
                msgs[lang] = _game(relative)
    for lang, raw in msgs.items():
        files[f"msg/{lang}/item.msgbnd.dcx"] = add_text(raw)
    verify(param_raw, files[GAMEPARAM], anibnd_raw, files[ANIBND])
    verify_model(files)
    # The sky lightning's effects in the common bank; without them the weapon still works, the
    # bolt just shows only in the Fishing Hamlet.
    try:
        common_raw, source_raw = _game(sky.COMMON), _game(sky.SOURCE)
        files[sky.COMMON], _added = sky.common_bank(common_raw, source_raw)
        sky.verify(common_raw, files[sky.COMMON], source_raw)
    except (sky.SkyError, OSError, ValueError, KeyError, struct.error) as error:
        files.pop(sky.COMMON, None)
        print(f"{NAME}: sky lightning shows only in the Fishing Hamlet ({error})", file=sys.stderr)
    return files
