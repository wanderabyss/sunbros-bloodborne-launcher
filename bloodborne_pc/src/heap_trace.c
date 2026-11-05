/* SPDX-License-Identifier: GPL-2.0-or-later
 * Heap trace: names the block behind a Dantelion2 heap panic.
 *
 * Crashes in the field end with DLRegularHeap.cpp(710) "given memory block seems to be improper or
 * freed already", reached from YEBIS tearing down its GPU surfaces, and the game's message does not
 * say which block. Its free (0x20858a0) takes the block in rsi and keeps it in rbx with the heap in
 * r14; the word at block - 8 points at the next block, and bit 0 says this one is in use.
 *
 * - GPU_FREE (0x11e6b00), the free of a surface's memory, adds each address to a small ring, with
 *   its caller and the caller's r15 (the surface, when 0x2a4b230 calls). It runs a few times a frame
 *   at most, so the ring costs nothing to speak of.
 * - PANIC_FREED and PANIC_RANGE are on the panics' own paths and never run in a healthy game. They
 *   print the block, its header and neighbours, then whether the ring saw it freed before: a
 *   double free, or a bad address.
 *
 * The ring is written without a lock from any thread and read only as the process ends: a line
 * can be torn when two threads free at that moment, which only misleads this report.
 *
 * Addresses are image offsets (eboot virtual address minus 0x400000). */
#include "heap_trace.h"
#include "engine_hooks.h"

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum {
    GPU_FREE_BODY = 0x11e6b04, /* after the frame is set up: [rbp + 8] is the caller */
    PANIC_RANGE = 0x20858dd,   /* mov esi, 0x2bb; xor eax, eax: "does not seem to belong here" */
    PANIC_FREED = 0x2085914,   /* mov esi, 0x2c6; xor eax, eax: "improper or freed already" */
    HEAP_FREE = 0x20858a0,
    HEAP_FREE_END = 0x2085b00,
    HEAP_BEGIN = 8,
    HEAP_END = 0x10,
    SURFACE_DESCRIPTOR = 0xc0, /* the base 0x2a4b230 frees is read from +0xc4 */
    RING = 256,
    SHOW_RECENT = 12,
};
static const BbCode gpu_free_code = {9, 0xdaef2df641d2e3e2ull};
static const BbCode panic_range_code = {7, 0x95146793eaa6bb9dull};
static const BbCode panic_freed_code = {7, 0xd5d2b21878b347fcull};

typedef struct {
    uint64_t address, caller, surface, ms;
    unsigned long thread;
} Free;

static Free g_ring[RING];
static uint32_t g_next;
static int g_reported;

#if defined(_WIN32)
#include <windows.h>
static uint64_t now_ms(void) { return GetTickCount64(); }
static unsigned long thread_id(void) { return GetCurrentThreadId(); }
#else
#include <time.h>
static uint64_t now_ms(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * 1000u + (uint64_t)t.tv_nsec / 1000000u;
}
static unsigned long thread_id(void) { return 0; }
#endif

static void describe(char *out, size_t size, uint64_t address) {
    const uint64_t image = (uint64_t)(uintptr_t)bb_guest(0);
    if (address - image < 0x20000000u)
        snprintf(out, size, "guest offset %#" PRIx64, address - image);
    else
        snprintf(out, size, "%#" PRIx64, address);
}

static void dump(const char *name, uint64_t at) {
    uint64_t w[4];
    if (bb_read(at, w, sizeof(w)))
        fprintf(stderr, "Heap trace: %s (%#" PRIx64 "): %016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %016" PRIx64 "\n",
                name, at, w[0], w[1], w[2], w[3]);
    else
        fprintf(stderr, "Heap trace: %s (%#" PRIx64 "): unreadable\n", name, at);
}

static void print_free(const char *label, const Free *f, uint64_t now) {
    char caller[64];
    describe(caller, sizeof(caller), f->caller);
    fprintf(stderr, "Heap trace: %s %#" PRIx64 ", %" PRIu64 " ms ago, from %s, r15 %#" PRIx64 ", thread %lu\n", label,
            f->address, now - f->ms, caller, f->surface, f->thread);
}

