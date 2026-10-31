/* SPDX-License-Identifier: GPL-2.0-or-later
 * Running-jump momentum at an uncapped frame rate.
 *
 * chr_motion_physics_update (image offset 0x1a4abca) multiplies the character's horizontal
 * momentum by a four-lane vector of 0.95, once per 30-FPS frame. The fixed FPS presets write
 * their rate's value into that vector when the game starts (patches.py running_jump). Uncapped
 * has no single rate - the frame time follows the machine - and the list's own 60-FPS value is
 * right only at 60. Reference: https://github.com/droogie/bbhost/blob/master/tools/dt_loads.txt
 *
 * Here the multiply reads a cell of ours instead (the instruction's RIP-relative operand is
 * pointed at it; everything else that reads the game's vector is left alone), and the main-thread
 * tick (bb_on_main_frame) writes 0.95 ** (30 dt) into it for the current frame time. That keeps
 * the decay per second at the 30-FPS game's whatever the rate, the way the fixed presets do at
 * theirs. It changes horizontal momentum only; the vertical impulse is not touched.
 *
 * The frame time is the game's own: its frame-time manager keeps the measured delta at +0x264, as
 * the Uncap FPS++ list's caves read it. When that field is unreadable or disagrees with the wall
 * clock by more than a factor of two, the wall clock between ticks is used. BB_JUMP_DT_SOURCE=
 * clock|game overrides that choice for comparison runs. BB_FPS_LOG=1 reports both readings every
 * ten seconds, so a log shows which one the game's frames follow.
 *
 * Addresses are image offsets (eboot virtual address minus 0x400000). */
#include "jump_decay.h"
#include "engine_hooks.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

enum {
    LOAD_AT = 0x1a4abca,        /* vmulps xmm0, xmm0, [rip + disp32]: 8 bytes */
    VECTOR = 0x490b5b0,         /* the four 0.95 lanes it reads */
    MANAGER_SLOT = 0x55404f8,   /* holds the frame-time manager's address */
    DT_FIELD = 0x264,           /* the manager's measured frame delta, seconds (float) */
    REPORT_MS = 10000,
};
static const BbCode load_code = {8, 0x67987ba40d103139ull};

static const float MIN_DT = 1.0f / 480.0f, MAX_DT = 1.0f / 20.0f;

typedef enum { SOURCE_AUTO, SOURCE_CLOCK, SOURCE_GAME } Source;

static float *g_cell;
static uint64_t g_slot;
static Source g_source = SOURCE_AUTO;
static int g_report;

/* Main-thread tick state and the report's counters. */
static uint64_t g_last_us, g_report_us;
static float g_ema_wall;
static unsigned g_frames, g_game_used, g_clock_used, g_game_bad;
static double g_game_sum, g_wall_sum;
static float g_factor_min = 1.0f, g_factor_max = 0.0f;

float bb_jump_decay_factor(float dt) {
    if (!(dt > MIN_DT)) dt = MIN_DT;  /* also NaN */
    if (dt > MAX_DT) dt = MAX_DT;
    return powf(0.95f, 30.0f * dt);
}

void bb_jump_decay_apply(float dt) {
    if (!g_cell) return;
    const float factor = bb_jump_decay_factor(dt);
    volatile float *cell = g_cell;
    for (int i = 0; i < 4; ++i) cell[i] = factor;
    if (factor < g_factor_min) g_factor_min = factor;
    if (factor > g_factor_max) g_factor_max = factor;
}

#if defined(_WIN32)
#include <windows.h>
static uint64_t now_us(void) {
    static LARGE_INTEGER freq;
    if (!freq.QuadPart) QueryPerformanceFrequency(&freq);
    LARGE_INTEGER counter;
    QueryPerformanceCounter(&counter);
    return (uint64_t)(counter.QuadPart * 1000000ULL / freq.QuadPart);
}
#else
static uint64_t now_us(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * 1000000u + (uint64_t)t.tv_nsec / 1000u;
}
#endif

/* The game's frame delta, or 0 when its manager is not there yet or holds nonsense. */
static float game_dt(void) {
    uint64_t manager = 0;
    float dt = 0.0f;
    if (!g_slot || !bb_read(g_slot, &manager, 8) || !manager || !bb_read(manager + DT_FIELD, &dt, 4)) return 0.0f;
    return dt > 0.0005f && dt < 0.25f ? dt : 0.0f;
}

