# SPDX-License-Identifier: GPL-2.0-or-later
"""Sojin Chikage abilities (plans/sojin-chikage.md 1.1): Blood Rhythm, Blood Crescent, Bankai.

Game data only. add_abilities(params) adds new SpEffect / Bullet / AtkParam_Pc / BehaviorParam_PC
rows in the checked-free blocks, each copied from the closest real row of the game, hooks Blood
Rhythm into the weapon's own trick-mode attack rows (variation 2030) when they are present, and
returns what must also happen outside the params: the TAE events (exact type, params, frames,
copied from which real event) and the build.py changes needed to integrate it.

Findings and evidence: abilities-notes.md. Self-test: python abilities.py  (read-only on the game;
it loads ShopEdit's gameparam and works on in-memory copies). python abilities.py --json prints the
description returned by add_abilities.
"""
import copy, json, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bbparam import Param, load_paramdefs, open_bnd

def vanilla_params():
    """The dump's own gameparam (bbparam.GAME, set by weapon.set_game)."""
    import bbparam
    return bbparam.GAME + "param/gameparam/gameparam.parambnd.dcx"


PARAMS = {"SpEffectParam": "SP_EFFECT_PARAM_ST", "Bullet": "BULLET_PARAM_ST",
          "AtkParam_Pc": "ATK_PARAM_ST", "BehaviorParam_PC": "BEHAVIOR_PARAM_ST"}

VAR = 2030                                    # Sojin Chikage's behaviour variation
SP_BLOCK = (2030000, 2030999)                 # free SpEffect ids (checked)
BULLET_BLOCK = (2030000, 2030999)             # free Bullet ids (checked)
BLOOD_HIT = 6400                              # Chikage's trick-mode blood hit (registBlood 30)
TRICK_STATE = 2                               # validCond_PCWeponState of trick mode (as 6740)

# --- Twin blades (balance, 2026-11-01 play tests) -----------------------------------------------
# The twin moveset lands about 1.5x as many hits per second as Chikage's transformed moveset, so
# its hits get their own blood hit with half of Chikage's bleed, and its own HP drain: Chikage's
# 6740 (0.85 %/s) took half the HP in a minute of standing in blood form. At 20 (Chikage's bleed
# per second) plus Rhythm and Bankai, Old Yharnam enemies bled out about every second hit; at 15 a
# blood loss (Chikage's own, 10 % max HP + 100) takes about 12 hits on 180 resistance.
TWIN_BLOOD_HIT, TWIN_BLEED = 2030031, 15      # copy of 6400, registBlood 30 -> 15
# Blood loss: Chikage's 10 % max HP + 100 was most of an Old Yharnam enemy (27-350 HP) and still
# too strong in the third play test; the Sojin weapons' own blood hits deal 6 % + 50 (a 200 HP
# enemy loses 62, the Blood-starved Beast 170 of 2000). Chikage's own 6400 is not touched.
BLOOD_LOSS_RATE, BLOOD_LOSS_POINT = 6.0, 50
# The transform back to the katana: one committed cut, a little above a twin hit (Chikage's 30
# made it the weapon's biggest bleed hit).
BACK_BLOOD_HIT, BACK_BLEED = 2030032, 20      # copy of 6400, registBlood 30 -> 20
# 0.4 %/s with Bankai's heal on hit was no risk at all (third play test): 0.6, still under Chikage's.
TWIN_DRAIN, TWIN_DRAIN_RATE = 2030030, 0.6    # copy of 6740 (the weapon's resident effect), 0.85 -> 0.6 %/s
BLOOD_HITS = (BLOOD_HIT, TWIN_BLOOD_HIT, BACK_BLOOD_HIT)   # blood-hit attacks: twin blades, transform back

# --- Blood Rhythm -------------------------------------------------------------------------------
# Five independent tiers. Tier k is applied to the attacker on a hit while tier k-1 is active, so
# after n hits tiers 1..n are all active; every hit refreshes them; all run out 3 s after the last
# hit (at 5 s they never ran out in a fight, so the +20 % was always on). The tiers' attack-power
# factors multiply to 1 + 0.04 n. Damage only: its bleed (+1 a stack) made blood loss come too
# fast. Full Rhythm (tier 5) keeps Bankai ready (BANKAI_READY).
RHYTHM = [2030001, 2030002, 2030003, 2030004, 2030005]            # stack tiers (on the attacker)
RHYTHM_STACK_S, RHYTHM_PER_STACK = 3.0, 0.04
RHYTHM_FACTORS = [(1 + RHYTHM_PER_STACK * k) / (1 + RHYTHM_PER_STACK * (k - 1)) for k in range(1, 6)]
RHYTHM_SLOTS = ("spEffectId0", "spEffectId2", "spEffectId3")     # first free one gets RHYTHM[0]
# HUD icons (SpEffect iconId; the game's buff pictures are 8800-8816, other ids show a co-op bell
# or nothing). The HUD shows one icon per iconId, so tiers 1-4 share the orange attack-up icon
# (only blood gems use it, and gems show none) and full Rhythm (tier 5) adds the red blood-up icon.
RHYTHM_ICON, RHYTHM_MAX_ICON = 8816, 8811

# --- Blood Crescent -----------------------------------------------------------------------------
CRESCENT_JUDGE = 591                          # free in variations 200 and 400 (HMS uses 590-592)
CRESCENT_BEHAVIOR = 100000000 + VAR * 1000 + CRESCENT_JUDGE      # 102030591
CRESCENT_ATK = VAR * 1000 + CRESCENT_JUDGE                        # 2030591
CRESCENT_LAUNCH, CRESCENT_FLIGHT = 2030010, 2030011
CRESCENT_SPEED, CRESCENT_RANGE_M = 20.0, 8.0
CRESCENT_MV = 85                              # % of AR (was 130, before the twin hits were scaled)

