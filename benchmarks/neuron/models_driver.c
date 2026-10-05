#define _POSIX_C_SOURCE 200809L
#include <math.h>
#include <string.h>
#include <time.h>
#include <inttypes.h>
#define main myrk_unused_main
#include "@GENERATED@"
#undef main
#define REAL @REAL@
#define R(x) @LITERAL@
#define EXP @EXP@
#define EXPM1 @EXPM1@
#define MODEL @MODEL@
#define POPULATION @POPULATION@
#define NSTATES @NSTATES@
#include "reference_models.h"

static double now(void) {
    struct timespec ts;
    if(clock_gettime(CLOCK_MONOTONIC,&ts)) {perror("clock_gettime");exit(1);}
    return (double)ts.tv_sec+(double)ts.tv_nsec*1e-9;
}
static long rss(void) {
    FILE *file=fopen("/proc/self/status","r");if(!file)return -1;
    char line[256];long value=-1;
    while(fgets(line,sizeof line,file)) if(sscanf(line,"VmHWM: %ld kB",&value)==1)break;
    fclose(file);return value;
}
static int32_t positive(char *s) {
    char *end;errno=0;long n=strtol(s,&end,10);
    if(errno || !*s || *end || n<1 || n>INT32_MAX)exit(2);
    return (int32_t)n;
}
static POPULATION create(int32_t n,int reference) {
    POPULATION p={0};p.size=n;
    @PARAMETERS@
    @ALLOCATIONS@
    if(reference)reference_initialize(&p);
    else {
        @PREFIX@_initialize(&p);
        for(int32_t i=0;i<n;++i) {
            p.v[i]=p.v_init+(REAL)(i%17)*R(0.125);
            @HETEROGENEOUS_GATES@
        }
    }
    return p;
}
static void buffers(POPULATION *p,REAL **out) { @BUFFERS@ }
static void release(POPULATION *p) { @FREES@ }
static void equal(POPULATION *a,POPULATION *b,int32_t timestep) {
    REAL *left[NSTATES],*right[NSTATES];buffers(a,left);buffers(b,right);
    for(int field=0;field<NSTATES;++field)for(int32_t i=0;i<a->size;++i) {
        if(!isfinite(left[field][i]) || !isfinite(right[field][i]) || left[field][i]!=right[field][i]) {
            fprintf(stderr,"state mismatch step %d neuron %d field %d\n",timestep,i,field);exit(1);
        }
    }
}
int main(int argc,char **argv) {
    if(argc!=5)return 2;
    int validate=!strcmp(argv[1],"validate"),trace=!strcmp(argv[1],"trace");
    if(!validate && !trace && strcmp(argv[1],"run"))return 2;
    int reference=!strcmp(argv[2],"c");
    if(!reference && strcmp(argv[2],"myrk"))return 2;
    int32_t n=positive(argv[3]),steps=positive(argv[4]);
    POPULATION p=create(n,reference),oracle={0};
    if(validate) {oracle=create(n,1);equal(&p,&oracle,-1);}
    uint64_t spikes=0;int32_t last=0;
    double started=now();
    for(int32_t t=0;t<steps;++t) {
        last=reference ? reference_step(&p) : @PREFIX@_step(&p);
        spikes+=(uint64_t)last;
        if(validate) {
            if(last!=reference_step(&oracle)){fprintf(stderr,"spike mismatch step %d\n",t);return 1;}
            equal(&p,&oracle,t);
        }
        if(trace) {
            REAL *arrays[NSTATES];buffers(&p,arrays);printf("%d",last);
            for(int32_t i=0;i<n;++i)for(int field=0;field<NSTATES;++field)printf(" %.17g",(double)arrays[field][i]);
            putchar('\n');
        }
    }
    double seconds=now()-started;
    if(!trace) {
        REAL *arrays[NSTATES];buffers(&p,arrays);
        uint64_t hash=UINT64_C(14695981039346656037);double sums[NSTATES]={0};
        for(int field=0;field<NSTATES;++field) {
            for(int32_t i=0;i<n;++i) {
                if(!isfinite(arrays[field][i])){fputs("nonfinite benchmark state\n",stderr);return 1;}
                sums[field]+=(double)arrays[field][i];
            }
            const unsigned char *bytes=(const unsigned char *)arrays[field];
            for(size_t i=0;i<(size_t)n*sizeof(REAL);++i)hash=(hash^bytes[i])*UINT64_C(1099511628211);
        }
        printf("{\"seconds\":%.17g,\"spikes\":%" PRIu64 ",\"last_spikes\":%d,"
               "\"state_hash\":\"%016" PRIx64 "\",\"peak_rss_kib\":%ld,\"sums\":[",
               seconds,spikes,last,hash,rss());
        for(int field=0;field<NSTATES;++field)printf("%s%.17g",field ? "," : "",sums[field]);
        puts("],\"passed\":true,\"max_abs_error\":0}");
    }
    if(validate)release(&oracle);release(&p);return 0;
}
