/* SPDX-License-Identifier: GPL-2.0-or-later
 * The game's menu system (SprjScaleformSystem) queues one job per menu player each frame. Removing a
 * player takes it off the system's list and hands it to the delayed delete, which frees it 5 frames
 * later. A job can still arrive after the removal: with jobs stalled on purpose, unlisted players'
 * jobs ran (still allocated then). A player's crash at image 0x1f591b0 (a call through [player+0x38],
 * by then what looks like a heap block header) came 8 s into a new game, just after an autosave and a
 * 660 ms hitch. That crash has not been reproduced; which path freed that player is not known.
 *
 * The job ends in a jump to the player's work, with the player in rdi and the system still in rsi. A
 * player on the list is alive, since it leaves the list before the delayed delete starts counting,
 * so the hook runs the work only for a listed player. A job that is skipped by a list being rewritten
 * under it (another player's removal) costs that menu one frame's update. */
#include "menu_job_guard.h"
#include "engine_hooks.h"

#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

enum {
    JOB_TAIL = 0x23644d8,    /* the job's `jmp` to the player's work */
    PLAYER_WORK = 0x2359150, /* the player's work */
    LIST_AT = 0x990,         /* the system's players; the game aligns the start to 8 */
    COUNT_AT = 0xa98,
    LIST_MAX = 33,
};

typedef void (BB_GUEST_ABI *Work)(uint64_t player);

static Work g_work;
static atomic_int g_skipped;

static int listed(uint64_t system, uint64_t player) {
    const uint64_t list = system + LIST_AT + ((0 - (system + LIST_AT)) & 7);
    uint64_t count;
    memcpy(&count, (const void *)(uintptr_t)(system + COUNT_AT), sizeof(count));
    if (count > LIST_MAX) return 0;
    for (uint64_t i = 0; i < count; ++i) {
        uint64_t entry;
        memcpy(&entry, (const void *)(uintptr_t)(list + i * sizeof(entry)), sizeof(entry));
        if (entry == player) return 1;
    }
    return 0;
}

static void BB_GUEST_ABI job(uint64_t player, uint64_t system) {
    if (listed(system, player)) {
        g_work(player);
        return;
    }
    printf("Menu job guard: skipped a job for a menu no longer listed (%d so far)\n", atomic_fetch_add(&g_skipped, 1) + 1);
    fflush(stdout);
}

int bb_menu_job_guard_install(void) {
    g_work = (Work)bb_guest(BB_BN(PLAYER_WORK));
    if (bb_hook_call(BB_BN(JOB_TAIL), BB_BN(PLAYER_WORK), (void *)job)) {
        printf("Menu job guard: off - %s\n", bb_hooks_error());
        return 0;
    }
    puts("Menu job guard: on");
    return 1;
}
