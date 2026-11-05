/* SPDX-License-Identifier: GPL-2.0-or-later
 * heap_trace.c on a small executable "image" holding game 1.09's three sites. The hooked code still
 * runs and returns; the report names a block freed twice, and the panic path on a block the
 * ring has seen once does not call it a double free. The process reports once, so each case runs in
 * its own child: test_heap_trace.exe <case>. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <io.h>
#include <windows.h>
#include "engine_hooks.h"
#include "heap_trace.h"

enum { GPU_FREE = 0x11e6b00, PANIC_FREED = 0x2085914, THUNK = 0x2085f00, CALLER = 0x11e7000, IMAGE = 0x3000000 };
typedef uint64_t (BB_GUEST_ABI *Call2)(uint64_t, uint64_t);
typedef void (BB_GUEST_ABI *Free1)(uint64_t, uint64_t);

/* Heap: "spans" lines read +8 and +0x10. A block: bit 0 of the word before it clear. */
static uint64_t g_heap[8];
static uint64_t g_blocks[32];

static void build(unsigned char *image) {
    /* The free's prologue and body (kept: the hook returns here), then its epilogue. */
    static const unsigned char gpu_free[] = {0x55, 0x48, 0x89, 0xe5, 0x41, 0x57, 0x41, 0x56, 0x53, 0x48, 0x83, 0xec,
                                             0x78, 0x48, 0x83, 0xc4, 0x78, 0x5b, 0x41, 0x5e, 0x41, 0x5f, 0x5d, 0xc3};
    memcpy(image + GPU_FREE, gpu_free, sizeof(gpu_free));
    /* A caller with rdi = address, r15 = rsi (as 0x2a4b230 has the surface in r15). */
    unsigned char caller[] = {0x41, 0x57, 0x49, 0x89, 0xf7, 0xe8, 0, 0, 0, 0, 0x41, 0x5f, 0xc3};
    const int32_t to_free = GPU_FREE - (CALLER + 10);
    memcpy(caller + 6, &to_free, 4);
    memcpy(image + CALLER, caller, sizeof(caller));
    /* The panic's site, returning; a thunk with rbx = rdi, r14 = rsi that returns esi. */
    static const unsigned char panic[] = {0xbe, 0xc6, 0x02, 0x00, 0x00, 0x31, 0xc0, 0x89, 0xf0, 0xc3};
    memcpy(image + PANIC_FREED, panic, sizeof(panic));
    unsigned char thunk[] = {0x53, 0x41, 0x56, 0x48, 0x89, 0xfb, 0x49, 0x89, 0xf6, 0xe8, 0, 0, 0, 0, 0x41, 0x5e, 0x5b, 0xc3};
    const int32_t to_panic = PANIC_FREED - (THUNK + 14);
    memcpy(thunk + 10, &to_panic, 4);
    memcpy(image + THUNK, thunk, sizeof(thunk));
}

static int child(const char *name, unsigned char *image) {
    Call2 panic = (Call2)(image + THUNK);
    Free1 gpu_free = (Free1)(image + CALLER);
    const uint64_t block = (uint64_t)(uintptr_t)&g_blocks[8], heap = (uint64_t)(uintptr_t)g_heap;
    const uint64_t other = (uint64_t)(uintptr_t)&g_blocks[20];
    g_heap[1] = 0x1000, g_heap[2] = 0x2000;
    g_blocks[7] = 0x40;
    if (!strcmp(name, "twice")) {
        gpu_free(block, 0x77);
        gpu_free(other, 0x88);
        gpu_free(block, 0x99);
    } else if (!strcmp(name, "once")) {
        gpu_free(other, 0x88);
        gpu_free(block, 0x99);
    } else if (!strcmp(name, "fault")) {
        bb_heap_trace_fault(0x2000000, block, heap); /* not the heap's free: silent */
        fputs("-- in the free --\n", stderr);
        bb_heap_trace_fault(0x208599f, block, heap);
        bb_heap_trace_fault(0x208599f, block, heap); /* once */
        return 0;
    }
    const uint64_t returned = panic(block, heap);
    assert(returned == 0x2c6); /* the site's mov still ran */
    fprintf(stderr, "-- second panic --\n");
    panic(block, heap);
    return 0;
}

static char *run(const char *self, const char *name) {
    char command[MAX_PATH + 64];
    snprintf(command, sizeof(command), "\"\"%s\" %s 2>&1\"", self, name);
    FILE *p = _popen(command, "r");
    assert(p);
    static char text[16384];
    const size_t n = fread(text, 1, sizeof(text) - 1, p);
    text[n] = 0;
    assert(_pclose(p) == 0);
    return text;
}

int main(int argc, char **argv) {
    unsigned char *image = VirtualAlloc(NULL, IMAGE, MEM_RESERVE | MEM_COMMIT, PAGE_EXECUTE_READWRITE);
    assert(image);
    build(image);
    assert(bb_hooks_init(image, IMAGE) == 0);
    if (argc > 1) {
        if (strcmp(argv[1], "off") == 0) {
            _putenv("BB_HEAP_TRACE=0");
            assert(bb_heap_trace_install() == 0);
            return 0;
        }
        /* Only two sites are in this image (PANIC_RANGE is not, and is refused). */
        assert(bb_heap_trace_install() == 2);
        bb_hooks_seal();
        return child(argv[1], image);
    }

    char self[MAX_PATH];
    GetModuleFileNameA(NULL, self, sizeof(self));
    run(self, "off");

    const char *t = run(self, "twice");
    assert(strstr(t, "bad free (block not marked in use)"));
    assert(strstr(t, "DOUBLE FREE"));
    assert(strstr(t, "r15 0x77"));                 /* the first free */
    assert(strstr(t, "this free:"));
    assert(strstr(t, "r15 0x99"));                 /* this one */
    assert(strstr(t, "guest offset 0x11e700a"));   /* its caller */
    assert(strstr(t, "spans 0x1000-0x2000"));
    assert(strstr(t, "header 0x40"));
    assert(strstr(t, "surface (the caller's r15) 0x99: vtable unreadable"));
    assert(strstr(t, "recent:"));
    /* Reported once, though the panic path ran twice. */
    assert(strstr(strstr(t, "-- second panic --"), "Heap trace") == NULL);

    t = run(self, "once");
    assert(!strstr(t, "DOUBLE FREE"));
    assert(strstr(t, "no earlier free of this block among the last 2 GPU memory frees"));
    assert(strstr(t, "this free:"));

    t = run(self, "none");
    assert(!strstr(t, "DOUBLE FREE"));
    assert(!strstr(t, "this free:"));
    assert(strstr(t, "among the last 0 GPU memory frees"));

    t = run(self, "fault");
    const char *marker = strstr(t, "-- in the free --");
    assert(marker);
    assert(strstr(t, "bad free (") > marker); /* only the offset inside the free reports */
    assert(strstr(marker, "bad free (fault in the heap's free)"));

    puts("heap trace test passed");
    return 0;
}
