/* SPDX-License-Identifier: GPL-2.0-or-later
 * Mouse camera: the mouse turns the camera directly, 1:1, like a PC game, instead of through the
 * right stick's deadzone and turn curve. Camera code and fields from imedved's Bloodborne mouse
 * camera (Nexus Mods), as ported to bbport by mcrib884 (Supermedo/bloodborne_pc#3) and
 * Jhony-Jhansen (Supermedo/bloodborne_pc#23). */
#ifndef BB_MOUSE_CAMERA_H
#define BB_MOUSE_CAMERA_H

#include <stdint.h>

/* Hooks the camera update (game 1.09; refused, changing nothing, on other code). Returns the
 * number of hooks installed. BB_MOUSE_CAMERA=0 or the PC menu's Mouse Camera turns it off. */
int bb_mouse_camera_install(void);

/* For the pad read: while locked on, a mouse flick is a right-stick flick (switches target).
 * Returns the right stick's x (0..255), or -1 when the mouse has nothing to add. */
int bb_mouse_camera_stick_x(void);

/* The pad read tells the camera when the right stick (a gamepad or bound keys) is turning it:
 * the game's own camera code then runs as usual. */
void bb_mouse_camera_note_stick(uint8_t right_x, uint8_t right_y);

#endif
