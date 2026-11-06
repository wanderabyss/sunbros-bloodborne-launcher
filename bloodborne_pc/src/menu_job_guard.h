/* SPDX-License-Identifier: GPL-2.0-or-later
 * Skips a queued menu job whose menu has already been freed (menu_job_guard.c). */
#ifndef BB_MENU_JOB_GUARD_H
#define BB_MENU_JOB_GUARD_H

#ifdef __cplusplus
extern "C" {
#endif

/* Returns the number of hooks placed: 1, or 0 when game 1.09's code is not there. */
int bb_menu_job_guard_install(void);

#ifdef __cplusplus
}
#endif

#endif
