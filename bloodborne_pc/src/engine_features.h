/* SPDX-License-Identifier: GPL-2.0-or-later
 * The PC features that hook the engine (engine_hooks.h), installed once at load while the image
 * is writable. Each feature has its own bbport.ini key and BB_* override, defaults to the game
 * as shipped, and leaves the image unchanged when its bytes are not the expected 1.09 ones. */
#ifndef BB_ENGINE_FEATURES_H
#define BB_ENGINE_FEATURES_H

#ifdef __cplusplus
extern "C" {
#endif

/* Installs every enabled feature's hooks; returns how many hooks went in. */
int bb_engine_install(void);

/* Once a frame, on the game's thread that submits the frame (sceVideoOutSubmitFlip). */
void bb_engine_frame(void);

#ifdef __cplusplus
}
#endif

#endif
