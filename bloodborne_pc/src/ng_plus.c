/* SPDX-License-Identifier: GPL-2.0-or-later
 * NG+7 world (pc_ng_plus_7): every enemy at its NG+7 strength, in any character.
 *
 * The game's cycle counter is GameDataMan +0x68 (0..7). Every enemy carries a SpEffect naming its
 * NG+1 multipliers (NpcParam GameClearSpEffectID, rows with bGameClearBonus), and each stat's code
 * scales that row by a 7-entry table indexed with the counter: 0 (no bonus), 1, 1.07 .. 1.2 for
 * health and attack, 0, 1, 1.1 .. 2.5 for echoes. About 70 places read the counter live and no
 * event or Lua script tests it, so the live counter is simply kept at 7.
 *
 * The save keeps the character's real cycle: the writer gets that value instead of the live one,
 * so with the switch off the character is as it was. The real value is learned where the game
 * loads the counter, is 0 where a new game clears it, and follows the ending's increment.
 *
 * In another player's world the game puts the host's cycle in the counter and marks it (session
 * +0x1598); the tick leaves it alone there. */
#include "ng_plus.h"
#include "engine_hooks.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum {
    GAME_DATA_MAN = 0x593b130, /* GameDataMan*; the cycle at +0x68 */
    SESSION = 0x5956678,       /* the session's state; +0x1598 set while visiting another's world */
    CYCLE_LOADED = 0x18eaf0a,  /* the load stores the save's cycle, in eax */
    CYCLE_CLEARED = 0x18e5fd9, /* a new game has just cleared it; rax = GameDataMan */
    CYCLE_SAVED = 0x18ea6de,   /* the save writes eax as the cycle */
    CYCLE_RAISED = 0x1bc0fcf,  /* the ending's "add a cycle" */
};
enum { CYCLE_AT = 0x68, VISITING_AT = 0x1598, TOP_CYCLE = 7 };
static const BbCode loaded_code = {7, 0x88704360af516772ull};
static const BbCode cleared_code = {7, 0x21a6d1fd7e4cbc1aull};
static const BbCode saved_code = {6, 0x433be1e55a4db04aull};
static const BbCode raised_code = {6, 0xa31e81628be19355ull};

static volatile int g_on;
static volatile int32_t g_real = -1; /* the character's own cycle; -1 before one is known */

static uint64_t slot_value(uint64_t bn) {
    uint64_t v = 0;
    return bb_read((uint64_t)(uintptr_t)bb_guest(BB_BN(bn)), &v, 8) ? v : 0;
}

static BB_GUEST_ABI void cycle_loaded(BbRegs *r) {
    if (!g_on) return;
    const int32_t cycle = (int32_t)r->rax;
    g_real = cycle < 0 ? 0 : cycle > TOP_CYCLE ? TOP_CYCLE : cycle;
    r->rax = TOP_CYCLE;
    printf("NG+7 world: this character's own cycle is %d\n", (int)g_real);
}

static BB_GUEST_ABI void cycle_cleared(BbRegs *r) {
    if (!g_on) return;
    const int32_t top = TOP_CYCLE;
    g_real = 0;
    memcpy((void *)(uintptr_t)(r->rax + CYCLE_AT), &top, 4);
}

static BB_GUEST_ABI void cycle_saved(BbRegs *r) {
    if (g_on && g_real >= 0) r->rax = (uint32_t)g_real;
}

static BB_GUEST_ABI void cycle_raised(BbRegs *r) {
    (void)r;
    if (g_on && g_real >= 0 && g_real < TOP_CYCLE) g_real = g_real + 1;
}

static void tick(void) {
    const uint64_t man = slot_value(GAME_DATA_MAN), session = slot_value(SESSION);
    int32_t cycle = 0;
    uint8_t visiting = 0;
    if (!man || !bb_read(man + CYCLE_AT, &cycle, 4) || cycle == TOP_CYCLE) return;
    if (session && bb_read(session + VISITING_AT, &visiting, 1) && visiting) return;
    const int32_t top = TOP_CYCLE;
    memcpy((void *)(uintptr_t)(man + CYCLE_AT), &top, 4);
}

int bb_ng_plus_install(void) {
    const char *on = getenv("BB_PC_NG7_ACTIVE");
    if (!on || strcmp(on, "1")) {
        puts("NG+7 world: off (pc_ng_plus_7, or the Hunter's Dream's script was not made)");
        return 0;
    }
    /* All or nothing: g_on stays 0 if one is refused, and the hooks already in place do nothing. */
    if (bb_hook_mid(BB_BN(CYCLE_SAVED), saved_code, cycle_saved) ||
        bb_hook_mid(BB_BN(CYCLE_RAISED), raised_code, cycle_raised) ||
        bb_hook_mid(BB_BN(CYCLE_CLEARED), cleared_code, cycle_cleared) ||
        bb_hook_mid(BB_BN(CYCLE_LOADED), loaded_code, cycle_loaded)) {
        printf("NG+7 world: off - %s\n", bb_hooks_error());
        return 0;
    }
    g_on = 1;
    bb_on_main_frame(tick);
    puts("NG+7 world: on, enemies at NG+7 strength; saves keep their own cycle");
    return 4;
}
