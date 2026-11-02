/* SPDX-License-Identifier: GPL-2.0-or-later
 * damage_log.c on a small executable "image" holding one of game 1.09's HP writes
 * (mov [rbx + 0xf8], ecx at 0x1a57e1c): the write is hooked and still writes, a lower HP on an
 * enemy's data module is logged with its damage, a write to memory that is not a character's
 * module is dropped, and the player's (WorldChrMan + 0x60) heals are summed into one line. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <io.h>
#include <windows.h>
#include "damage_log.h"
#include "engine_hooks.h"

enum { SITE = 0x1a57e1c, THUNK = 0x1a57f00, WORLD_CHR_MAN = 0x553e878, IMAGE = 0x5540000 };
typedef void (BB_GUEST_ABI *WriteFn)(uint64_t module, int32_t hp);

/* A ChrIns, its module bag and its data module, as far as the log reads them. */
typedef struct {
    unsigned char chr[0x400];
    unsigned char bag[0x40];
    unsigned char module[0x200];
} Chr;

static void make_chr(Chr *c, int32_t hp, int32_t max) {
    memset(c, 0, sizeof(*c));
    const uint64_t bag = (uint64_t)(uintptr_t)c->bag, module = (uint64_t)(uintptr_t)c->module,
                   chr = (uint64_t)(uintptr_t)c->chr;
    memcpy(c->chr + 0x3b0, &bag, 8);
    memcpy(c->bag + 0x20, &module, 8);
    memcpy(c->module + 0x08, &chr, 8);
    memcpy(c->module + 0xf8, &hp, 4);
    memcpy(c->module + 0xfc, &max, 4);
}

static int32_t hp_of(const Chr *c) {
    int32_t hp;
    memcpy(&hp, c->module + 0xf8, 4);
    return hp;
}

static char *read_all(FILE *f) {
    fflush(stdout);
    fseek(f, 0, SEEK_END);
    const long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *text = calloc((size_t)n + 1, 1);
    assert(fread(text, 1, (size_t)n, f) == (size_t)n);
    return text;
}

int main(void) {
    unsigned char *image = VirtualAlloc(NULL, IMAGE, MEM_RESERVE | MEM_COMMIT, PAGE_EXECUTE_READWRITE);
    assert(image);
    /* The site, then ret; a thunk that calls it with rbx = module, ecx = hp (rbx kept). */
    static const unsigned char site[] = {0x89, 0x8b, 0xf8, 0x00, 0x00, 0x00, 0xc3};
    memcpy(image + SITE, site, sizeof(site));
    unsigned char thunk[] = {0x53, 0x48, 0x89, 0xfb, 0x89, 0xf1, 0xe8, 0, 0, 0, 0, 0x5b, 0xc3};
    const int32_t rel = SITE - (THUNK + 11);
    memcpy(thunk + 7, &rel, 4);
    memcpy(image + THUNK, thunk, sizeof(thunk));

    FILE *out = tmpfile();
    assert(out);
    const int saved = _dup(_fileno(stdout));
    _dup2(_fileno(out), _fileno(stdout));

    /* Off unless BB_DAMAGE_LOG=1. */
    assert(bb_hooks_init(image, IMAGE) == 0);
    assert(bb_damage_log_install() == 0);
    _putenv("BB_DAMAGE_LOG=1");
    assert(bb_damage_log_install() == 1);  /* only this site is in the image */
    bb_hooks_seal();

    static Chr player, enemy, other;
    make_chr(&player, 500, 1000);
    make_chr(&enemy, 1240, 1240);
    make_chr(&other, 50, 100);
    static unsigned char world[0x1080];
    const uint64_t world_at = (uint64_t)(uintptr_t)world, player_at = (uint64_t)(uintptr_t)player.chr;
    memcpy(world + 0x60, &player_at, 8);
    memcpy(image + WORLD_CHR_MAN, &world_at, 8);
    /* Not a character's module: its owner's bag leads elsewhere. */
    memset(other.bag + 0x20, 0, 8);

    WriteFn write_hp = (WriteFn)(image + THUNK);
    /* Known before anyone is hit, as in play: the player from the first frame, the enemy from a
     * write that changes nothing. A character first seen dying (an area loading its dead) is no
     * line. */
    static Chr dead_on_load;
    make_chr(&dead_on_load, 544, 544);
    write_hp((uint64_t)(uintptr_t)enemy.module, 1240);
    bb_damage_log_flush();
    write_hp((uint64_t)(uintptr_t)dead_on_load.module, 0);
    write_hp((uint64_t)(uintptr_t)enemy.module, 928);
    assert(hp_of(&enemy) == 928);  /* the game's own write still happens */
    write_hp((uint64_t)(uintptr_t)enemy.module, 0);
    write_hp((uint64_t)(uintptr_t)other.module, 10);
    write_hp((uint64_t)(uintptr_t)player.module, 415);
    write_hp((uint64_t)(uintptr_t)player.module, 600);
    write_hp((uint64_t)(uintptr_t)player.module, 815);
    /* A character first seen through a write that changes nothing (as the max-HP setup does as it
     * loads), then hit by code no hook covers: the frame's poll finds the change. */
    static Chr second, listed, freed;
    make_chr(&second, 800, 800);
    write_hp((uint64_t)(uintptr_t)second.module, 800);
    /* WorldChrMan's character list (count +0x1068, 0x38-byte entries from +0x1070): a character
     * only there is watched too; one whose memory is then reused is never a line. */
    make_chr(&listed, 300, 300);
    make_chr(&freed, 400, 400);
    static unsigned char entries[3 * 0x38];
    const uint64_t listed_at = (uint64_t)(uintptr_t)listed.chr, freed_at = (uint64_t)(uintptr_t)freed.chr,
                   entries_at = (uint64_t)(uintptr_t)entries;
    const uint32_t count = 2;
    memcpy(entries, &listed_at, 8);
    memcpy(entries + 0x38, &freed_at, 8);
    memcpy(world + 0x1068, &count, 4);
    memcpy(world + 0x1070, &entries_at, 8);
    Sleep(600);  /* the list is read twice a second */
    bb_damage_log_flush();
    Sleep(1100);  /* the heals end: a second without one */
    const int32_t hit = 650, listed_hit = 220, garbage[2] = {-1085413291, -1045132894};
    memcpy(second.module + 0xf8, &hit, 4);
    memcpy(listed.module + 0xf8, &listed_hit, 4);
    memcpy(freed.module + 0xf8, garbage, 8);
    bb_damage_log_flush();

    char *text = read_all(out);
    _dup2(saved, _fileno(stdout));
    fputs(text, stdout);
    assert(strstr(text, "Damage log: on (1 of 14 HP writes hooked;"));
    assert(strstr(text, "enemy 2 (max HP 800) took 150 (800 -> 650)\n"));
    assert(strstr(text, "(max HP 300) took 80 (300 -> 220)\n"));
    assert(!strstr(text, "-1085413291"));
    assert(!strstr(text, "max HP 544"));
    assert(strstr(text, "enemy 1 (max HP 1240) took 312 (1240 -> 928)\n"));
    assert(strstr(text, "enemy 1 (max HP 1240) took 928 (928 -> 0), killed\n"));
    assert(!strstr(text, "max HP 100)"));
    assert(strstr(text, "you took 85 (500 -> 415 of 1000)\n"));
    assert(strstr(text, "you healed 400 (415 -> 815 of 1000)\n"));
    assert(strstr(text, "HP write 0x169ab76 not hooked"));  /* the other thirteen are not in this image */
    puts("damage-log-test: ok");
    return 0;
}