# --- Bankai -------------------------------------------------------------------------------------
# Bankai must be earned: it works only after full Blood Rhythm. Tier 5 renews BANKAI_READY every
# second; it lasts 4 s, long enough to go back to the katana and cast Bankai from there (at 10 s,
# with tier 5's own life on top, Bankai stayed ready about 15 s after the last hit, and every R2 R2
# finisher and L2 in that time cost HP). Every Bankai effect waits for it the way the game's DLC
# beast effects wait for each other (252 is valid only while an effect with stateInfo 290, 240,
# is on): validCond_StateInfo = READY_STATE. That condition only holds while BANKAI_READY lasts, so
# the animation does not give the 30 s effects itself: it gives short starters, valid only while
# ready, that give them once. A cycle effect ticks as it starts and then every motionInterval (the
# game's 3240 and 5290-5299 have intervals longer than their lives, so only that first tick ever
# fires): with an interval longer than the starter's life it gives its effect once. At every 0.1 s
# for 0.5 s it gave it up to six times, and the heal and bleed carriers seem to stack: heal and
# bleed far above their values.
# The 30 s work only with blood in the blades. A 30 s effect with the trick-mode condition was
# rejected in game (it is given during the transform attack, before the weapon counts as
# transformed), so the 30 s effects carry no condition and what they give is checked as it is
# given: BANKAI_POWER gives BANKAI_TWIN (power and bleed, trick mode only) every second, for one
# second, so the two never overlap; the heal on hit is trick mode only. Before, the 30 s ran in
# katana form with no drain, the better place to use it. No extra drain: with the doubled drain
# the 30 s cost about a third of the HP bar for +10 % damage.
BANKAI_POWER = 2030100      # 30 s: gives BANKAI_TWIN every second; nothing of its own (the HUD timer)
BANKAI_TWIN = 2030140       # 1 s, trick mode only: x1.10 attack power, each hit -> BANKAI_BLEED
BANKAI_LEECH = 2030101      # 30 s carrier: each hit -> BANKAI_HEAL
BANKAI_HEAL = 2030102       # instant heal of the attacker, 0.2 % max HP, trick mode only (a hit on each enemy heals)
BANKAI_BLEED = 2030104      # +5 bleed on the target (15 + 5 = 20 a twin hit during Bankai)
BANKAI_READY = 2030106      # 4 s marker of full Rhythm (stateInfo READY_STATE); its icon says Bankai is ready
# Three Bankai, one per input, all with full Rhythm only and all paying in HP:
#   Awakening (L1 then R1, the transform attack from the katana): the 30 s effects above. Full cost.
#   Crimson Moon (R2 R2 in blood form: the second R2, 41100, attack 510 and the Blood Crescent):
#     for 1.2 s, x1.6 damage and +15 bleed a hit: the finisher and its Crescent land as one burst
#     (15 + 15 a hit: its two hits stay under an Old Yharnam enemy's 180 resistance). Half the cost:
#     it buys about two R1 hits of damage, on the R2 R2 every player uses.
#   Blood Ward (L2 in blood form, Blade of Mercy's 46000, attack 930): 20 s of a fifth less damage
#     taken (a quarter was the best value for HP of the three). Half the cost.
# Without full Rhythm the three moves are the plain moves and cost nothing.
MOON_SURGE = 2030130        # 1.2 s: x1.6 attack power
MOON_BLOOD = 2030131        # 1.2 s carrier: each hit -> MOON_BLEED
MOON_BLEED = 2030132        # +15 bleed on the target
WARD = 2030133              # 20 s: x0.80 damage taken
BANKAI_START = {BANKAI_POWER: 2030107, BANKAI_LEECH: 2030108,     # starters
                MOON_SURGE: 2030137, MOON_BLOOD: 2030138, WARD: 2030139}
MOON_S, MOON_POWER_RATE, MOON_BLEED_ADD = 1.2, 1.6, 15
WARD_S, WARD_CUT = 20.0, 0.80
WARD_CUTS = ("slashDamageCutRate", "blowDamageCutRate", "thrustDamageCutRate", "neutralDamageCutRate",
             "magicDamageCutRate", "fireDamageCutRate", "thunderDamageCutRate")
READY_STATE = 89            # a stateInfo no SpEffect of the game uses
BANKAI_READY_S, BANKAI_START_S, BANKAI_START_TICK = 4.0, 0.5, 1.0
# HP cost ~ 20 % of current HP: twenty instant effects of 1 % max HP, each only if HP >= its band
# (conditionHpRate 100, 95, .. 5), applied highest band first. Cost = floor(HP / 5) % of max HP:
# exactly 20 % of current HP at 5, 10, .. 100 %, never more, never lethal, free only below 5 %
# (with ten 2 % bands it was free below 10 %). The cost cannot be regained by rally
# (regainGaugeDamage 0, as the Chikage's drain 6740): the template's (Bloodletter's 6160) can, and
# the move's own hit, 2-3 frames after the cost, won it all back (play test: Ward -7 %, back in 0.1 s).
BANKAI_COST = list(range(2030110, 2030130))
BANKAI_COST_BANDS, BANKAI_COST_STEP = tuple(float(b) for b in range(100, 0, -5)), 1.0
HALF_COST = BANKAI_COST[1::2]  # bands 95, 85, .. 5 %: about 10 % of current HP (Crimson Moon, Blood Ward)
BANKAI_S, BANKAI_POWER_RATE, BANKAI_HEAL_RATE, BANKAI_BLEED_ADD = 30.0, 1.10, 0.2, 5
BANKAI_TWIN_S = 1.0         # BANKAI_POWER's interval: given again as it runs out
# HUD icons for the 30 s: on BANKAI_POWER (the gold attack-up icon, gem-only in the game), heal on
# hit on BANKAI_LEECH (the HP regen icon of Regain Up and the HP Regene effects).
BANKAI_ICON, BANKAI_HEAL_ICON = 8807, 8809
WARD_ICON = 8808            # the defence-up icon (blood gems only in the game, as 8807)
WAVE_JUDGE = 396            # free in variations 200 and 400
WAVE_BEHAVIOR = 100000000 + VAR * 1000 + WAVE_JUDGE              # 102030396
WAVE_ATK = VAR * 1000 + WAVE_JUDGE                                # 2030396
WAVE_BULLET = 2030020
WAVE_MV = 40                # % of AR, no blood hit: with it (and 80) one Bankai could bleed a full-HP enemy out

# Real rows every new row is copied from (all exist in the game and in ShopEdit).
TEMPLATE = {
    "rhythm": 108100,     # rune "visceral HP recovery" intermediate: on-hit effect to the attacker that is itself an atkOccurrence carrier (stateInfo 152)
    "carrier": 57101,     # blood-gem effect on the wielder: atkOccurrence carrier (stateInfo 152)
    "bleed": 38403,       # blood-gem "bleed +4" effect added to an attack (registBlood, spCategory 10003)
    "power": 6020,        # Logarius' Wheel "Rotation Enhancement 1": 20 s trick-mode buff with HP drain
    "heal": 109000,       # rune visceral heal: instant heal of the attacker
    "cost": 6160,         # Bloodletter transform self-damage: instant 20.1 % max HP
    "plain": 240,         # DLC: a lasting effect on the wearer that does nothing else (stateInfo 290)
    "crescent_launch": 1110, "crescent_flight": 1111,    # Holy Moonlight Sword mode B charged R2 light wave
    "crescent_atk": 2600591, "crescent_behavior": 102600591,
    "wave_bullet": 950,   # Beast Claw (Embrace) L2 roar: AoE around the player
    "wave_atk": 3700930,
}

FPS = 30.0


def _frames(a, b):
    return {"start": round(a / FPS, 4), "end": round(b / FPS, 4), "frames": [a, b]}


def _ev(ability, anims, etype, group, frames, ints, copied_from, why):
    raw = struct.pack("<4i", *ints)
    return {"ability": ability, "anims": anims, "type": etype, "group_type": group, **frames,
            "params_ints": list(ints), "params_hex": raw.hex(" ", 4), "copied_from": copied_from, "why": why}


