/* SPDX-License-Identifier: GPL-2.0-or-later
 * jump_decay.c on a small executable "image": the momentum multiply is pointed at a cell only
 * when its bytes, its operand and the vector are the expected ones (a refusal changes nothing),
 * the game's own vector is never written, and the cell the multiply reads follows the frame
 * time as 0.95 ** (30 dt), limited so a stall or a bad reading cannot stop or launch the
 * character. */
#include <assert.h>
#include <immintrin.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <windows.h>
#include "engine_hooks.h"
#include "jump_decay.h"

enum { LOAD = 0x100, VECTOR = 0x800, WRONG_VECTOR = 0x820, IMAGE = 0x2000 };
/* vmulps xmm0, xmm0, [rip + disp32]; ret - the displacement is filled in below. */
static const unsigned char vmulps_code[] = {0xc5, 0xf8, 0x59, 0x05, 0, 0, 0, 0};
typedef __m128 (BB_GUEST_ABI *MulFn)(__m128);

static float lane(__m128 v, int i) {
    float out[4];
    _mm_storeu_ps(out, v);
    return out[i];
}

static void expect_all(__m128 v, float want) {
    for (int i = 0; i < 4; ++i) assert(fabsf(lane(v, i) - want) < 1e-3f);
}

int main(void) {
    unsigned char *image = VirtualAlloc(NULL, IMAGE, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    assert(image);
    memset(image, 0xcc, IMAGE);
    memcpy(image + LOAD, vmulps_code, sizeof(vmulps_code));
    const int32_t disp = VECTOR - (LOAD + (int32_t)sizeof(vmulps_code));
    memcpy(image + LOAD + 4, &disp, 4);
    image[LOAD + 8] = 0xc3;
    const float game[4] = {0.95f, 0.95f, 0.95f, 0.95f};
    memcpy(image + VECTOR, game, sizeof(game));
    memcpy(image + VECTOR + 16, game, sizeof(game));  /* a valid vector the operand does not address */
    const float other[4] = {0.95f, 0.9f, 0.95f, 0.95f};
    memcpy(image + WRONG_VECTOR, other, sizeof(other));

    const BbCode load = {sizeof(vmulps_code), bb_code_hash(image + LOAD, sizeof(vmulps_code))};

    /* The factor: the game's 0.95 at 30 FPS, and the rate's value at the others. */
    assert(fabsf(bb_jump_decay_factor(1.0f / 30.0f) - 0.95f) < 1e-6f);
    assert(fabsf(bb_jump_decay_factor(1.0f / 60.0f) - 0.97467943f) < 1e-6f);
    assert(fabsf(bb_jump_decay_factor(1.0f / 120.0f) - 0.98726f) < 1e-4f);
    assert(fabsf(bb_jump_decay_factor(1.0f / 144.0f) - powf(0.95f, 30.0f / 144.0f)) < 1e-6f);
    /* Limits: a stall decays like 1/20 s, a zero, negative or NaN reading like 1/480 s. */
    assert(fabsf(bb_jump_decay_factor(10.0f) - powf(0.95f, 1.5f)) < 1e-6f);
    assert(fabsf(bb_jump_decay_factor(0.0f) - powf(0.95f, 30.0f / 480.0f)) < 1e-6f);
    assert(fabsf(bb_jump_decay_factor(-1.0f) - powf(0.95f, 30.0f / 480.0f)) < 1e-6f);
    assert(fabsf(bb_jump_decay_factor(NAN) - powf(0.95f, 30.0f / 480.0f)) < 1e-6f);
    assert(bb_jump_decay_factor(1.0f / 144.0f) > bb_jump_decay_factor(1.0f / 60.0f));  /* shorter frame, less decay */

    /* Nothing is installed before the hooks are: no image. */
    assert(bb_jump_decay_setup(LOAD, load, VECTOR, 0) == -1);

    assert(bb_hooks_init(image, IMAGE) == 0);
    unsigned char before[IMAGE];
    memcpy(before, image, IMAGE);

    /* Refusals change nothing: other code, another constant, another vector. */
    const BbCode wrong_code = {sizeof(vmulps_code), load.hash ^ 1};
    assert(bb_jump_decay_setup(LOAD, wrong_code, VECTOR, 0) == -1);
    assert(bb_jump_decay_setup(LOAD, load, WRONG_VECTOR, 0) == -1);  /* the lanes differ, and the operand */
    assert(bb_jump_decay_setup(LOAD, load, VECTOR + 16, 0) == -1);   /* the operand is not that constant */
    assert(!memcmp(before, image, IMAGE));
    assert(bb_hook_rip_operand(LOAD, load, VECTOR, NULL) == -1);
    assert(bb_hooks_cell(0) == NULL && bb_hooks_cell(65) == NULL);
    assert(!memcmp(before, image, IMAGE));

    /* Installed: the multiply reads a cell that starts as the game's value. */
    assert(bb_jump_decay_setup(LOAD, load, VECTOR, 0) == 0);
    assert(memcmp(before + LOAD, image + LOAD, 8) != 0);               /* the operand moved */
    assert(!memcmp(before + VECTOR, image + VECTOR, 16));              /* the game's vector did not */
    assert(!memcmp(before + LOAD + 8, image + LOAD + 8, IMAGE - LOAD - 8));
    assert(bb_jump_decay_setup(LOAD, load, VECTOR, 0) == -1);          /* already redirected */

    bb_hooks_seal();
    DWORD old;
    assert(VirtualProtect(image, IMAGE, PAGE_EXECUTE_READ, &old));
    FlushInstructionCache(GetCurrentProcess(), image, IMAGE);
    MulFn multiply = (MulFn)(image + LOAD);

    expect_all(multiply(_mm_set1_ps(100.0f)), 95.0f);
    bb_jump_decay_apply(1.0f / 60.0f);
    expect_all(multiply(_mm_set1_ps(100.0f)), 97.4679f);
    bb_jump_decay_apply(1.0f / 120.0f);
    expect_all(multiply(_mm_set1_ps(100.0f)), 98.726f);
    bb_jump_decay_apply(1.0f / 30.0f);
    expect_all(multiply(_mm_set1_ps(100.0f)), 95.0f);
    bb_jump_decay_apply(10.0f);
    expect_all(multiply(_mm_set1_ps(100.0f)), 100.0f * powf(0.95f, 1.5f));
    /* Whatever the rate, a second of frames decays like a second of the 30 FPS game's. */
    for (int fps = 45; fps <= 360; fps += 45) {
        bb_jump_decay_apply(1.0f / (float)fps);
        float momentum = 100.0f;
        for (int frame = 0; frame < fps; ++frame) momentum = lane(multiply(_mm_set1_ps(momentum)), 0);
        assert(fabsf(momentum - 100.0f * powf(0.95f, 30.0f)) < 0.05f);
    }
    puts("jump decay: ok");
    return 0;
}
