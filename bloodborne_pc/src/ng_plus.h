/* SPDX-License-Identifier: GPL-2.0-or-later
 * NG+7 world's runtime (ng_plus.c): on when run.py made the Hunter's Dream's rune gift
 * (BB_PC_NG7_ACTIVE=1, from pc_ng_plus_7 / BB_PC_NG7). */
#ifndef BB_NG_PLUS_H
#define BB_NG_PLUS_H

/* Hooks where the game loads, resets, saves and raises its NG cycle and registers the main-thread
 * tick; returns hooks added. */
int bb_ng_plus_install(void);

#endif
