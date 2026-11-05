/* SPDX-License-Identifier: GPL-2.0-or-later
 * Windows spatial sound for the game's 7.1 mix (runtime_audio_spatial.c). */
#ifndef BB_RUNTIME_AUDIO_SPATIAL_H
#define BB_RUNTIME_AUDIO_SPATIAL_H

#include <stdint.h>

/* Starts the stream on the default output when a spatial sound format is on for it (Dolby Atmos,
 * Windows Sonic, DTS) and BB_AUDIO_SPATIAL is not 0. One at a time. Returns 1 when it plays. */
int runtime_audio_spatial_open(void);
/* Queues frames of 8 floats, in SDL's 7.1 order (FL FR FC LFE BL BR SL SR). Returns 0 once the
 * stream has ended (the output changed): the caller goes back to its ordinary path. */
int runtime_audio_spatial_write(const float *frames, uint32_t count);
void runtime_audio_spatial_close(void);

#endif
