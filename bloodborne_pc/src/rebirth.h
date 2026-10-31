/* SPDX-License-Identifier: GPL-2.0-or-later
 * Rebirth in the Nightmare's runtime (rebirth.c): on when run.py made the altar's script
 * (BB_PC_REBIRTH_ACTIVE=1, from pc_rebirth / BB_PC_REBIRTH). */
#ifndef BB_REBIRTH_H
#define BB_REBIRTH_H

/* Hooks the menu step constructor and registers the main-thread tick; returns hooks added. */
int bb_rebirth_install(void);

#endif
