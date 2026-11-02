/* SPDX-License-Identifier: GPL-2.0-or-later
 * Damage log (damage_log.c): every change of a character's HP, as lines in the game's output
 * (last_run.log), for balancing weapons. BB_DAMAGE_LOG=1 (bbport.ini damage_log=1) turns it on. */
#ifndef BB_DAMAGE_LOG_H
#define BB_DAMAGE_LOG_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Hooks game 1.09's HP setters when BB_DAMAGE_LOG=1. Returns the number of hooks installed;
 * a site whose code differs is left alone. */
int bb_damage_log_install(void);

/* Test seam: one HP change as a hook sees it, then the main-thread tick that prints it. */
void bb_damage_log_record(uint64_t module, int32_t old_hp, int32_t new_hp, int32_t max_hp);
void bb_damage_log_flush(void);

#ifdef __cplusplus
}
#endif

#endif
