/* The list of files over the game (BB_APP0_LAYER, scripts/mods.py build_layer), through the file
 * layer's own translate and folder listing. Argument: an empty folder. Built and run by
 * tests/test_runtime_file_layer.py. */
#include "../src/runtime_file.c"
#include <assert.h>

/* What the rest of the runtime gives runtime_file.c; none of it runs here. */
int compat_errno_from_win32(unsigned long error) { (void)error; return EIO; }
ssize_t compat_pread(int fd, void *buffer, size_t size, int64_t offset) { (void)fd; (void)buffer; (void)size; (void)offset; return -1; }
ssize_t compat_pwrite(int fd, const void *buffer, size_t size, int64_t offset) { (void)fd; (void)buffer; (void)size; (void)offset; return -1; }
int32_t *runtime_errno(void) { static int32_t value; return &value; }
int32_t runtime_guest_errno(int host_errno) { return host_errno; }
uintptr_t runtime_lookup(const RuntimeExport *table, size_t count, const char *nid) { (void)table; (void)count; (void)nid; return 0; }

static char root[512];

static void put(const char *relative) {
    char path[800];
    snprintf(path, sizeof(path), "%s/%s", root, relative);
    for (char *p = path + strlen(root) + 1; *p; ++p)
        if (*p == '/') { *p = 0; mkdir(path, 0755); *p = '/'; }
    FILE *f = fopen(path, "wb");
    assert(f);
    fputs(relative, f);
    fclose(f);
}

static void expect(const char *guest, const char *relative) {
    char out[1024], want[800];
    assert(!runtime_file_translate(guest, out, sizeof(out)));
    snprintf(want, sizeof(want), "%s/%s", root, relative);
    if (strcmp(out, want)) { fprintf(stderr, "%s -> %s, not %s\n", guest, out, want); exit(1); }
}

/* How many times `name` is listed, and its type. */
static int listed(const Listing *l, const char *name, int *type) {
    int count = 0;
    for (size_t i = 0; i < l->count; ++i)
        if (!strcmp(l->names + l->offsets[i], name)) { ++count; *type = l->types[i]; }
    return count;
}

int main(int argc, char **argv) {
    assert(argc == 2);
    snprintf(root, sizeof(root), "%s", argv[1]);
    put("game/eboot.bin");
    put("game/dvdroot_ps4/chr/a.dcx");
    put("game/dvdroot_ps4/chr/b.dcx");
    put("mod/dvdroot_ps4/chr/a.dcx");
    put("mod/dvdroot_ps4/chr/New.dcx");
    put("mod/dvdroot_ps4/Extra/deep/c.dcx");

    char path[800], game[800], user[800];
    snprintf(path, sizeof(path), "%s/list.txt", root);
    FILE *list = fopen(path, "w");
    assert(list);
    fprintf(list, "dvdroot_ps4/chr/a.dcx\t%s/mod/dvdroot_ps4/chr/a.dcx\n", root);
    fprintf(list, "dvdroot_ps4/chr/New.dcx\t%s/mod/dvdroot_ps4/chr/New.dcx\n", root);
    fprintf(list, "dvdroot_ps4/Extra/deep/c.dcx\t%s/mod/dvdroot_ps4/Extra/deep/c.dcx\n", root);
    fclose(list);
    static char variable[900];
    snprintf(variable, sizeof(variable), "BB_APP0_LAYER=%s", path);
    putenv(variable);
    snprintf(game, sizeof(game), "%s/game", root);
    snprintf(user, sizeof(user), "%s/user", root);
    runtime_file_configure(game, user);
    assert(redirect_count == 3);

    /* A listed file, however the game spells or reaches it. */
    expect("/app0/dvdroot_ps4/chr/a.dcx", "mod/dvdroot_ps4/chr/a.dcx");
    expect("/app0/DVDROOT_PS4/Chr/A.DCX", "mod/dvdroot_ps4/chr/a.dcx");
    expect("/app0//dvdroot_ps4/./chr/a.dcx", "mod/dvdroot_ps4/chr/a.dcx");
    expect("/hostapp/dvdroot_ps4/chr/a.dcx", "mod/dvdroot_ps4/chr/a.dcx");
    expect("dvdroot_ps4/chr/new.dcx", "mod/dvdroot_ps4/chr/New.dcx");
    /* Everything else stays in the game folder. */
    expect("/app0/dvdroot_ps4/chr/b.dcx", "game/dvdroot_ps4/chr/b.dcx");
    expect("/app0/eboot.bin", "game/eboot.bin");
    expect("/app0/dvdroot_ps4/chr", "game/dvdroot_ps4/chr");
    /* Not found stays not found, under the game's own folder. */
    expect("/app0/dvdroot_ps4/chr/missing.dcx", "game/dvdroot_ps4/chr/missing.dcx");
    /* A folder only a mod has. */
    expect("/app0/dvdroot_ps4/extra", "mod/dvdroot_ps4/Extra");
    expect("/app0/dvdroot_ps4/extra/deep", "mod/dvdroot_ps4/Extra/deep");
    /* Saves and the other mounts never are. */
    char out[1024], want[800];
    assert(!runtime_file_translate("/temp0/dvdroot_ps4/chr/a.dcx", out, sizeof(out)));
    snprintf(want, sizeof(want), "%s/temp0/dvdroot_ps4/chr/a.dcx", user);
    assert(!strcmp(out, want));

    int type = 0;
    snprintf(path, sizeof(path), "%s/game/dvdroot_ps4/chr", root);
    Listing *l = list_game_directory(path, "/app0/dvdroot_ps4/chr");
    assert(l);
    assert(listed(l, "a.dcx", &type) == 1);
    assert(listed(l, "b.dcx", &type) == 1);
    assert(listed(l, "New.dcx", &type) == 1 && type == 8);
    free_listing(l);

    snprintf(path, sizeof(path), "%s/game/dvdroot_ps4", root);
    l = list_game_directory(path, "/app0/dvdroot_ps4");
    assert(l);
    assert(listed(l, "chr", &type) == 1 && type == 4);
    assert(listed(l, "Extra", &type) == 1 && type == 4);
    free_listing(l);

    snprintf(path, sizeof(path), "%s/game", root);
    l = list_game_directory(path, "/app0");
    assert(l);
    assert(listed(l, "dvdroot_ps4", &type) == 1);
    free_listing(l);

    /* A mod's folder keeps what no game folder has, once. */
    snprintf(path, sizeof(path), "%s/mod/dvdroot_ps4/Extra", root);
    l = list_game_directory(path, "/app0/dvdroot_ps4/extra");
    assert(l);
    assert(listed(l, "deep", &type) == 1 && type == 4);
    free_listing(l);

    puts("PASS: files over the game");
    return 0;
}
