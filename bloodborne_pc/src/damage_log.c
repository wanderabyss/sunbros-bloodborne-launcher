/* SPDX-License-Identifier: GPL-2.0-or-later
 * Damage log: every HP change of the player and of the characters they fight, as lines in the
 * game's output (last_run.log), so a weapon's real damage can be read after a fight.
 *
 * A character's HP lives in its data module ([[ChrIns + 0x3b0] + 0x20]): current HP at +0xf8,
 * max HP at +0xfc, the owning ChrIns at +0x08 (bbsc-0.0.2's GetBbscLocalPlayerHp reads the
 * player's this way).
 *
 * Game 1.09 does not apply hit damage through one recognisable instruction: thirteen writes share
 * the HP bar's redraw tail (the new value clamped to 0..max, `mov [module + 0xf8], r32`, then the
 * global at image offset 0x5556678, byte +0x176f), but in play only the death write among them
 * fires; ordinary hits change HP elsewhere (4.2.18 play test). So the log does not wait for the
 * write. It reads WorldChrMan's character list twice a second (count at +0x1068, entries of 0x38
 * bytes from the pointer at +0x1070, the ChrIns at +0; found by reading a running game's memory)
 * and keeps every character's data module in a table; the main-thread tick (bb_on_main_frame) reads
 * each one's HP every frame, and any change, whatever wrote it, is a line. The hooks (bb_hook_mid,
 * before each write; nothing is changed) add the modules they see too, the max-HP setup at
 * 0x1a567ab (characters as they load) among them, and give the death write its own line.
 *
 * A module counts only when its owner's own module pointer leads back to it, checked as it is
 * first seen, every second after and again before any change is logged; HP and max HP must make
 * sense too (0 <= HP <= max HP <= MAX_SANE_HP). A character unloaded leaves the table: in play,
 * memory freed at an area change once read as HP changes of a billion. The player
 * is the ChrIns at WorldChrMan + 0x60; everyone else is "enemy N", numbered in the order they are
 * first hurt, with their max HP. The player's heals are summed until a second passes without one
 * (blood vials, rally and regeneration come as many small changes); an enemy's HP coming back (a
 * reset or a load) is not logged.
 *
 * Diagnostics: the first main-thread tick says so once; every ten seconds with new activity a line
 * counts each site's writes, the characters tracked and the events dropped and why; the first few
 * writes that are not a character's are printed with their pointers.
 *
 * Addresses are image offsets (eboot virtual address minus 0x400000). */
#include "damage_log.h"
#include "engine_hooks.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

enum {
    WORLD_CHR_MAN = 0x553e878,  /* WorldChrMan*; the player's ChrIns at +0x60 */
    PLAYER_CHR = 0x60,
    CHR_MODULES = 0x3b0, DATA_MODULE = 0x20,
    MODULE_OWNER = 0x08, MODULE_HP = 0xf8, MODULE_MAX_HP = 0xfc,
    QUEUE = 512,                /* HP writes between two main-thread frames */
    TRACKED = 512,              /* characters whose HP is read every frame */
    ENEMIES = 64,
    HEAL_QUIET_MS = 1000,
    CHECK_MS = 1000,            /* how often every tracked module's owner is checked again */
    CHR_SET_COUNT = 0x1068, CHR_SET = 0x1070, CHR_ENTRY = 0x38,  /* WorldChrMan's character list */
    CHR_SET_MAX = 4096,
    LIST_MS = 500,              /* how often that list is read for new characters */
    MAX_SANE_HP = 10000000,
    REPORT_MS = 10000,
    SHOW_DROPPED = 8,           /* "not a character" writes printed in full */
};

/* BbRegs as an array: r15, r14, r13, r12, r11, r10, r9, r8, rdi, rsi, rbp, rbx, rdx, rcx, rax. */
enum { R15, R14, R13, R12, R11, R10, R9, R8, RDI, RSI, RBP, RBX, RDX, RCX, RAX };

typedef struct {
    uint64_t at;
    BbCode code;    /* the write itself: mov dword [base + 0xf8], value */
    int base, value;
} Site;