static void report(uint64_t block, uint64_t heap, const char *why) {
    if (__atomic_exchange_n(&g_reported, 1, __ATOMIC_ACQ_REL)) return;
    fflush(stdout);
    const uint64_t now = now_ms();
    uint64_t header = 0, bounds[2] = {0, 0};
    const int have_header = block >= 8 && bb_read(block - 8, &header, sizeof(header));
    const int have_heap = bb_read(heap + HEAP_BEGIN, bounds, sizeof(bounds));
    fprintf(stderr, "Heap trace: bad free (%s) of block %#" PRIx64 ", header %s%#" PRIx64 "\n", why, block,
            have_header ? "" : "unreadable, ", header);
    fprintf(stderr, have_heap ? "Heap trace: heap %#" PRIx64 " spans %#" PRIx64 "-%#" PRIx64 "\n"
                              : "Heap trace: heap %#" PRIx64 " is unreadable\n",
            heap, bounds[0], bounds[1]);
    if (block >= 0x20) dump("before the block", block - 0x20);
    dump("the block", block);

    /* Newest first. A free through GPU_FREE is in the ring itself, as this thread's newest entry for
     * the block: only older entries mean it was freed before. */
    const uint32_t next = __atomic_load_n(&g_next, __ATOMIC_ACQUIRE);
    const uint32_t count = next < RING ? next : RING;
    const unsigned long me = thread_id();
    const Free *current = NULL;
    unsigned earlier = 0;
    for (uint32_t i = 1; i <= count; ++i) {
        const Free *f = &g_ring[(next - i) % RING];
        if (f->address != block) continue;
        if (!current && !earlier && f->thread == me) {
            current = f;
            continue;
        }
        if (!earlier++) fputs("Heap trace: DOUBLE FREE: this block was already freed:\n", stderr);
        print_free("  freed", f, now);
    }
    if (!earlier)
        fprintf(stderr, "Heap trace: no earlier free of this block among the last %u GPU memory frees: a bad address "
                        "or an overwritten header, or a free by another route\n", (unsigned)count);
    if (current) {
        print_free("this free:", current, now);
        uint64_t table = 0;
        char where[64] = "unreadable";
        if (bb_read(current->surface, &table, sizeof(table))) describe(where, sizeof(where), table);
        fprintf(stderr, "Heap trace: surface (the caller's r15) %#" PRIx64 ": vtable %s\n", current->surface, where);
        dump("surface + 0xc0", current->surface + SURFACE_DESCRIPTOR);
    }
    for (uint32_t i = 1; i <= count && i <= SHOW_RECENT; ++i) print_free("recent:", &g_ring[(next - i) % RING], now);
    fflush(stderr);
}

static void BB_GUEST_ABI on_gpu_free(BbRegs *r) {
    uint64_t caller = 0;
    bb_read(r->rbp + 8, &caller, sizeof(caller));
    const uint32_t i = __atomic_fetch_add(&g_next, 1u, __ATOMIC_ACQ_REL);
    Free *f = &g_ring[i % RING];
    f->address = r->rdi;
    f->caller = caller;
    f->surface = r->r15;
    f->ms = now_ms();
    f->thread = thread_id();
}

static void BB_GUEST_ABI on_panic_range(BbRegs *r) { report(r->rbx, r->r14, "outside its heap"); }
static void BB_GUEST_ABI on_panic_freed(BbRegs *r) { report(r->rbx, r->r14, "block not marked in use"); }

void bb_heap_trace_fault(uint64_t guest_offset, uint64_t rbx, uint64_t r14) {
    if (guest_offset >= HEAP_FREE && guest_offset < HEAP_FREE_END) report(rbx, r14, "fault in the heap's free");
}

int bb_heap_trace_install(void) {
    const char *on = getenv("BB_HEAP_TRACE");
    if (on && !strcmp(on, "0")) return 0;
    static const struct {
        uint64_t at;
        const BbCode *code;
        void(BB_GUEST_ABI *host)(BbRegs *);
    } sites[] = {{GPU_FREE_BODY, &gpu_free_code, on_gpu_free},
                 {PANIC_RANGE, &panic_range_code, on_panic_range},
                 {PANIC_FREED, &panic_freed_code, on_panic_freed}};
    int hooks = 0;
    for (size_t i = 0; i < sizeof(sites) / sizeof(*sites); ++i) {
        if (bb_hook_mid(sites[i].at, *sites[i].code, sites[i].host))
            printf("Heap trace: %#llx not hooked (%s)\n", (unsigned long long)sites[i].at, bb_hooks_error());
        else
            ++hooks;
    }
    printf("Heap trace: %d of %u hooks; a rejected free is described in lines starting \"Heap trace\"\n", hooks,
           (unsigned)(sizeof(sites) / sizeof(*sites)));
    return hooks;
}
