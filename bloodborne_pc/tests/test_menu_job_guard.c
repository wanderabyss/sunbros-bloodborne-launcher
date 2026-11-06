/* SPDX-License-Identifier: GPL-2.0-or-later
 * menu_job_guard.c on a small executable "image" holding the job's tail: a menu player's work runs
 * only while the player is on the system's list, and a different layout leaves the hook out. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <windows.h>
#include "engine_hooks.h"
#include "menu_job_guard.h"

enum { JOB = 0x1f644d0, JOB_TAIL = 0x1f644d8, WORK = 0x1f59150, IMAGE = 0x3000000 };
enum { LIST_AT = 0x990, COUNT_AT = 0xa98 };
typedef void (BB_GUEST_ABI *Job)(uint64_t unused, uint64_t system, uint64_t player);

/* The work: stores rdi where the test can see it. */
static uint64_t g_ran;
static void build(unsigned char *image) {
    /* mov rax, &g_ran; mov [rax], rdi; ret */
    unsigned char work[] = {0x48, 0xb8, 0, 0, 0, 0, 0, 0, 0, 0, 0x48, 0x89, 0x38, 0xc3};
    const uint64_t ran = (uint64_t)(uintptr_t)&g_ran;
    memcpy(work + 2, &ran, sizeof(ran));
    memcpy(image + WORK, work, sizeof(work));
    /* test rdx, rdx; je +8; mov rdi, rdx; jmp work; ret */
    unsigned char job[] = {0x48, 0x85, 0xd2, 0x74, 0x08, 0x48, 0x89, 0xd7, 0xe9, 0, 0, 0, 0, 0xc3};
    const int32_t rel = WORK - (JOB_TAIL + 5);
    memcpy(job + 9, &rel, sizeof(rel));
    memcpy(image + JOB, job, sizeof(job));
}

static void set_list(unsigned char *system, const uint64_t *players, uint64_t count) {
    memset(system + LIST_AT, 0xcc, COUNT_AT - LIST_AT);
    memcpy(system + LIST_AT, players, count * sizeof(*players));
    memcpy(system + COUNT_AT, &count, sizeof(count));
}

static uint64_t run(unsigned char *image, unsigned char *system, uint64_t player) {
    g_ran = 0;
    ((Job)(image + JOB))(0, (uint64_t)(uintptr_t)system, player);
    return g_ran;
}

int main(void) {
    unsigned char *image = VirtualAlloc(NULL, IMAGE, MEM_RESERVE | MEM_COMMIT, PAGE_EXECUTE_READWRITE);
    assert(image);
    assert(bb_hooks_init(image, IMAGE) == 0);

    /* Another layout: nothing is hooked. */
    assert(bb_menu_job_guard_install() == 0);
    build(image);
    unsigned char before[5];
    memcpy(before, image + JOB_TAIL, sizeof(before));
    assert(bb_menu_job_guard_install() == 1);
    assert(memcmp(before, image + JOB_TAIL, sizeof(before)) != 0);
    bb_hooks_seal();

    static _Alignas(8) unsigned char system[0xaa0];
    const uint64_t a = 0x1000, b = 0x2000, gone = 0x3000;

    const uint64_t both[] = {a, b};
    set_list(system, both, 2);
    assert(run(image, system, a) == a);
    assert(run(image, system, b) == b);
    assert(run(image, system, gone) == 0); /* removed: the delayed delete owns it now */

    const uint64_t one[] = {b};
    set_list(system, one, 1);
    assert(run(image, system, a) == 0);
    assert(run(image, system, b) == b);

    /* The job's own check: no player, no work. */
    assert(run(image, system, 0) == 0);

    /* An empty list, and a count no list can hold. */
    set_list(system, one, 0);
    assert(run(image, system, b) == 0);
    const uint64_t silly = 34;
    memcpy(system + COUNT_AT, &silly, sizeof(silly));
    assert(run(image, system, b) == 0);

    puts("menu job guard: ok");
    return 0;
}
