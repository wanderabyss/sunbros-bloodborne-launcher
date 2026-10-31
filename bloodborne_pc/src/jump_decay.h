/* SPDX-License-Identifier: GPL-2.0-or-later
 * Running-jump momentum at an uncapped frame rate (jump_decay.c). The fixed presets (60/90/120/144)
 * write one decay value for their rate (patches.py running_jump); uncapped has no one rate, so the
 * game's decay vector is updated each frame from the frame time instead. */
#ifndef BB_JUMP_DECAY_H
#define BB_JUMP_DECAY_H

#include "code_check.h"

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* The factor the game's 0.95 per 30-FPS frame becomes for a frame of `dt` seconds: 0.95 ** (30 dt).
 * dt is limited to 1/480..1/20 s, so a stall frame cannot stop the character and a bad reading
 * cannot make it slide. */
float bb_jump_decay_factor(float dt);

/* Hooks the momentum multiply of game 1.09 when BB_JUMP_DT=1 (run.py sets it for the uncapped
 * preset; BB_RUNNING_JUMP_FIX=0 / running_jump_fix=0 leave it unset). Returns the number of hooks
 * installed; refused, changing nothing, on other code. */
int bb_jump_decay_install(void);

/* Test seam: the same set-up for another site, vector and frame-manager slot (image offsets).
 * Returns 0 when installed. */
int bb_jump_decay_setup(uint64_t load_at, BbCode load, uint64_t vector, uint64_t manager_slot);
/* Test seam: writes the cell for a frame of `dt` seconds. */
void bb_jump_decay_apply(float dt);

#ifdef __cplusplus
}
#endif

#endif