static const Site sites[] = {
    {0x169ab76, {7, 0xaeb0422e8320724bull}, R14, RCX},
    {0x18bf883, {7, 0x9aadea7a8fb44f48ull}, R15, RCX},
    {0x18bfa04, {6, 0x10a887ff450b5915ull}, RBX, RCX},
    {0x18c4a2b, {6, 0x45bd3f52e519668cull}, RAX, RDI},
    {0x18ce604, {6, 0x10a887ff450b5915ull}, RBX, RCX},
    {0x193ca5f, {8, 0x4c6decdc0116c9c7ull}, R12, RDX},
    {0x1a1254d, {7, 0x42e572c0f8750b63ull}, R14, RDX},
    {0x1a2c095, {6, 0xf7a46f7449639e9aull}, RDX, RSI},
    {0x1a2fdfd, {6, 0x71cb68193b2fe1fdull}, RBX, RDX},
    {0x1a31912, {7, 0x398b0a60998fc660ull}, R15, RDX},
    {0x1a35ed3, {6, 0x91d3a8565ff13137ull}, RCX, RAX},
    {0x1a57e1c, {6, 0x10a887ff450b5915ull}, RBX, RCX},
    {0x1c13ec1, {8, 0x5d2f188d6123cb3full}, R12, RCX},
    /* The max-HP setup: max from the character's parameters, HP clamped to it, as it loads. */
    {0x1a567ab, {6, 0x0ba6c7283ccfc19dull}, RBX, RSI},
};
#define SITES (sizeof(sites) / sizeof(*sites))
enum { SITES_N = SITES };

typedef struct {
    uint64_t module;
    int32_t old_hp, new_hp, max_hp;
    volatile int ready;
} Event;

static Event g_queue[QUEUE];
static volatile unsigned g_head; /* written by the game's threads */
static unsigned g_tail;          /* read by the main thread */
static unsigned g_dropped;

/* The characters being watched (main thread only). */
typedef struct {
    uint64_t module, owner;
    int32_t hp, max_hp;
} Tracked;
static Tracked g_tracked[TRACKED];
static unsigned g_count;
static uint64_t g_checked_ms, g_listed_ms;
static unsigned g_insane;

static uint64_t g_enemy[ENEMIES]; /* owner ChrIns of enemy N + 1 */
static unsigned g_enemies;
static uint64_t g_start_ms;

/* The player's heals being summed. */
static int32_t g_heal_from, g_heal_to, g_heal_max;
static uint64_t g_heal_ms;

/* Diagnostics: writes seen per site (game threads), and what became of them (main thread). */
static volatile unsigned g_hits[SITES_N], g_unreadable;
static unsigned g_not_chr, g_enemy_up, g_logged, g_full, g_shown_drops, g_ticks;
static uint64_t g_report_ms;
static unsigned g_reported;     /* g_hits' total and g_logged at the last report */

#if defined(_WIN32)
#include <windows.h>
static uint64_t now_ms(void) { return GetTickCount64(); }
#else
static uint64_t now_ms(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * 1000u + (uint64_t)t.tv_nsec / 1000000u;
}
#endif

void bb_damage_log_record(uint64_t module, int32_t old_hp, int32_t new_hp, int32_t max_hp) {
    const unsigned slot = __atomic_fetch_add(&g_head, 1u, __ATOMIC_RELAXED) % QUEUE;
    Event *e = &g_queue[slot];
    if (__atomic_load_n(&e->ready, __ATOMIC_ACQUIRE)) {  /* the main thread has not caught up */
        __atomic_fetch_add(&g_dropped, 1u, __ATOMIC_RELAXED);
        return;
    }
    e->module = module;
    e->old_hp = old_hp;
    e->new_hp = new_hp;
    e->max_hp = max_hp;
    __atomic_store_n(&e->ready, 1, __ATOMIC_RELEASE);
}