# TAE events the new moveset must carry. Animation ids use Blade of Mercy's numbering (a113.tae),
# which the trick-mode half of the Sojin TAE copies; params are 16 bytes (4 x int32), unk = 0.
CRESCENT_ANIMS = [41100]                       # trick R2 finisher "mode B large 2", attack 510 at frames 17-20
BANKAI_ANIMS = [33300, 33310]                  # transform attack into trick mode, attack 395 / 390 from frame 16
MOON_ANIMS = [41100]                           # R2 R2: the finisher, attack 510 at 17-20, the Crescent at 19
WARD_ANIMS = [46000]                           # L2 in trick mode (Blade of Mercy's), attack 930 at 13-16
TAE_EVENTS = [
    _ev("Blood Crescent", CRESCENT_ANIMS, 318, 2, _frames(19, 20), (12130, 0, CRESCENT_JUDGE, 0),
        "a143.tae (Holy Moonlight Sword) anim 42660: type 318 (12130, 0, 592, 0) frames 17-18, the last frame "
        "of its attack 581 (also 42620: 590, 42630: 591)",
        "fires behaviour 102030591 (refType 1 -> bullet 2030010) from dummy 130 of model part 2 (the right "
        "blood blade; wp_a_1063_2 has dummy 130) on the last frame of attack 510"),
    *[_ev("Bankai", BANKAI_ANIMS, 66, 66, _frames(14, 15), (sp, 0, 0, 0),
          "a146.tae (Bloodletter) anim 33300: type 66 (6160, 0, 0, 0) frames 19-20 (self-damage on the "
          "transform attack into mode B)",
          f"HP cost band {i + 1}/{len(BANKAI_COST)}: -{BANKAI_COST_STEP:g} % max HP if HP >= "
          f"{BANKAI_COST_BANDS[i]:g} %; one frame so it applies once; keep this order (highest band first)")
      for i, sp in enumerate(BANKAI_COST)],
    # Type 67 (add effect once), as Tonitrus applies 6030 in a109 33300. Type 401 (Logarius'
    # Wheel's) was tried first: in game the 20 s buff never showed (no doubled drain).
    *[_ev("Bankai", BANKAI_ANIMS, 67, 67, _frames(a, a + 1), (BANKAI_START[sp], 0, 0, 0),
          "a109.tae (Tonitrus) anim 33300: type 67 (6030, ...) one frame (adds its buff once); "
          "a110 46000's type 401 did not apply these in game",
          what) for sp, a, what in (
              (BANKAI_POWER, 15, "starts the 30 s of +10 % damage and +5 bleed a hit with blood in the blades (if "
                                 "the first second takes hold before the swing, 16-20, and the shockwave, 16-25, "
                                 "they get them too: +5 bleed each)"),
              (BANKAI_LEECH, 15, "starts the 30 s heal-on-hit carrier"))],
    *[_ev("Crimson Moon", MOON_ANIMS, 66, 66, _frames(14, 15), (sp, 0, 0, 0),
          "Bankai's own cost bands (a146 33300's 6160 pattern)",
          "every other cost band (95, 85, .. 5 %) before the finisher: about half Bankai's cost; full Rhythm only")
      for sp in HALF_COST],
    *[_ev("Crimson Moon", MOON_ANIMS, 67, 67, _frames(15, 16), (BANKAI_START[sp], 0, 0, 0),
          "a109.tae (Tonitrus) anim 33300: type 67 (6030, ...) one frame", what)
      for sp, what in ((MOON_SURGE, "starts the 1.2 s x1.6 surge over the finisher (17-20) and its Crescent (19-)"),
                       (MOON_BLOOD, "starts the 1.2 s +15 bleed carrier over the same hits"))],
    *[_ev("Blood Ward", WARD_ANIMS, 66, 66, _frames(10, 11), (sp, 0, 0, 0),
          "Bankai's own cost bands (a146 33300's 6160 pattern)",
          "every other cost band (95, 85, .. 5 %): about half Bankai's cost; full Rhythm only")
      for sp in HALF_COST],
    _ev("Blood Ward", WARD_ANIMS, 67, 67, _frames(11, 12), (BANKAI_START[WARD], 0, 0, 0),
        "a109.tae (Tonitrus) anim 33300: type 67 (6030, ...) one frame",
        "starts the 20 s ward as the L2 swing starts (attack 930 at 13-16)"),
    _ev("Bankai", BANKAI_ANIMS, 318, 2, _frames(16, 17), (9, 0, WAVE_JUDGE, 0),
        "a156.tae (Kos Parasite) anim 46000: type 318 (9, 0, 930, 0) frames 42-43 (its L2 'space explosion' "
        "AoE around the player, bullet 970)",
        "fires behaviour 102030396 (refType 1 -> bullet 2030020, growing 1.5 -> 4.5 m sphere) from character "
        "dummy 9 (chest) when the transform swing starts"),
    _ev("Bankai (visual, optional)", BANKAI_ANIMS, 96, 96, _frames(16, 31), (252060, 220, 0, 0),
        "a146.tae (Bloodletter) anim 46000: type 96 (252060, 12100, 0) frames 31-56 (its blood burst)",
        "blood burst FFX at character dummy 220 (chest) for the shockwave"),
    _ev("Bankai (visual, optional)", BANKAI_ANIMS, 96, 96, _frames(17, 32), (7119, 12130, 0, 0),
        "a146.tae (Bloodletter) anim 33300: type 96 (7119, 12130, 0) frames 20-35 (blood coating the blade "
        "on its transform)",
        "blood on the right blade as Bankai starts"),
]


def _key(params, name):
    for k in (name, name + ".param"):
        if k in params:
            return params[k]
    raise KeyError(f"params needs {name!r} (got {sorted(params)})")


def _new(p, rid, src, name, **fields):
    p.add(rid, src, name)
    for f, v in fields.items():
        p.set(rid, f, v)
        got = p.get(rid, f)
        assert (abs(got - v) < 1e-5 if isinstance(v, float) else got == v), (rid, f, v, got)
    return rid


def _in(block, rid):
    return block[0] <= rid <= block[1]


def ability_rows():
    """Every row id add_abilities adds, per param."""
    return {
        "SpEffectParam": sorted(RHYTHM + BANKAI_COST + list(BANKAI_START.values()) +
                                [BANKAI_POWER, BANKAI_TWIN, BANKAI_LEECH, BANKAI_HEAL, BANKAI_BLEED,
                                 BANKAI_READY, MOON_SURGE, MOON_BLOOD, MOON_BLEED, WARD,
                                 TWIN_DRAIN, TWIN_BLOOD_HIT, BACK_BLOOD_HIT]),
        "Bullet": [CRESCENT_LAUNCH, CRESCENT_FLIGHT, WAVE_BULLET],
        "AtkParam_Pc": sorted([CRESCENT_ATK, WAVE_ATK]),
        "BehaviorParam_PC": sorted([CRESCENT_BEHAVIOR, WAVE_BEHAVIOR]),
    }


