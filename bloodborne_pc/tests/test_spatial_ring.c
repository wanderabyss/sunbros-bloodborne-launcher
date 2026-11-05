/* SPDX-License-Identifier: GPL-2.0-or-later
 * spatial_ring.h: channels stay apart and in order, playback waits for the lead, an empty queue is
 * silence with one underrun and a new wait, and a queue that runs long drops its oldest frames. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "spatial_ring.h"

static BbSpatialRing ring;
static float out_buffers[BB_SPATIAL_CHANNELS][BB_SPATIAL_RING_FRAMES];
static uint32_t next_frame;

/* Each sample says which frame and channel it is. */
static void write_frames(uint32_t count) {
    static float frames[4096 * BB_SPATIAL_CHANNELS];
    assert(count <= 4096);
    for (uint32_t i = 0; i < count; ++i, ++next_frame)
        for (int c = 0; c < BB_SPATIAL_CHANNELS; ++c) frames[i * BB_SPATIAL_CHANNELS + (unsigned)c] = (float)(next_frame * 10 + (unsigned)c + 1);
    bb_spatial_ring_write(&ring, frames, count);
}

static void read_frames(uint32_t count) {
    float *out[BB_SPATIAL_CHANNELS];
    for (int c = 0; c < BB_SPATIAL_CHANNELS; ++c) out[c] = out_buffers[c];
    bb_spatial_ring_read(&ring, out, count);
}

int main(void) {
    /* Not enough for the lead yet: silence, and no underrun, since it never played. */
    write_frames(BB_SPATIAL_START - 1);
    out_buffers[0][0] = 99.f;
    read_frames(480);
    assert(out_buffers[0][0] == 0.f);
    assert(atomic_load(&ring.underruns) == 0);
    assert(atomic_load(&ring.taken) == 0);

    /* The lead is there: it plays from the first frame, each channel its own. */
    write_frames(1);
    read_frames(480);
    for (int c = 0; c < BB_SPATIAL_CHANNELS; ++c) {
        assert(out_buffers[c][0] == (float)(c + 1));
        assert(out_buffers[c][479] == (float)(4790 + c + 1));
    }

    /* A skipped channel leaves the others alone. */
    float *some[BB_SPATIAL_CHANNELS] = {NULL, out_buffers[1]};
    bb_spatial_ring_read(&ring, some, 480);
    assert(out_buffers[1][0] == (float)(4800 + 2));

    /* Empty: what is left, then silence, one underrun, and a new wait for the lead. */
    read_frames(480);
    assert(atomic_load(&ring.underruns) == 0);
    read_frames(300);
    assert(atomic_load(&ring.underruns) == 0);
    read_frames(300); /* 180 frames left */
    assert(out_buffers[0][179] != 0.f);
    assert(out_buffers[0][180] == 0.f);
    assert(atomic_load(&ring.underruns) == 1);
    read_frames(480);
    assert(out_buffers[0][0] == 0.f);
    assert(atomic_load(&ring.underruns) == 1);
    const uint32_t resume = next_frame;
    write_frames(BB_SPATIAL_START);
    read_frames(480);
    assert(out_buffers[0][0] == (float)(resume * 10 + 1));

    /* Over the high mark: back to the lead, keeping the newest frames. */
    while (atomic_load(&ring.written) - atomic_load(&ring.taken) <= BB_SPATIAL_HIGH) write_frames(1024);
    const unsigned before = atomic_load(&ring.dropped_frames);
    const uint64_t level = atomic_load(&ring.written) - atomic_load(&ring.taken);
    read_frames(480);
    assert(atomic_load(&ring.dropped_frames) - before == level - BB_SPATIAL_START);
    assert(out_buffers[0][0] == (float)((next_frame - BB_SPATIAL_START) * 10 + 1));
    assert(atomic_load(&ring.written) - atomic_load(&ring.taken) == BB_SPATIAL_START - 480);

    /* A stopped reader: the writer keeps what fits and counts the rest, across the ring's end. */
    while (atomic_load(&ring.written) - atomic_load(&ring.taken) + 4096 <= BB_SPATIAL_RING_FRAMES) write_frames(4096);
    const unsigned full_before = atomic_load(&ring.dropped_frames);
    const uint64_t room = BB_SPATIAL_RING_FRAMES - (atomic_load(&ring.written) - atomic_load(&ring.taken));
    write_frames(4096);
    assert(atomic_load(&ring.written) - atomic_load(&ring.taken) == BB_SPATIAL_RING_FRAMES);
    assert(atomic_load(&ring.dropped_frames) - full_before == 4096 - room);

    puts("spatial ring: ok");
    return 0;
}
