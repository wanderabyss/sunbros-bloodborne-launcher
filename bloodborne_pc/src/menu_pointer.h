/* SPDX-License-Identifier: GPL-3.0-or-later
 * Mouse pointer in the game's menus (menu_pointer.c), after droogie's bbhost
 * (https://github.com/droogie/bbhost, engine/menu_pointer.cpp). Hovering a row moves the game's
 * own cursor there, a left click decides (or steps an option's value), a right click goes back
 * and the wheel scrolls. mouse_menu=0 in bbport.ini or BB_MOUSE_MENU=0 turns it off. */
#ifndef BB_MENU_POINTER_H
#define BB_MENU_POINTER_H

#include <stdint.h>

/* Checks the game's list code and arms the pointer; returns 1 when it is on. The list update
 * hook itself is pc_menu.c's (bb_menu_lists_hook). */
int bb_menu_pointer_install(void);
/* Turns it off again (the list hook was refused). */
void bb_menu_pointer_off(void);
/* From every menu list's update, before the game's own: moves the cursor to the row under the
 * pointer and turns a click into a press. `input` is the list's focus byte. */
void bb_menu_pointer_step(unsigned char *comp, const unsigned char *input);
/* Once a frame: tells the window whether a menu owns the mouse (it shows the pointer). */
void bb_menu_pointer_frame(void);
/* Front-end flow is active and no transition blocks input (including Press Any Button). */
int bb_menu_frontend_ready(void);

/* From the pad read (runtime_pad.c). Whether the pointer owns the mouse buttons now: then a
 * left click is bb_menu_pointer_click(), a right click the game's back button, and the buttons'
 * gameplay bindings are skipped. */
int bb_menu_pointer_owns_mouse(void);
void bb_menu_pointer_click(void);
/* The pad buttons a click or a right click asks for; held for a short press. */
uint32_t bb_menu_pointer_buttons(void);
/* A right click: the game's back button (Circle, or Cross in the Japanese layout). */
void bb_menu_pointer_back(void);

#endif
