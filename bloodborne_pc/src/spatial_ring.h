/* SPDX-License-Identifier: GPL-2.0-or-later
 * The queue between the game's audio thread and the spatial sound thread (runtime_audio_spatial.c):
 * one writer, one reader, 8 floats a frame. The game's clock and the device's are not the same, so
 * the reader keeps the level in a band: it waits for BB_SPATIAL_START frames before it plays, starts
 * that wait again after running empty (one short gap, not a crackle on every quantum), and drops the
 * oldest frames down to BB_SPATIAL_START when the level passes BB_SPATIAL_HIGH. */
#ifndef BB_SPATIAL_RING_H
#define BB_SPATIAL_RING_H

#include <stdatomic.h>
#include <stdint.h>
#include <string.h>

enum {
    BB_SPATIAL_CHANNELS = 8,
    BB_SPATIAL_RING_FRAMES = 12000, /* 250 ms at 48 kHz */
    BB_SPATIAL_START = 1920,        /* 40 ms */
    BB_SPATIAL_HIGH = 6000,         /* 125 ms */
};

typedef struct {
    float data[BB_SPATIAL_RING_FRAMES * BB_SPATIAL_CHANNELS];
    _Atomic uint64_t written, taken; /* frames since the start */
    int playing;                     /* reader's */
    _Atomic unsigned underruns, dropped_frames;
} BbSpatialRing;

/* Writer. Frames that do not fit are lost (the reader has stopped). */
static inline void bb_spatial_ring_write(BbSpatialRing *r, const float *frames, uint32_t count) {
    uint64_t at = atomic_load_explicit(&r->written, memory_order_relaxed);
    const uint64_t taken = atomic_load_explicit(&r->taken, memory_order_acquire);
    const uint64_t room = BB_SPATIAL_RING_FRAMES - (at - taken);
    if (count > room) {
        atomic_fetch_add_explicit(&r->dropped_frames, (unsigned)(count - room), memory_order_relaxed);
        count = (uint32_t)room;
    }
    for (uint32_t i = 0; i < count; ++i, ++at)
        memcpy(&r->data[at % BB_SPATIAL_RING_FRAMES * BB_SPATIAL_CHANNELS], &frames[i * BB_SPATIAL_CHANNELS],
               BB_SPATIAL_CHANNELS * sizeof(float));
    atomic_store_explicit(&r->written, at, memory_order_release);
}

/* Reader. Fills `count` frames, per channel: out[c] is that channel's mono buffer (NULL skips it).
 * Silence stands in for whatever is not there. */
static inline void bb_spatial_ring_read(BbSpatialRing *r, float *const out[BB_SPATIAL_CHANNELS], uint32_t count) {
    const uint64_t written = atomic_load_explicit(&r->written, memory_order_acquire);
    uint64_t taken = atomic_load_explicit(&r->taken, memory_order_relaxed);
    uint64_t level = written - taken;
    if (level > BB_SPATIAL_HIGH) {
        const uint64_t drop = level - BB_SPATIAL_START;
        atomic_fetch_add_explicit(&r->dropped_frames, (unsigned)drop, memory_order_relaxed);
        taken += drop;
        level -= drop;
    }
    if (!r->playing && level >= BB_SPATIAL_START) r->playing = 1;
    uint32_t have = 0;
    if (r->playing) {
        have = level < count ? (uint32_t)level : count;
        if (have < count) {
            r->playing = 0;
            atomic_fetch_add_explicit(&r->underruns, 1u, memory_order_relaxed);
        }
    }
    for (int c = 0; c < BB_SPATIAL_CHANNELS; ++c) {
        if (!out[c]) continue;
        for (uint32_t i = 0; i < have; ++i)
            out[c][i] = r->data[(taken + i) % BB_SPATIAL_RING_FRAMES * BB_SPATIAL_CHANNELS + (unsigned)c];
        for (uint32_t i = have; i < count; ++i) out[c][i] = 0.f;
    }
    atomic_store_explicit(&r->taken, taken + have, memory_order_release);
}

#endif