static void report(uint64_t now) {
    if (g_report && now - g_report_us >= (uint64_t)REPORT_MS * 1000u && g_frames) {
        printf("Running-jump decay: %u frames, game dt %.2f ms, clock dt %.2f ms, game used %u, "
               "clock used %u, game unusable %u, decay factor %.5f..%.5f (30 FPS: 0.95)\n",
               g_frames, g_game_used ? g_game_sum / g_game_used * 1000.0 : 0.0, g_wall_sum / g_frames * 1000.0,
               g_game_used, g_clock_used, g_game_bad, g_factor_min, g_factor_max);
        fflush(stdout);
        g_frames = g_game_used = g_clock_used = g_game_bad = 0;
        g_game_sum = g_wall_sum = 0.0;
        g_factor_min = 1.0f;
        g_factor_max = 0.0f;
    }
    if (!g_report_us || now - g_report_us >= (uint64_t)REPORT_MS * 1000u) g_report_us = now;
}

static void tick(void) {
    const uint64_t now = now_us();
    const uint64_t last = g_last_us;
    g_last_us = now;
    if (!last) {
        g_report_us = now;
        return;
    }
    const float wall = (float)(now - last) / 1e6f;
    /* The average ignores stalls, so the game's reading is compared with the usual frame. */
    g_ema_wall = g_ema_wall > 0.0f ? (wall < g_ema_wall * 4.0f ? g_ema_wall * 0.9f + wall * 0.1f : g_ema_wall) : wall;
    const float game = g_source == SOURCE_CLOCK ? 0.0f : game_dt();
    const int agrees = game > 0.0f && game > g_ema_wall * 0.5f && game < g_ema_wall * 2.0f;
    float dt = wall;
    if (g_source == SOURCE_GAME ? game > 0.0f : agrees) {
        dt = game;
        ++g_game_used;
        g_game_sum += game;
    } else {
        ++g_clock_used;
        if (g_source != SOURCE_CLOCK) ++g_game_bad;
    }
    ++g_frames;
    g_wall_sum += wall;
    bb_jump_decay_apply(dt);
    report(now);
}

int bb_jump_decay_setup(uint64_t load_at, BbCode load, uint64_t vector, uint64_t manager_slot) {
    float lanes[4];
    const unsigned char *original = bb_guest(vector);
    if (!original) return -1;  /* no image: the hooks are not initialised */
    memcpy(lanes, original, sizeof(lanes));
    /* The game's own or the preset's value: four equal lanes below one. Anything else is another
     * layout, and is left alone. */
    for (int i = 0; i < 4; ++i)
        if (!(lanes[i] > 0.5f && lanes[i] < 1.0f) || lanes[i] != lanes[0]) {
            printf("Running-jump decay: the momentum vector is not the expected one; not installed\n");
            return -1;
        }
    float *cell = bb_hooks_cell(sizeof(lanes));
    if (!cell) {
        printf("Running-jump decay: no cell for the vector; not installed\n");
        return -1;
    }
    memcpy(cell, lanes, sizeof(lanes));
    if (bb_hook_rip_operand(load_at, load, vector, cell)) {
        printf("Running-jump decay: %s; not installed\n", bb_hooks_error());
        return -1;
    }
    g_cell = cell;
    g_slot = manager_slot ? (uint64_t)(uintptr_t)bb_guest(manager_slot) : 0;
    return 0;
}

int bb_jump_decay_install(void) {
    const char *on = getenv("BB_JUMP_DT");
    if (!on || strcmp(on, "1")) return 0;
    const char *source = getenv("BB_JUMP_DT_SOURCE");
    if (source && !strcmp(source, "clock")) g_source = SOURCE_CLOCK;
    else if (source && !strcmp(source, "game")) g_source = SOURCE_GAME;
    const char *log = getenv("BB_FPS_LOG");
    g_report = !log || (log[0] && log[0] != '0');
    if (bb_jump_decay_setup(LOAD_AT, load_code, VECTOR, MANAGER_SLOT)) return 0;
    bb_on_main_frame(tick);
    printf("Running-jump decay: horizontal momentum follows the frame time (%s)\n",
           g_source == SOURCE_CLOCK ? "clock" : g_source == SOURCE_GAME ? "game's delta" : "game's delta, clock as fallback");
    return 1;
}