/* Runs before the write at the site: the old HP is still in the module. */
static void on_write(const BbRegs *regs, const Site *site) {
    const uint64_t *r = (const uint64_t *)regs;
    const uint64_t module = r[site->base];
    __atomic_fetch_add(&g_hits[site - sites], 1u, __ATOMIC_RELAXED);
    int32_t old_hp = 0, max_hp = 0;
    if (!bb_read(module + MODULE_HP, &old_hp, 4) || !bb_read(module + MODULE_MAX_HP, &max_hp, 4)) {
        __atomic_fetch_add(&g_unreadable, 1u, __ATOMIC_RELAXED);
        return;
    }
    bb_damage_log_record(module, old_hp, (int32_t)(uint32_t)r[site->value], max_hp);
}

#define HOST(i) static void BB_GUEST_ABI host_##i(BbRegs *regs) { on_write(regs, &sites[i]); }
HOST(0) HOST(1) HOST(2) HOST(3) HOST(4) HOST(5) HOST(6) HOST(7) HOST(8) HOST(9) HOST(10) HOST(11) HOST(12)
HOST(13)
static void (BB_GUEST_ABI *const hosts[])(BbRegs *) = {
    host_0, host_1, host_2, host_3, host_4, host_5, host_6, host_7, host_8, host_9, host_10, host_11, host_12,
    host_13,
};

static uint64_t read_ptr(uint64_t at) {
    uint64_t v = 0;
    return at && bb_read(at, &v, 8) ? v : 0;
}

static uint64_t module_of(uint64_t chr) {
    return read_ptr(read_ptr(chr + CHR_MODULES) + DATA_MODULE);
}

/* The module's owner when the module is that owner's data module, else 0. */
static uint64_t owner_of(uint64_t module) {
    const uint64_t owner = read_ptr(module + MODULE_OWNER);
    return owner && module_of(owner) == module ? owner : 0;
}

static uint64_t player_chr(void) {
    const uint64_t slot = (uint64_t)(uintptr_t)bb_guest(WORLD_CHR_MAN);
    return read_ptr(read_ptr(slot) + PLAYER_CHR);
}

static unsigned enemy_number(uint64_t owner) {
    for (unsigned i = 0; i < g_enemies; ++i)
        if (g_enemy[i] == owner) return i + 1;
    const unsigned i = g_enemies < ENEMIES ? g_enemies++ : (g_enemies = 1, 0);  /* full: start again */
    g_enemy[i] = owner;
    return i + 1;
}

static double seconds(uint64_t ms) { return (double)(ms - g_start_ms) / 1000.0; }

static void flush_heal(uint64_t now, int force) {
    if (!g_heal_ms || (!force && now - g_heal_ms < HEAL_QUIET_MS)) return;
    printf("Damage log %8.2f s: you healed %d (%d -> %d of %d)\n", seconds(g_heal_ms),
           g_heal_to - g_heal_from, g_heal_from, g_heal_to, g_heal_max);
    g_heal_ms = 0;
}

static int sane(int32_t hp, int32_t max_hp) {
    return max_hp > 0 && max_hp <= MAX_SANE_HP && hp >= 0 && hp <= max_hp;
}

/* One HP change of a tracked character: a line, or (the player's heals) a running sum. */
static void log_change(const Tracked *t, int32_t old_hp, int32_t new_hp, int32_t max_hp, uint64_t player,
                       uint64_t now) {
    const int32_t change = new_hp - old_hp;
    if (!change) return;
    if (t->owner == player) {
        if (change > 0) {
            if (!g_heal_ms) g_heal_from = old_hp;
            g_heal_to = new_hp;
            g_heal_max = max_hp;
            g_heal_ms = now;
            return;
        }
        flush_heal(now, 1);
        ++g_logged;
        printf("Damage log %8.2f s: you took %d (%d -> %d of %d)%s\n", seconds(now), -change, old_hp, new_hp,
               max_hp, new_hp <= 0 ? ", dead" : "");
        return;
    }
    if (change > 0) {  /* an enemy's HP coming back: a reset or a load, not a fight */
        ++g_enemy_up;
        return;
    }
    ++g_logged;
    printf("Damage log %8.2f s: enemy %u (max HP %d) took %d (%d -> %d)%s\n", seconds(now), enemy_number(t->owner),
           max_hp, -change, old_hp, new_hp, new_hp <= 0 ? ", killed" : "");
}

