/* Standalone kernel measurement; initialization, validation, hashing and IO
 * are outside the measured region. Template tokens replaced by harness. */
#define _POSIX_C_SOURCE 200809L
#include <math.h>
#include <string.h>
#include <time.h>
#include <inttypes.h>
#include <errno.h>
#define main myrk_example_main
#include "@GENERATED@"
#undef main
#define REAL @REAL@
#define R(x) @LITERAL@
#define MYRK_STEP myrk_izh_@DTYPE@_step
#include "@REFERENCE@"

static const REAL A=R(0.02), B=R(0.2), C=R(-65.0), D=R(8.0), DT=R(0.5), INPUT=R(10.0);

static void initialize(int32_t n, REAL *v, REAL *u) {
    for (int32_t i=0; i<n; ++i) {
        /* Exact binary variation, including SIMD tails; never collapse to one neuron. */
        v[i] = R(-70.0) + (REAL)(i % 97) * R(0.125);
        u[i] = B * v[i];
    }
}
static int32_t update(int reference, int32_t n, REAL *v, REAL *u) {
    return reference ? reference_step(n,v,u,A,B,C,D,DT,INPUT)
                     : MYRK_STEP(n,v,u,A,B,C,D,DT,INPUT);
}
static double now(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts)) { perror("clock_gettime"); exit(1); }
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}
static long peak_rss_kib(void) {
    /* Read this native process, avoiding Python parent's inherited wait4 high water. */
    FILE *f = fopen("/proc/self/status", "r");
    if (!f) return -1;
    char line[256]; long value = -1;
    while (fgets(line,sizeof line,f)) {
        if (sscanf(line,"VmHWM: %ld kB",&value)==1) break;
    }
    fclose(f); return value;
}
static uint64_t hash_state(int32_t n, const REAL *v, const REAL *u) {
    uint64_t h=UINT64_C(14695981039346656037);
    const unsigned char *buffers[2]={(const unsigned char *)v,(const unsigned char *)u};
    for (int k=0;k<2;++k)
        for (size_t i=0;i<(size_t)n*sizeof(REAL);++i)
            h=(h^buffers[k][i])*UINT64_C(1099511628211);
    return h;
}
static int32_t positive(const char *s) {
    char *end; errno=0; long n=strtol(s,&end,10);
    if (errno || !*s || *end || n<1 || n>INT32_MAX) exit(2);
    return (int32_t)n;
}
int main(int argc, char **argv) {
    if (argc!=5) return 2;
    const int validate = strcmp(argv[1],"validate")==0;
    const int trace = strcmp(argv[1],"trace")==0;
    if (!validate && !trace && strcmp(argv[1],"run")) return 2;
    if (strcmp(argv[2],"myrk") && strcmp(argv[2],"c")) return 2;
    const int reference = strcmp(argv[2],"c")==0;
    const int32_t n=positive(argv[3]), steps=positive(argv[4]);
    REAL *v=myrk_alloc(n,sizeof(REAL)), *u=myrk_alloc(n,sizeof(REAL));
    initialize(n,v,u);
    REAL *vr=NULL,*ur=NULL;
    if (validate) {
        vr=myrk_alloc(n,sizeof(REAL)); ur=myrk_alloc(n,sizeof(REAL)); initialize(n,vr,ur);
    }
    uint64_t spikes=0;
    const double start=now();
    for (int32_t t=0;t<steps;++t) {
        const int32_t fired=update(reference,n,v,u);
        spikes+=(uint64_t)fired;
        if (validate) {
            if (reference_step(n,vr,ur,A,B,C,D,DT,INPUT)!=fired) {
                fprintf(stderr,"spike mismatch at step %d\n",t); return 1;
            }
            for (int32_t i=0;i<n;++i) {
                if (!isfinite(v[i]) || !isfinite(u[i]) || v[i]!=vr[i] || u[i]!=ur[i]) {
                    fprintf(stderr,"state mismatch at step %d neuron %d\n",t,i); return 1;
                }
            }
        }
        if (trace) {
            printf("%d",fired);
            for (int32_t i=0;i<n;++i) printf(" %.17g %.17g",(double)v[i],(double)u[i]);
            putchar('\n');
        }
    }
    const double seconds=now()-start;
    if (!trace) {
        double sum_v=0,sum_u=0;
        for (int32_t i=0;i<n;++i) {
            if (!isfinite(v[i]) || !isfinite(u[i])) { fputs("nonfinite state\n",stderr); return 1; }
            sum_v+=(double)v[i]; sum_u+=(double)u[i];
        }
        printf("{\"seconds\":%.17g,\"spikes\":%" PRIu64 ",\"sum_v\":%.17g,\"sum_u\":%.17g,"
               "\"state_hash\":\"%016" PRIx64 "\",\"peak_rss_kib\":%ld,"
               "\"max_abs_error\":0,\"passed\":true}\n",
               seconds,spikes,sum_v,sum_u,hash_state(n,v,u),peak_rss_kib());
    }
    free(vr);free(ur);free(v);free(u);
    return 0;
}
