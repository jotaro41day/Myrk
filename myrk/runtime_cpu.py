"""Small persistent pthread executor for proven-independent population batches."""

PTHREAD_RUNTIME = r'''
#include <pthread.h>
#include <errno.h>
#define MYRK_MAX_THREADS 64
static struct {
    pthread_mutex_t mutex;
    pthread_cond_t work, complete;
    pthread_t threads[MYRK_MAX_THREADS - 1];
    int ids[MYRK_MAX_THREADS - 1];
    int width, ready, done, stop;
    uint64_t generation;
    void (*job)(int, int, void *);
    void *context;
} myrk_cpu = {
    .mutex = PTHREAD_MUTEX_INITIALIZER,
    .work = PTHREAD_COND_INITIALIZER,
    .complete = PTHREAD_COND_INITIALIZER
};
static void myrk_cpu_check(int error) {
    if (error) {
        fprintf(stderr,"Myrk runtime error: pthread operation failed (%d)\n",error);
        _Exit(70);
    }
}
/* Read once on the control thread; workers receive an immutable job field. */
static int32_t myrk_cpu_tile(void) {
    static int initialized=0;
    static int32_t tile=0;
    if (!initialized) {
        const char *setting=getenv("MYRK_TILE");
        if (setting) {
            char *end; errno=0;
            long value=strtol(setting,&end,10);
            if (errno || !*setting || *end || value<0 || value>INT32_MAX) {
                fputs("Myrk runtime error: MYRK_TILE must be an integer in [0,2147483647]\n",stderr);
                exit(70);
            }
            tile=(int32_t)value;
        }
        initialized=1;
    }
    return tile;
}
static void *myrk_cpu_worker(void *arg) {
    const int id = *(int *)arg;
    uint64_t seen = 0;
    myrk_cpu_check(pthread_mutex_lock(&myrk_cpu.mutex));
    ++myrk_cpu.ready;
    if (myrk_cpu.ready == myrk_cpu.width - 1)
        myrk_cpu_check(pthread_cond_signal(&myrk_cpu.complete));
    for (;;) {
        while (!myrk_cpu.stop && seen == myrk_cpu.generation)
            myrk_cpu_check(pthread_cond_wait(&myrk_cpu.work, &myrk_cpu.mutex));
        if (myrk_cpu.stop) break;
        seen = myrk_cpu.generation;
        void (*job)(int,int,void *) = myrk_cpu.job;
        void *context = myrk_cpu.context;
        myrk_cpu_check(pthread_mutex_unlock(&myrk_cpu.mutex));
        job(id, myrk_cpu.width, context);
        myrk_cpu_check(pthread_mutex_lock(&myrk_cpu.mutex));
        ++myrk_cpu.done;
        if (myrk_cpu.done == myrk_cpu.width - 1)
            myrk_cpu_check(pthread_cond_signal(&myrk_cpu.complete));
    }
    myrk_cpu_check(pthread_mutex_unlock(&myrk_cpu.mutex));
    return NULL;
}
static void myrk_cpu_shutdown(void) {
    myrk_cpu_check(pthread_mutex_lock(&myrk_cpu.mutex));
    myrk_cpu.stop = 1;
    myrk_cpu_check(pthread_cond_broadcast(&myrk_cpu.work));
    myrk_cpu_check(pthread_mutex_unlock(&myrk_cpu.mutex));
    for (int i=0; i<myrk_cpu.width-1; ++i)
        myrk_cpu_check(pthread_join(myrk_cpu.threads[i], NULL));
    myrk_cpu_check(pthread_cond_destroy(&myrk_cpu.work));
    myrk_cpu_check(pthread_cond_destroy(&myrk_cpu.complete));
    myrk_cpu_check(pthread_mutex_destroy(&myrk_cpu.mutex));
}
static int myrk_cpu_threads(void) {
    if (myrk_cpu.width) return myrk_cpu.width;
    const char *setting = getenv("MYRK_THREADS");
    long width = 1;
    if (setting) {
        char *end; errno=0;
        width = strtol(setting, &end, 10);
        if (errno || !*setting || *end || width<1 || width>MYRK_MAX_THREADS) {
            fputs("Myrk runtime error: MYRK_THREADS must be an integer in [1,64]\n",stderr);
            exit(70);
        }
    }
    myrk_cpu.width = (int)width;
    if (width > 1) {
        for (int i=0; i<width-1; ++i) {
            myrk_cpu.ids[i] = i+1;
            myrk_cpu_check(pthread_create(&myrk_cpu.threads[i], NULL,
                                         myrk_cpu_worker, &myrk_cpu.ids[i]));
        }
        myrk_cpu_check(pthread_mutex_lock(&myrk_cpu.mutex));
        while (myrk_cpu.ready != width-1)
            myrk_cpu_check(pthread_cond_wait(&myrk_cpu.complete,&myrk_cpu.mutex));
        myrk_cpu_check(pthread_mutex_unlock(&myrk_cpu.mutex));
        if (atexit(myrk_cpu_shutdown)) {
            fputs("Myrk runtime error: cannot register pool shutdown\n",stderr);
            _Exit(70);
        }
    }
    return myrk_cpu.width;
}
/* Submit is called only by the language's control thread; jobs never nest. */
static void myrk_parallel(void (*job)(int,int,void *), void *context) {
    const int width = myrk_cpu_threads();
    if (width == 1) { job(0,1,context); return; }
    myrk_cpu_check(pthread_mutex_lock(&myrk_cpu.mutex));
    myrk_cpu.job=job; myrk_cpu.context=context; myrk_cpu.done=0;
    ++myrk_cpu.generation;
    myrk_cpu_check(pthread_cond_broadcast(&myrk_cpu.work));
    myrk_cpu_check(pthread_mutex_unlock(&myrk_cpu.mutex));
    job(0,width,context);
    myrk_cpu_check(pthread_mutex_lock(&myrk_cpu.mutex));
    while (myrk_cpu.done != width-1)
        myrk_cpu_check(pthread_cond_wait(&myrk_cpu.complete,&myrk_cpu.mutex));
    myrk_cpu_check(pthread_mutex_unlock(&myrk_cpu.mutex));
}
'''