/* The table entry for `module` (a character's, owner checked), added with `hp` when new. */
static Tracked *track(uint64_t module, uint64_t owner, int32_t hp, int32_t max_hp) {
    for (unsigned i = 0; i < g_count; ++i)
        if (g_tracked[i].module == module) {
            g_tracked[i].owner = owner;
            return &g_tracked[i];
        }
    if (g_count == TRACKED) {
        ++g_full;
        return NULL;
    }
    Tracked *t = &g_tracked[g_count++];
    t->module = module;
    t->owner = owner;
    t->hp = hp;
    t->max_hp = max_hp;
    return t;
}

/* A hooked write: the module joins the table, and its own change is logged as written. */
static void take_event(const Event *e, uint64_t player, uint64_t now) {
    const uint64_t owner = owner_of(e->module);
    if (!owner) {
        ++g_not_chr;
        if (g_shown_drops < SHOW_DROPPED) {
            ++g_shown_drops;
            const uint64_t raw = read_ptr(e->module + MODULE_OWNER);
            printf("Damage log: dropped HP %d -> %d (max %d): module %#llx, +0x08 %#llx, its +0x3b0/+0x20 %#llx, "
                   "player %#llx -> %#llx\n", e->old_hp, e->new_hp, e->max_hp, (unsigned long long)e->module,
                   (unsigned long long)raw, (unsigned long long)(raw ? module_of(raw) : 0),
                   (unsigned long long)player, (unsigned long long)module_of(player));
        }
        return;
    }
    if (!sane(e->old_hp, e->max_hp)) {
        ++g_insane;
        return;
    }
    /* A character first seen through a write is only taken in: as an area loads, the game sets
     * every enemy already dead there to 0 HP (27 "kills" in one frame, 4.2.18 play), and live ones
     * are in the character list before anyone hits them. */
    const unsigned known = g_count;
    Tracked *t = track(e->module, owner, e->old_hp, e->max_hp);
    if (!t) return;
    const int32_t new_hp = e->new_hp < 0 ? 0 : e->new_hp > e->max_hp ? e->max_hp : e->new_hp;
    if (g_count != known) {
        t->hp = new_hp;
        t->max_hp = e->max_hp;
        return;
    }
    log_change(t, t->hp, new_hp, e->max_hp, player, now);
    t->hp = e->new_hp;
    t->max_hp = e->max_hp;
}

/* WorldChrMan's character list: every character there joins the table with its HP as it is now. */
static void read_list(uint64_t now) {
    if (now - g_listed_ms < LIST_MS) return;
    g_listed_ms = now;
    const uint64_t man = read_ptr((uint64_t)(uintptr_t)bb_guest(WORLD_CHR_MAN));
    uint32_t count = 0;
    const uint64_t entries = man ? read_ptr(man + CHR_SET) : 0;
    if (!entries || !bb_read(man + CHR_SET_COUNT, &count, 4) || count > CHR_SET_MAX) return;
    for (uint32_t i = 0; i < count; ++i) {
        const uint64_t chr = read_ptr(entries + (uint64_t)i * CHR_ENTRY);
        const uint64_t module = chr ? module_of(chr) : 0;
        int32_t hp_max[2];
        if (!module || read_ptr(module + MODULE_OWNER) != chr || !bb_read(module + MODULE_HP, hp_max, sizeof(hp_max)) ||
            !sane(hp_max[0], hp_max[1]))
            continue;
        track(module, chr, hp_max[0], hp_max[1]);
    }
}

