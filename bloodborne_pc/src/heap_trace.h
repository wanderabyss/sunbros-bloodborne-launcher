/* SPDX-License-Identifier: GPL-2.0-or-later
 * Heap trace (heap_trace.c): when the game's heap rejects a free ("given memory block seems to be
 * improper or freed already"), says in last_run.log which block it was and whether it was freed
 * before. On by default; BB_HEAP_TRACE=0 turns it off. */
#ifndef BB_HEAP_TRACE_H
#define BB_HEAP_TRACE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Hooks game 1.09's GPU memory free and the heap's two panics. Returns the number of hooks
 * installed; a site whose code differs is left alone. */
int bb_heap_trace_install(void);

/* The process is about to end on a fault at this guest offset: when that is inside the heap's free
 * (a damaged block header faults there instead of panicking), reports rbx's block from r14's heap. */
void bb_heap_trace_fault(uint64_t guest_offset, uint64_t rbx, uint64_t r14);

#ifdef __cplusplus
}
#endif

#endif
