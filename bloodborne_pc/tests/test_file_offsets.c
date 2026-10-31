/* Issue #6: a thread reading with lseek + read and another reading the same descriptor with pread.
 * On FreeBSD pread leaves the offset alone; Windows' emulation must too, or the first thread
 * reads from the wrong place (map pieces and their collision loaded from garbage). */
#include "../src/runtime_file.c"
#include <assert.h>
#include <time.h>
static int32_t guest_errno;
int32_t *runtime_errno(void) { return &guest_errno; }
int32_t runtime_guest_errno(int e) { return e; }
uintptr_t runtime_lookup(const RuntimeExport *table,size_t n,const char *name) {
    for (size_t i=0;i<n;++i) if (!strcmp(table[i].name,name)) return (uintptr_t)table[i].function;
    return 0;
}
#define WORDS (1u<<20) /* 4 MiB: word i holds i */
#define CHUNK 1024     /* words per read */
static int fd;
static volatile int stop;
static unsigned bad_seek, bad_pread;
static unsigned next(unsigned *s) { *s=*s*1103515245u+12345u; return (*s>>8)%(WORDS-CHUNK); }
static int check(const uint32_t *b,unsigned at) {
    for (unsigned i=0;i<CHUNK;++i) if (b[i]!=at+i) return 0;
    return 1;
}
static void *seek_reader(void *arg) {
    unsigned s=(unsigned)(uintptr_t)arg; uint32_t b[CHUNK];
    while (!stop) {
        unsigned at=next(&s);
        assert(do_lseek(fd,(int64_t)at*4,0)==(int64_t)at*4);
        if (do_read(fd,b,sizeof(b))!=(int64_t)sizeof(b) || !check(b,at)) ++bad_seek;
    }
    return NULL;
}
static void *pread_reader(void *arg) {
    unsigned s=(unsigned)(uintptr_t)arg; uint32_t b[CHUNK];
    while (!stop) {
        unsigned at=next(&s);
        if (do_pread(fd,b,sizeof(b),(int64_t)at*4)!=(int64_t)sizeof(b) || !check(b,at)) __atomic_add_fetch(&bad_pread,1,__ATOMIC_RELAXED);
    }
    return NULL;
}
int main(void) {
    char root[64];
    snprintf(root,sizeof(root),"bbport-offsets-%u",(unsigned)time(NULL));
    char game[128],user[128],data[160];
    snprintf(game,sizeof(game),"%s/game",root); snprintf(user,sizeof(user),"%s/user",root);
    snprintf(data,sizeof(data),"%s/data.bin",game);
    mkdir(root,0755); mkdir(game,0755);
    FILE *f=fopen(data,"wb"); assert(f);
    for (uint32_t i=0;i<WORDS;++i) assert(fwrite(&i,4,1,f)==1);
    assert(!fclose(f));
    runtime_file_configure(game,user);
    fd=(int)do_open("/app0/data.bin",0,0); assert(fd>=3);
    pthread_t a,b,c;
    pthread_create(&a,NULL,seek_reader,(void *)1);
    pthread_create(&b,NULL,pread_reader,(void *)2);
    pthread_create(&c,NULL,pread_reader,(void *)3);
    struct timespec wait={2,0}; nanosleep(&wait,NULL);
    stop=1;
    pthread_join(a,NULL); pthread_join(b,NULL); pthread_join(c,NULL);
    assert(!do_close(fd));
    printf("lseek+read wrong data: %u, pread wrong data: %u\n",bad_seek,bad_pread);
    remove(data); rmdir(game);
    rmdir(user); /* left with its temp0/download0/data subdirectories if it cannot be removed */
    assert(!bad_seek && !bad_pread);
    puts("file offset test passed");
    return 0;
}