/* Every tracked character's HP as it is now; a change no hooked write reported is logged here. */
static void poll(uint64_t player, uint64_t now) {
    const int check = now - g_checked_ms >= CHECK_MS;
    if (check) g_checked_ms = now;
    unsigned kept = 0;
    for (unsigned i = 0; i < g_count; ++i) {
        Tracked t = g_tracked[i];
        int32_t hp_max[2];
        if (!bb_read(t.module + MODULE_HP, hp_max, sizeof(hp_max))) continue;   /* gone */
        if (check) {
            const uint64_t owner = owner_of(t.module);
            if (!owner) continue;                                               /* unloaded or reused */
            t.owner = owner;
        }
        if (hp_max[0] != t.hp) {
            /* Before a line: still this owner's module, and numbers that are HP. */
            if (!check && owner_of(t.module) != t.owner) continue;
            if (!sane(hp_max[0], hp_max[1])) {
                ++g_insane;
                continue;
            }
            log_change(&t, t.hp, hp_max[0], hp_max[1], player, now);
        }
        t.hp = hp_max[0];
        t.max_hp = hp_max[1];
        g_tracked[kept++] = t;
    }
    g_count = kept;
}

static void report(uint64_t now, uint64_t player) {
    unsigned total = 0;
    for (size_t i = 0; i < SITES; ++i) total += __atomic_load_n(&g_hits[i], __ATOMIC_RELAXED);
    if (now - g_report_ms < REPORT_MS || total + g_logged == g_reported) return;
    g_report_ms = now;
    g_reported = total + g_logged;
    printf("Damage log: %u HP writes (", total);
    for (size_t i = 0; i < SITES; ++i) {
        const unsigned n = __atomic_load_n(&g_hits[i], __ATOMIC_RELAXED);
        if (n) printf("%#llx:%u ", (unsigned long long)sites[i].at, n);
    }
    printf("), %u characters tracked%s, unreadable %u, not a character %u, not HP %u, enemy HP up %u, logged %u; "
           "player %#llx, %u ticks\n", g_count, g_full ? " (table full)" : "",
           __atomic_load_n(&g_unreadable, __ATOMIC_RELAXED), g_not_chr, g_insane, g_enemy_up, g_logged,
           (unsigned long long)player, g_ticks);
}

void bb_damage_log_flush(void) {
    const uint64_t now = now_ms();
    const uint64_t player = player_chr();
    if (!g_ticks++) printf("Damage log: main-thread tick running (player ChrIns %#llx)\n", (unsigned long long)player);
    const unsigned logged = g_logged;
    for (;;) {
        Event *e = &g_queue[g_tail % QUEUE];
        if (!__atomic_load_n(&e->ready, __ATOMIC_ACQUIRE)) break;
        take_event(e, player, now);
        __atomic_store_n(&e->ready, 0, __ATOMIC_RELEASE);
        ++g_tail;
    }
    /* The player is always watched, hooked write or not. */
    const uint64_t mine = player ? module_of(player) : 0;
    int32_t hp_max[2];
    if (mine && bb_read(mine + MODULE_HP, hp_max, sizeof(hp_max))) track(mine, player, hp_max[0], hp_max[1]);
    read_list(now);
    poll(player, now);
    flush_heal(now, 0);
    const unsigned dropped = __atomic_exchange_n(&g_dropped, 0u, __ATOMIC_RELAXED);
    if (dropped) printf("Damage log: %u HP writes not seen (more than %d in one frame)\n", dropped, QUEUE);
    report(now, player);
    if (g_ticks == 1 || g_logged != logged || dropped || g_heal_ms == 0) fflush(stdout);
}

int bb_damage_log_install(void) {
    const char *on = getenv("BB_DAMAGE_LOG");
    if (!on || strcmp(on, "1")) return 0;
    int hooks = 0;
    for (size_t i = 0; i < SITES; ++i) {
        if (bb_hook_mid(sites[i].at, sites[i].code, hosts[i]))
            printf("Damage log: HP write %#llx not hooked (%s)\n", (unsigned long long)sites[i].at, bb_hooks_error());
        else
            ++hooks;
    }
    if (!hooks) {
        puts("Damage log: off - none of game 1.09's HP writes were found");
        return 0;
    }
    g_start_ms = now_ms();
    bb_on_main_frame(bb_damage_log_flush);
    printf("Damage log: on (%d of %u HP writes hooked; every character's HP is read each frame); lines start "
           "\"Damage log\"\n", hooks, (unsigned)SITES);
    return hooks;
}
