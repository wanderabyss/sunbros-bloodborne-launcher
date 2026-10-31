#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <direct.h>
#include <process.h>
#include <time.h>

static char user_dir[900];
static int64_t visible[128];
static int toasts;

const char *runtime_file_user_dir(void) { return user_dir; }
void bbgpu_trophy_load(const int64_t *flags, uint32_t count) {
    assert(count == 128);
    memcpy(visible, flags, count * sizeof(visible[0]));
}
void bbgpu_trophy_unlocked(int32_t id, int64_t timestamp) {
    assert(id >= 0 && id < 128);
    visible[id] = timestamp;
    ++toasts;
}
void runtime_trophy_configure(void);
int runtime_trophy_unlock(int id);

int main(int argc, char **argv) {
    assert(argc == 2);
    int length = snprintf(user_dir, sizeof(user_dir), "%s/trophy-test-%lld-%u", argv[1],
                          (long long)time(NULL), (unsigned)_getpid());
    assert(length > 0 && (size_t)length < sizeof(user_dir));
    assert(_mkdir(user_dir) == 0);
    runtime_trophy_configure();
    assert(!visible[7] && !visible[127]);
    assert(runtime_trophy_unlock(7) == 1);
    assert(runtime_trophy_unlock(7) == 0);
    assert(runtime_trophy_unlock(127) == 1);
    assert(runtime_trophy_unlock(-1) == -1);
    assert(runtime_trophy_unlock(128) == -1);
    assert(toasts == 2);
    memset(visible, 0, sizeof(visible));
    runtime_trophy_configure();
    assert(visible[7] && visible[127]);
    assert(visible[7] > 1000000000 && visible[127] > 1000000000);
    assert(runtime_trophy_unlock(7) == 0 && toasts == 2);
    puts("trophy history: persistence, duplicate suppression, and ID bounds passed");
    return 0;
}