def add_abilities(params):
    """Add the three abilities. params: {"SpEffectParam", "Bullet", "AtkParam_Pc",
    "BehaviorParam_PC": Param} (".param" suffix accepted). Changes only new rows, plus one free
    spEffect slot of the weapon's own trick-mode attack rows (variation 2030) when present.
    Returns a description of what was added and what must happen outside the params."""
    sp, bl = _key(params, "SpEffectParam"), _key(params, "Bullet")
    atk, beh = _key(params, "AtkParam_Pc"), _key(params, "BehaviorParam_PC")
    rows = ability_rows()
    for name, p in (("SpEffectParam", sp), ("Bullet", bl), ("AtkParam_Pc", atk), ("BehaviorParam_PC", beh)):
        taken = [r for r in rows[name] if r in p.rows]
        assert not taken, f"{name}: ability ids already taken: {taken}"
    assert all(_in(SP_BLOCK, r) for r in rows["SpEffectParam"]) and all(_in(BULLET_BLOCK, r) for r in rows["Bullet"])
    assert not any(beh.get(r, "variationId") == VAR and beh.get(r, "behaviorJudgeId") in (CRESCENT_JUDGE, WAVE_JUDGE)
                   for r in beh.rows), "ability judges taken in variation 2030"
    for t in ("rhythm", "carrier", "bleed", "power", "heal", "cost", "plain"):
        assert TEMPLATE[t] in sp.rows, t
    T = TEMPLATE

    # Twin blades: their own blood hit and HP drain (build.py puts them on the weapon) ----------
    _new(sp, TWIN_BLOOD_HIT, BLOOD_HIT, f"Sojin Chikage: twin blades blood hit (bleed {TWIN_BLEED})",
         registBlood=TWIN_BLEED, changeHpRate=BLOOD_LOSS_RATE, changeHpPoint=BLOOD_LOSS_POINT)
    _new(sp, BACK_BLOOD_HIT, BLOOD_HIT, f"Sojin Chikage: transform back blood hit (bleed {BACK_BLEED})",
         registBlood=BACK_BLEED, changeHpRate=BLOOD_LOSS_RATE, changeHpPoint=BLOOD_LOSS_POINT)
    _new(sp, TWIN_DRAIN, 6740, "Sojin Chikage: twin blades HP drain", changeHpRate=TWIN_DRAIN_RATE)
    assert not any(sp.get(r, "stateInfo") == READY_STATE for r in sp.rows), "READY_STATE is used"

    # Blood Rhythm ------------------------------------------------------------------------------
    for k in range(5):
        f = RHYTHM_FACTORS[k]
        _new(sp, RHYTHM[k], T["rhythm"], f"Sojin Chikage: Blood Rhythm stack {k + 1}",
             effectEndurance=RHYTHM_STACK_S, motionInterval=1.0,
             atkOccurrenceSpEffectId=RHYTHM[k + 1] if k < 4 else -1,
             cycleOccurrenceSpEffectId=BANKAI_READY if k == 4 else -1,
             physicsAttackPowerRate=f, magicAttackPowerRate=f, fireAttackPowerRate=f, thunderAttackPowerRate=f,
             throwAttackParamChange=0, validCond_PCWeponState=TRICK_STATE, wepParamChange=1, useSpEffectEffect=0,
             iconId=RHYTHM_ICON if k < 4 else RHYTHM_MAX_ICON)

    # Bankai ------------------------------------------------------------------------------------
    _new(sp, BANKAI_READY, T["plain"], "Sojin Chikage: Bankai ready (full Blood Rhythm)",
         effectEndurance=BANKAI_READY_S, stateInfo=READY_STATE, validCond_PCWeponState=0, useSpEffectEffect=0,
         iconId=RHYTHM_MAX_ICON)
    # No weapon-state condition on Bankai's 30 s effects: they are applied during the transform
    # attack, before the weapon counts as transformed, and a trick-only condition got them
    # rejected in game. What they give is trick mode only, checked as it is given: the power and
    # bleed every second (BANKAI_TWIN), the heal at every hit (BANKAI_HEAL).
    _new(sp, BANKAI_POWER, T["power"], "Sojin Chikage: Bankai (30 s)",
         effectEndurance=BANKAI_S, motionInterval=BANKAI_TWIN_S, changeHpRate=0.0, cycleOccurrenceSpEffectId=BANKAI_TWIN,
         physicsAttackPowerRate=1.0, magicAttackPowerRate=1.0, fireAttackPowerRate=1.0, thunderAttackPowerRate=1.0,
         validCond_PCWeponState=0, regainGaugeDamage=0, useSpEffectEffect=0, iconId=BANKAI_ICON)
    # A Blood Rhythm tier (attack power and a carrier, trick mode only), for one second, given again
    # as it runs out. No sp category, so it cannot replace another effect.
    _new(sp, BANKAI_TWIN, T["rhythm"], "Sojin Chikage: Bankai power and bleed (twin blades only)",
         effectEndurance=BANKAI_TWIN_S, motionInterval=1.0, atkOccurrenceSpEffectId=BANKAI_BLEED,
         cycleOccurrenceSpEffectId=-1,
         physicsAttackPowerRate=BANKAI_POWER_RATE, magicAttackPowerRate=BANKAI_POWER_RATE,
         fireAttackPowerRate=BANKAI_POWER_RATE, thunderAttackPowerRate=BANKAI_POWER_RATE,
         throwAttackParamChange=0, validCond_PCWeponState=TRICK_STATE, wepParamChange=1, useSpEffectEffect=0,
         spCategory=0, iconId=-1)
    _new(sp, BANKAI_LEECH, T["carrier"], "Sojin Chikage: Bankai heal on hit (carrier)",
         effectEndurance=BANKAI_S, atkOccurrenceSpEffectId=BANKAI_HEAL, validCond_PCWeponState=0,
         iconId=BANKAI_HEAL_ICON)
    _new(sp, BANKAI_HEAL, T["heal"], "Sojin Chikage: Bankai heal on hit (twin blades only)",
         changeHpPoint=0, changeHpRate=-BANKAI_HEAL_RATE, validCond_PCWeponState=TRICK_STATE)
    _new(sp, BANKAI_BLEED, T["bleed"], f"Sojin Chikage: Bankai bleed +{BANKAI_BLEED_ADD}", registBlood=BANKAI_BLEED_ADD,
         changeHpRate=BLOOD_LOSS_RATE, changeHpPoint=BLOOD_LOSS_POINT)
    for target, rid in BANKAI_START.items():
        _new(sp, rid, T["plain"], f"Sojin Chikage: Bankai start of {target} (full Rhythm only)",
             effectEndurance=BANKAI_START_S, motionInterval=BANKAI_START_TICK, cycleOccurrenceSpEffectId=target, stateInfo=0,
             validCond_PCWeponState=0, validCond_StateInfo=READY_STATE, useSpEffectEffect=0)
    # Crimson Moon and Blood Ward. No sp category on the surge (6020's 110 is Bankai power's).
    _new(sp, MOON_SURGE, T["power"], "Sojin Chikage: Crimson Moon surge",
         effectEndurance=MOON_S, motionInterval=1.0, changeHpRate=0.0,
         physicsAttackPowerRate=MOON_POWER_RATE, magicAttackPowerRate=MOON_POWER_RATE,
         fireAttackPowerRate=MOON_POWER_RATE, thunderAttackPowerRate=MOON_POWER_RATE,
         validCond_PCWeponState=0, regainGaugeDamage=0, useSpEffectEffect=0, spCategory=0, iconId=BANKAI_ICON)
    _new(sp, MOON_BLOOD, T["carrier"], "Sojin Chikage: Crimson Moon bleed (carrier)",
         effectEndurance=MOON_S, atkOccurrenceSpEffectId=MOON_BLEED, validCond_PCWeponState=0)
    _new(sp, MOON_BLEED, T["bleed"], f"Sojin Chikage: Crimson Moon bleed +{MOON_BLEED_ADD}", registBlood=MOON_BLEED_ADD,
         changeHpRate=BLOOD_LOSS_RATE, changeHpPoint=BLOOD_LOSS_POINT)
    _new(sp, WARD, T["plain"], "Sojin Chikage: Blood Ward",
         effectEndurance=WARD_S, stateInfo=0, validCond_PCWeponState=0, useSpEffectEffect=0, iconId=WARD_ICON,
         **{f: WARD_CUT for f in WARD_CUTS})
    for i, rid in enumerate(BANKAI_COST):
        _new(sp, rid, T["cost"], f"Sojin Chikage: Bankai HP cost band {i + 1} (HP >= {BANKAI_COST_BANDS[i]:g} %)",
             changeHpRate=BANKAI_COST_STEP, conditionHpRate=BANKAI_COST_BANDS[i], validCond_StateInfo=READY_STATE,
             regainGaugeDamage=0)

    # Blood Crescent: HMS light-wave pattern (0.03 s launcher -> flying wave), physical damage from
    # the weapon's own AR (Lost Chikage's physical scales most with Bloodtinge), the twin blood hit.
    flight_life = round(CRESCENT_RANGE_M / CRESCENT_SPEED - bl.get(T["crescent_launch"], "life"), 3)
    _new(atk, CRESCENT_ATK, T["crescent_atk"], "Sojin Chikage: mode B large 2 _ Blood Crescent",
         atkPhysCorrection=CRESCENT_MV, atkMagCorrection=CRESCENT_MV, atkFireCorrection=CRESCENT_MV,
         atkThunCorrection=CRESCENT_MV,
         atkAttribute=4, spAttribute=1, isChargeAtk=0)
    # Looks: Bloodletter's blood burst (252062, a player effect, always loaded) for the flying
    # wave and its hit; the Holy Moonlight Sword wave (252031/253031) showed green in game.
    _new(bl, CRESCENT_LAUNCH, T["crescent_launch"], "Sojin Chikage: Blood Crescent _ firing",
         atkId_Bullet=CRESCENT_ATK, HitBulletID=CRESCENT_FLIGHT, spEffectId0=TWIN_BLOOD_HIT,
         sfxId_Bullet=252062, sfxId_Hit=252062, sfxId_Flick=-1, atkAttribute=4, spAttribute=1)
    _new(bl, CRESCENT_FLIGHT, T["crescent_flight"], "Sojin Chikage: Blood Crescent _ Bullet",
         atkId_Bullet=CRESCENT_ATK, life=flight_life, hitRadius=0.4, hitRadiusMax=0.8, spreadTime=0.3,
         spEffectId0=TWIN_BLOOD_HIT, sfxId_Bullet=252062, sfxId_Hit=252062, sfxId_Flick=-1, atkAttribute=4, spAttribute=1)
    _new(beh, CRESCENT_BEHAVIOR, T["crescent_behavior"], "Sojin Chikage: mode B_ large 2_ Blood Crescent",
         variationId=VAR, behaviorJudgeId=CRESCENT_JUDGE, refType=1, refId=CRESCENT_LAUNCH, stamina=0, mp=0)

    # Bankai shockwave: Beast Claw roar pattern (bullet with no speed at a body dummy), one growing sphere.
    _new(atk, WAVE_ATK, T["wave_atk"], "Sojin Chikage: Bankai _ blood shockwave",
         atkPhysCorrection=WAVE_MV, atkMagCorrection=WAVE_MV, atkFireCorrection=WAVE_MV, atkThunCorrection=WAVE_MV,
         atkAttribute=4)
    _new(bl, WAVE_BULLET, T["wave_bullet"], "Sojin Chikage: Bankai _ blood shockwave",
         atkId_Bullet=WAVE_ATK, life=0.3, hitRadius=1.5, hitRadiusMax=4.5, spreadTime=0.25,
         HitBulletID=-1, spEffectId0=-1, atkAttribute=4)
    _new(beh, WAVE_BEHAVIOR, T["crescent_behavior"], "Sojin Chikage: mode A_ Mode change attack_ Bankai shockwave",
         variationId=VAR, behaviorJudgeId=WAVE_JUDGE, refType=1, refId=WAVE_BULLET, stamina=0, mp=0)

    # Hook: every trick-mode attack of variation 2030 (the attack rows its behaviours point at that
    # carry a blood hit, 6400 or 2030031) also gives stack 1 to the attacker.
    applied, pending, problems = [], [], []
    own = set(rows["AtkParam_Pc"])
    trick_rows = sorted({beh.get(r, "refId") for r in beh.rows
                         if beh.get(r, "variationId") == VAR and beh.get(r, "refType") == 0
                         and beh.get(r, "refId") in atk.rows and beh.get(r, "refId") not in own
                         and atk.get(beh.get(r, "refId"), "spEffectId1") in BLOOD_HITS})
    for r in trick_rows:
        slot = next((s for s in RHYTHM_SLOTS if atk.get(r, s) == -1), None)
        if slot is None:
            problems.append(f"AtkParam_Pc {r}: no free spEffect slot for Blood Rhythm")
            continue
        atk.set(r, slot, RHYTHM[0])
        applied.append({"param": "AtkParam_Pc", "row": r, "field": slot, "value": RHYTHM[0]})
    if not trick_rows:
        pending.append("AtkParam_Pc rows 2030000+judge with spEffectId1 in (6400, 2030031) (built by build.py) are not "
                       "in these params: run add_abilities after build.py has added variation 2030, or set the "
                       f"first free of {RHYTHM_SLOTS} = {RHYTHM[0]} on each of them")

    return {
        "rows": rows,
        "hooks_applied": applied,
        "hooks_pending": pending,
        "problems": problems,
        "tae_events": TAE_EVENTS,
        "tae_notes": [
            "ability_events.add_ability_events(a157 bytes) inserts these events into the combined moveset "
            "(combine_moveset.build_combined(157)). 41000/41010/41100 are not playable under a157 until the "
            "behaviour graph has their clips; 41100 stays the Crescent's target.",
            "Animation ids are Blade of Mercy's (a113.tae): the Sojin TAE copies its trick-mode entries. Use the "
            "entries that carry attack judge 510 (Crescent) and 390/395 (Bankai); Chikage's own a114 puts its "
            "A->B transform attacks at 43300/43310, Blade of Mercy at 33300 (395) / 33310 (390).",
            "Each new event also needs an entry in one of the animation's event groups: group type = event type, "
            "except type 318 (bullet) whose group type is 2 (as every 318 event in the game).",
            "Event params are 16 bytes (4 x int32) for types 66, 67, 96, 318 and 401; event header unk = 0; times "
            "are frame/30.",
            "Bankai goes on the transform ATTACK only (R1 right after L1). The plain L1 transform lives in "
            "a00.tae (19xxx per weapon); it gets nothing.",
            "Blood Rhythm needs no TAE event (it is driven by the attack rows and SpEffects).",
        ],
        "build_py_integration": [
            "call add_abilities after the variation-2030 rows are added and before the params are written",
            f"verify(): exclude ability judges {CRESCENT_JUDGE} and {WAVE_JUDGE} from the 'judge set equals the "
            "moveset's' check and from the blood-hit check (bleeds(591) is True but the crescent's attack row "
            "carries no spEffect: its bullets carry 6400)",
            f"verify(): trick-mode attack rows now also have {RHYTHM[0]} in their first free spEffect slot",
            "the free-id asserts should also cover the SpEffect and Bullet blocks 2030000-2030999",
        ],
        "numbers": {
            "rhythm_damage_per_stack": RHYTHM_PER_STACK, "twin_bleed": TWIN_BLEED, "wave_mv": WAVE_MV,
            "rhythm_timeout_s": RHYTHM_STACK_S, "rhythm_factors": [round(f, 6) for f in RHYTHM_FACTORS],
            "crescent_range_m": CRESCENT_RANGE_M, "crescent_flight_life_s": flight_life,
            "bankai_s": BANKAI_S, "bankai_power": BANKAI_POWER_RATE, "bankai_heal_pct_max_hp": BANKAI_HEAL_RATE,
            "bankai_bleed_add": BANKAI_BLEED_ADD, "bankai_cost_bands": BANKAI_COST_BANDS,
            "bankai_cost_step_pct_max_hp": BANKAI_COST_STEP, "bankai_ready_s": BANKAI_READY_S,
            "crimson_moon": {"s": MOON_S, "power": MOON_POWER_RATE, "bleed_add": MOON_BLEED_ADD,
                             "cost_bands": len(HALF_COST)},
            "blood_ward": {"s": WARD_S, "damage_taken": WARD_CUT, "cost_bands": len(HALF_COST)},
        },
    }


