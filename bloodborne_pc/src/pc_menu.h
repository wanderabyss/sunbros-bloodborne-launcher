/* SPDX-License-Identifier: GPL-2.0-or-later
 * The in-game PC menu (pc_menu.c): System > PC Settings and PC Enhancements. On when its assets
 * were made (BB_PC_MENU_ASSETS=1, run.py); BB_PC_MENU=0 turns it off. */
#ifndef BB_PC_MENU_H
#define BB_PC_MENU_H

/* Installs guarded desktop-exit hooks and optional menu hooks. Returns installed count.
 * BB_EXIT_TO_DESKTOP=0 keeps the original in-game return-to-title behavior. */
int bb_pc_menu_install(void);
/* Once a frame: the rows' changes become bbport.ini settings. */
void bb_pc_menu_frame(void);
/* Hooks every menu list's update (once; the PC menu and the menu pointer share it). Returns how
 * many hooks went in now. */
int bb_menu_lists_hook(void);
/* Whether that hook is in. */
int bb_menu_lists_hooked(void);

#endif
