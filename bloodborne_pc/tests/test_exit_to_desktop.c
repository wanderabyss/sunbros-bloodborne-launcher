/* Standalone flow test: clang -O2 -ffunction-sections -fdata-sections -I bloodborne_pc
 * bloodborne_pc/tests/test_exit_to_desktop.c -Wl,--gc-sections -o exit-test.exe */
#include <assert.h>
#include <stdlib.h>
#include "../src/pc_menu.c"

static int hides, saves, titles, quits, order, frontend;
static BB_GUEST_ABI int64_t save_action(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f) {
    assert(hides == saves + 1); ++saves; order = 1; return 42;
}
static BB_GUEST_ABI int64_t title_action(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f) {
    ++titles; if (saves) { assert(order == 1 || order == 2); order = 2; } return 0;
}
void *bb_guest(uint64_t at) {
    if (at == BB_BN(0x200d050)) return (void *)save_action;
    if (at == BB_BN(TITLE_FINALIZE)) return (void *)title_action;
    abort();
}
void bbgpu_hide_for_exit(void) { ++hides; }
void bbgpu_request_quit(void) { assert(order == 2); ++quits; }
int bb_hook_call(uint64_t at, uint64_t target, void *host) { abort(); }
const char *bb_hooks_error(void) { abort(); }
int bb_patch(uint64_t at, const void *expected, const void *replacement, size_t n) { abort(); }
int bb_menu_frontend_ready(void) { if (frontend) order = 2; return frontend; }
int main(void) {
    /* Startup/title and cancel (no YES callback) must never hide or quit. */
    title_finalize(NULL,NULL,NULL); assert(!hides && !quits);
    assert(exit_to_title_yes(0,0,0,0,0,0) == 42);
    assert(saves == 1 && hides == 1 && quits == 0);
    title_finalize(NULL,NULL,NULL); assert(quits == 1);
    title_finalize(NULL,NULL,NULL); assert(quits == 1);
    exit_to_title_yes(0,0,0,0,0,0);
    bb_pc_menu_frame(); assert(quits == 1); /* Still saving/transitioning. */
    frontend = 1;
    bb_pc_menu_frame(); assert(quits == 2); /* Press Any Button needs no input. */
    bb_pc_menu_frame(); assert(quits == 2);
    return 0;
}