def bankai_cost(hp_pct, sequential=True, bands=None):
    """HP cost in % of max HP at hp_pct % HP (each band pays if HP >= band). sequential: bands
    applied one after another in event order, highest first, HP dropping in between; else all judged
    on the starting HP. The engine does one of the two; with highest-first order both agree.
    bands: the cost effects' ids (default all of BANKAI_COST; HALF_COST for Crimson Moon and Blood Ward)."""
    hp = hp_pct
    for rid in BANKAI_COST if bands is None else bands:
        band = BANKAI_COST_BANDS[BANKAI_COST.index(rid)]
        if (hp if sequential else hp_pct) >= band:
            hp -= BANKAI_COST_STEP
    return hp_pct - hp


# --- self-test ----------------------------------------------------------------------------------

def _bleeds(judge):  # weapon.bleeds, repeated here only for the phase-1 simulation
    return judge == 930 or (400 <= judge < 800 and judge not in (700, 741))


def _simulate_phase1(params):
    """What build.py adds for variation 2030 (behaviour + attack rows from Blade of Mercy's table,
    blood hit on trick-mode attacks), enough to test the Blood Rhythm hook."""
    beh, atk = params["BehaviorParam_PC"], params["AtkParam_Pc"]
    for r in sorted(r for r in beh.rows if beh.get(r, "variationId") == 400):
        j = beh.get(r, "behaviorJudgeId")
        new_atk = VAR * 1000 + j
        beh.add(100000000 + VAR * 1000 + j, r, "sim")
        beh.set(100000000 + VAR * 1000 + j, "variationId", VAR)
        beh.set(100000000 + VAR * 1000 + j, "refId", new_atk)
        atk.add(new_atk, beh.get(r, "refId"), "sim")
        if _bleeds(j):
            atk.set(new_atk, "spEffectId1", TWIN_BLOOD_HIT)


def _check_unchanged(base, work, label, allowed=()):
    for name in PARAMS:
        b, w = base[name], work[name]
        allow = {(r, f) for p, r, f in allowed if p == name}
        rows_allowed = {r for r, _ in allow}
        for r in b.rows:
            assert r in w.rows and w.names[r] == b.names[r], f"{label}: {name} {r} lost or renamed"
            if r in rows_allowed:
                diffs = {f for f, v in b.dump(r).items() if w.dump(r)[f] != v}
                assert diffs <= {f for rr, f in allow if rr == r}, f"{label}: {name} {r} changed {diffs}"
            else:
                assert w.rows[r] == b.rows[r], f"{label}: {name} {r} changed"


HERE = os.path.dirname(os.path.abspath(__file__))
BUILT = os.path.join(HERE, "out", "Sojin Chikage", "dvdroot_ps4", "param", "gameparam", "gameparam.parambnd.dcx")
# The current build's blood-hit judges of variation 2030 (coordinator, 2026-11-01).
CURRENT_BLOOD = sorted([*range(400, 480, 10), 500, 510, *range(600, 700, 10), *range(710, 750, 10), 790, 795, 930])


def load_params(path=None):
    path = path or vanilla_params()
    defs = load_paramdefs()
    _, gp = open_bnd(path)
    return {k: Param(gp.files[gp.index(k + ".param")], defs[st]) for k, st in PARAMS.items()}


def _trick_rows(params):
    beh, atk = params["BehaviorParam_PC"], params["AtkParam_Pc"]
    return {beh.get(r, "behaviorJudgeId"): beh.get(r, "refId") for r in beh.rows
            if beh.get(r, "variationId") == VAR and beh.get(r, "refType") == 0
            and atk.get(beh.get(r, "refId"), "spEffectId1") in BLOOD_HITS}


def self_test(path=None):
    path = path or vanilla_params()
    """Read-only on `path` (a gameparam.parambnd.dcx): works on in-memory copies. With ShopEdit's
    params (no variation 2030) the phase-1 rows are simulated for the hook test; with the mod's
    built params the hook is tested on the real variation-2030 rows."""
    base = load_params(path)
    built = any(base["BehaviorParam_PC"].get(r, "variationId") == VAR for r in base["BehaviorParam_PC"].rows)
    label = "built mod" if built else "ShopEdit"
    expected = ability_rows()
    for name, p in base.items():
        assert not any(r in p.rows for r in expected[name]), f"{name}: ability ids not free in {label}"
    assert not any(_in(SP_BLOCK, r) for r in base["SpEffectParam"].rows), "SpEffect block not free"
    assert not any(_in(BULLET_BLOCK, r) for r in base["Bullet"].rows), "Bullet block not free"
    trick_before = _trick_rows(base)
    if built:
        n = sum(1 for r in base["BehaviorParam_PC"].rows if base["BehaviorParam_PC"].get(r, "variationId") == VAR)
        assert sorted(trick_before) == CURRENT_BLOOD, f"blood judges differ from the expected build: {sorted(trick_before)}"
        print(f"{label}: variation {VAR} has {n} behaviour rows, blood hit on {len(trick_before)} judges")

    # 1. Rows added, nothing else changed (except the hook slot on the weapon's own trick rows).
    work = copy.deepcopy(base)
    info = add_abilities(work)
    for name in PARAMS:
        added = sorted(set(work[name].rows) - set(base[name].rows))
        assert added == expected[name], (name, added)
    assert not info["problems"], info["problems"]
    if built:
        assert not info["hooks_pending"] and sorted(h["row"] for h in info["hooks_applied"]) == sorted(trick_before.values())
        for h in info["hooks_applied"]:
            assert base["AtkParam_Pc"].get(h["row"], h["field"]) == -1 and work["AtkParam_Pc"].get(h["row"], h["field"]) == RHYTHM[0]
        _check_unchanged(base, work, label, [("AtkParam_Pc", h["row"], h["field"]) for h in info["hooks_applied"]])
        others = [r for r in base["AtkParam_Pc"].rows if VAR * 1000 <= r < VAR * 1000 + 1000 and r not in trick_before.values()]
        assert all(RHYTHM[0] not in [work["AtkParam_Pc"].get(r, s) for s in RHYTHM_SLOTS] for r in others)
    else:
        assert info["hooks_pending"] and not info["hooks_applied"]
        _check_unchanged(base, work, label)
    sp, bl, atk, beh = (work[k] for k in PARAMS)

    # Blood Rhythm chain and numbers
    prod = 1.0
    for k in range(5):
        s = RHYTHM[k]
        assert sp.get(s, "effectTargetAttacker") == 1 and sp.get(s, "stateInfo") == 152
        assert sp.get(s, "atkOccurrenceSpEffectId") == (RHYTHM[k + 1] if k < 4 else -1)
        assert sp.get(s, "cycleOccurrenceSpEffectId") == (BANKAI_READY if k == 4 else -1)
        assert sp.get(s, "validCond_PCWeponState") == TRICK_STATE
        assert sp.get(s, "throwAttackParamChange") == 0 and abs(sp.get(s, "effectEndurance") - RHYTHM_STACK_S) < 1e-6
        assert sp.get(s, "iconId") == (RHYTHM_ICON if k < 4 else RHYTHM_MAX_ICON)
        prod *= sp.get(s, "physicsAttackPowerRate")
        assert abs(prod - (1 + 0.04 * (k + 1))) < 1e-5, (k, prod)
    # Bankai: ready only with full Rhythm; every effect it gives waits for that
    assert sp.get(BANKAI_READY, "stateInfo") == READY_STATE and sp.get(BANKAI_READY, "validCond_PCWeponState") == 0
    assert abs(sp.get(BANKAI_READY, "effectEndurance") - BANKAI_READY_S) < 1e-6
    assert sp.get(BANKAI_READY, "iconId") == RHYTHM_MAX_ICON
    gated = list(BANKAI_START.values()) + BANKAI_COST
    assert all(sp.get(r, "validCond_StateInfo") == READY_STATE for r in gated)
    assert all(sp.get(r, "validCond_StateInfo") == 0 for r in expected["SpEffectParam"] if r not in gated)
    for target, rid in BANKAI_START.items():
        assert sp.get(rid, "cycleOccurrenceSpEffectId") == target and sp.get(rid, "stateInfo") == 0
        assert 0 < sp.get(rid, "effectEndurance") < sp.get(rid, "motionInterval")    # one tick: gives its effect once
    started = {e["params_ints"][0] for e in info["tae_events"] if e["type"] == 67}
    assert started == set(BANKAI_START.values()), started
    assert abs(sp.get(BANKAI_HEAL, "changeHpRate") + 0.2) < 1e-6
    # Crimson Moon and Blood Ward: on their own moves, gated like Awakening
    assert abs(sp.get(MOON_SURGE, "physicsAttackPowerRate") - MOON_POWER_RATE) < 1e-6
    assert abs(sp.get(MOON_SURGE, "effectEndurance") - MOON_S) < 1e-6 and sp.get(MOON_SURGE, "spCategory") == 0
    assert sp.get(MOON_SURGE, "changeHpRate") == 0 and sp.get(MOON_SURGE, "cycleOccurrenceSpEffectId") == -1
    assert sp.get(MOON_BLOOD, "atkOccurrenceSpEffectId") == MOON_BLEED and sp.get(MOON_BLEED, "registBlood") == MOON_BLEED_ADD
    assert all(abs(sp.get(WARD, f) - WARD_CUT) < 1e-6 for f in WARD_CUTS) and sp.get(WARD, "iconId") == WARD_ICON
    assert abs(sp.get(WARD, "effectEndurance") - WARD_S) < 1e-6 and sp.get(WARD, "stateInfo") == 0
    per_anim = {}
    for e in info["tae_events"]:
        if e["type"] in (66, 67):
            for a in e["anims"]:
                per_anim.setdefault(a, set()).add(e["params_ints"][0])
    assert per_anim[41100] == set(HALF_COST) | {BANKAI_START[MOON_SURGE], BANKAI_START[MOON_BLOOD]}, per_anim[41100]
    assert per_anim[46000] == set(HALF_COST) | {BANKAI_START[WARD]}, per_anim[46000]
    assert per_anim[33300] == per_anim[33310] == set(BANKAI_COST) | {BANKAI_START[r] for r in (BANKAI_POWER, BANKAI_LEECH)}
    # Bankai's 30 s: no drain, no effect of its own; every second it gives the twin-only power and
    # bleed for a second (never two at once), and its heal on hit is twin-only.
    assert sp.get(BANKAI_POWER, "changeHpRate") == 0 and sp.get(BANKAI_POWER, "cycleOccurrenceSpEffectId") == BANKAI_TWIN
    assert all(sp.get(BANKAI_POWER, f) == 1.0 for f in ("physicsAttackPowerRate", "magicAttackPowerRate",
                                                         "fireAttackPowerRate", "thunderAttackPowerRate"))
    assert abs(sp.get(BANKAI_POWER, "effectEndurance") - BANKAI_S) < 1e-6
    assert abs(sp.get(BANKAI_POWER, "motionInterval") - sp.get(BANKAI_TWIN, "effectEndurance")) < 1e-6
    assert abs(sp.get(BANKAI_TWIN, "physicsAttackPowerRate") - BANKAI_POWER_RATE) < 1e-6
    assert sp.get(BANKAI_TWIN, "atkOccurrenceSpEffectId") == BANKAI_BLEED and sp.get(BANKAI_TWIN, "cycleOccurrenceSpEffectId") == -1
    assert sp.get(BANKAI_TWIN, "stateInfo") == 152 and sp.get(BANKAI_TWIN, "spCategory") == 0
    assert all(sp.get(r, "validCond_PCWeponState") == TRICK_STATE for r in (BANKAI_TWIN, BANKAI_HEAL))
    assert all(sp.get(r, "validCond_PCWeponState") == 0 for r in (BANKAI_POWER, BANKAI_LEECH))
    assert sp.get(BANKAI_POWER, "iconId") == BANKAI_ICON and sp.get(BANKAI_LEECH, "iconId") == BANKAI_HEAL_ICON
    assert all(sp.get(r, "iconId") == -1 for r in [BANKAI_TWIN, BANKAI_HEAL, BANKAI_BLEED] + gated)
    assert sp.get(BANKAI_LEECH, "atkOccurrenceSpEffectId") == BANKAI_HEAL and sp.get(BANKAI_HEAL, "changeHpRate") < 0
    assert sp.get(BANKAI_HEAL, "effectTargetAttacker") == 1
    assert sp.get(TWIN_BLOOD_HIT, "registBlood") == 15 and sp.get(BANKAI_BLEED, "registBlood") == 5
    # Nothing but the twin drain takes HP over time (no doubled drain in Bankai).
    assert [r for r in expected["SpEffectParam"] if sp.get(r, "changeHpRate") > 0 and r not in BANKAI_COST
            and r not in (TWIN_BLOOD_HIT, BACK_BLOOD_HIT, BANKAI_BLEED, MOON_BLEED)] == [TWIN_DRAIN]
    # Copies of Chikage's blood hit and drain with only the balance values changed; every Sojin
    # bleed deals the Sojin blood loss, Chikage's own 6400 keeps 10 % + 100.
    loss = {"changeHpRate": BLOOD_LOSS_RATE, "changeHpPoint": BLOOD_LOSS_POINT}
    for new, src, want in ((TWIN_BLOOD_HIT, BLOOD_HIT, {"registBlood": TWIN_BLEED, **loss}),
                           (BACK_BLOOD_HIT, BLOOD_HIT, {"registBlood": BACK_BLEED, **loss}),
                           (TWIN_DRAIN, 6740, {"changeHpRate": TWIN_DRAIN_RATE})):
        diffs = {f for f, v in sp.dump(src).items() if sp.dump(new)[f] != v}
        assert diffs == set(want) and all(abs(sp.get(new, f) - v) < 1e-5 for f, v in want.items()), (new, diffs)
    assert sp.get(BACK_BLOOD_HIT, "registBlood") == 20 and sp.get(BLOOD_HIT, "registBlood") == 30
    assert all(abs(sp.get(r, "changeHpRate") - BLOOD_LOSS_RATE) < 1e-5 and sp.get(r, "changeHpPoint") == BLOOD_LOSS_POINT
               for r in (TWIN_BLOOD_HIT, BACK_BLOOD_HIT, BANKAI_BLEED, MOON_BLEED))
    for i, rid in enumerate(BANKAI_COST):
        assert abs(sp.get(rid, "conditionHpRate") - BANKAI_COST_BANDS[i]) < 1e-6 and sp.get(rid, "effectEndurance") == 0
        assert sp.get(rid, "regainGaugeDamage") == 0 and sp.get(TEMPLATE["cost"], "regainGaugeDamage") == 1   # no rally back
    # Crescent and shockwave references
    assert beh.get(CRESCENT_BEHAVIOR, "refType") == 1 and beh.get(CRESCENT_BEHAVIOR, "refId") == CRESCENT_LAUNCH
    assert bl.get(CRESCENT_LAUNCH, "HitBulletID") == CRESCENT_FLIGHT
    assert bl.get(CRESCENT_LAUNCH, "atkId_Bullet") == bl.get(CRESCENT_FLIGHT, "atkId_Bullet") == CRESCENT_ATK
    rng = bl.get(CRESCENT_LAUNCH, "initVellocity") * (bl.get(CRESCENT_LAUNCH, "life") + bl.get(CRESCENT_FLIGHT, "life"))
    assert abs(rng - CRESCENT_RANGE_M) < 0.05, rng
    assert beh.get(WAVE_BEHAVIOR, "refId") == WAVE_BULLET and bl.get(WAVE_BULLET, "atkId_Bullet") == WAVE_ATK
    assert bl.get(WAVE_BULLET, "initVellocity") == 0 and bl.get(WAVE_BULLET, "hitRadiusMax") > 4
    assert bl.get(WAVE_BULLET, "spEffectId0") == -1 and atk.get(WAVE_ATK, "atkPhysCorrection") == WAVE_MV
    for r in (CRESCENT_ATK, WAVE_ATK):
        assert atk.get(r, "atkPhysCorrection") > 0
    for r in (CRESCENT_BEHAVIOR, WAVE_BEHAVIOR):
        assert beh.get(r, "variationId") == VAR and r == 100000000 + VAR * 1000 + beh.get(r, "behaviorJudgeId")
    # every id referenced by a new row exists
    for r in expected["SpEffectParam"]:
        for f in ("atkOccurrenceSpEffectId", "cycleOccurrenceSpEffectId", "replaceSpEffectId"):
            v = sp.get(r, f)
            assert v == -1 or v in sp.rows, (r, f, v)
    for r in expected["Bullet"]:
        assert bl.get(r, "HitBulletID") in (-1, 0) or bl.get(r, "HitBulletID") in bl.rows
        assert bl.get(r, "atkId_Bullet") in atk.rows and (bl.get(r, "spEffectId0") in sp.rows or r == WAVE_BULLET)
    # TAE templates: ids they name exist
    for e in info["tae_events"]:
        assert len(bytes.fromhex(e["params_hex"].replace(" ", ""))) == 16
        if e["type"] in (66, 67, 401):
            assert e["params_ints"][0] in sp.rows
        if e["type"] == 318:
            assert 100000000 + VAR * 1000 + e["params_ints"][2] in beh.rows

    # 2. Round trip through the writer: every row survives byte for byte.
    for name in PARAMS:
        again = Param(work[name].to_bytes(), work[name].fields)
        assert set(again.rows) == set(work[name].rows)
        assert all(again.rows[r] == work[name].rows[r] for r in expected[name])

    # 3. ShopEdit only: with simulated phase-1 rows, Blood Rhythm is hooked into every trick row.
    trick = sorted(trick_before.values())
    if not built:
        sim = copy.deepcopy(base)
        _simulate_phase1(sim)
        before = copy.deepcopy(sim)
        info2 = add_abilities(sim)
        assert not info2["hooks_pending"] and not info2["problems"]
        trick = [r for r in before["AtkParam_Pc"].rows if VAR * 1000 <= r < VAR * 1000 + 1000
                 and before["AtkParam_Pc"].get(r, "spEffectId1") in BLOOD_HITS]
        assert trick and len(info2["hooks_applied"]) == len(trick)
        for h in info2["hooks_applied"]:
            assert sim["AtkParam_Pc"].get(h["row"], h["field"]) == RHYTHM[0]
            assert before["AtkParam_Pc"].get(h["row"], h["field"]) == -1
        _check_unchanged(before, sim, "phase1", [("AtkParam_Pc", h["row"], h["field"]) for h in info2["hooks_applied"]])
        normal = [r for r in before["AtkParam_Pc"].rows if VAR * 1000 <= r < VAR * 1000 + 1000 and r not in trick]
        assert all(RHYTHM[0] not in [sim["AtkParam_Pc"].get(r, s) for s in RHYTHM_SLOTS] for r in normal)

    # 4. A second call refuses (ids taken).
    try:
        add_abilities(work)
        raise AssertionError("second add_abilities should fail")
    except AssertionError as e:
        assert "already taken" in str(e), e

    hooks = info["hooks_applied"] if built else info2["hooks_applied"]
    slots = sorted({h["field"] for h in hooks})
    print(f"ok ({label}): rows added", {k: len(v) for k, v in expected.items()},
          f"| Rhythm hooked into {len(trick)} trick attack rows via {slots}")
    for h in range(1, 101):
        c, half = bankai_cost(h), bankai_cost(h, bands=HALF_COST)
        assert c == bankai_cost(h, False) and half == bankai_cost(h, False, HALF_COST), h   # order-independent
        assert c <= 0.2 * h + 1e-9 and (h < 10 or c >= 0.1 * h) and h - c > 0, (h, c)   # <= 20 % of current, never lethal
        assert (c > 0 and half > 0) == (h >= 5), (h, c, half)                            # free only below 5 %
        assert half <= 0.2 * h + 1e-9 and (h < 20 or half >= 0.05 * h) and half <= (c + 1) / 2, (h, half)
    assert bankai_cost(100) == 20 and bankai_cost(100, bands=HALF_COST) == 10
    print("Bankai cost (% max HP) at HP 5..100 %:", [(h, bankai_cost(h)) for h in (4, 5, 9, 10, 15, 25, 39, 50, 75, 99, 100)])
    print("Crimson Moon / Blood Ward cost:", [(h, bankai_cost(h, bands=HALF_COST)) for h in (4, 5, 14, 15, 25, 50, 100)])
    print(f"TAE events: {len(info['tae_events'])} templates for anims "
          f"{sorted({a for e in info['tae_events'] for a in e['anims']})}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--json" in sys.argv:
        print(json.dumps(add_abilities(copy.deepcopy(load_params(args[0] if args else None))), indent=1, default=str))
    elif args:
        self_test(args[0])
    else:
        self_test()
        # A phase-1 build (variation 2030 without abilities) also gets the hook test; a finished
        # build already holds the ability rows, and build.py verifies those.
        if os.path.exists(BUILT) and RHYTHM[0] not in load_params(BUILT)["SpEffectParam"].rows:
            self_test(BUILT)
