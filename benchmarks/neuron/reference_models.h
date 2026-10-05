/* Independent scalar/auto-vectorizable C oracle. Never calls compiler kernels.
 * Same SoA payload, parameters, precision and discrete solver; no FMA. */
#if MODEL == 4
static REAL reference_ratio(REAL x) { return x==R(0.0) ? R(1.0) : x/(-EXPM1(-x)); }
static void reference_rates(REAL voltage,REAL *am,REAL *bm,REAL *ah,REAL *bh,REAL *an,REAL *bn) {
    *am=reference_ratio((voltage+R(40.0))/R(10.0));
    *bm=R(4.0)*EXP(-((voltage+R(65.0))/R(18.0)));
    *ah=R(0.07)*EXP(-((voltage+R(65.0))/R(20.0)));
    *bh=R(1.0)/(R(1.0)+EXP(-((voltage+R(35.0))/R(10.0))));
    *an=R(0.1)*reference_ratio((voltage+R(55.0))/R(10.0));
    *bn=R(0.125)*EXP(-((voltage+R(65.0))/R(80.0)));
}
static REAL reference_gate(REAL q,REAL alpha,REAL beta,REAL dt) {
    REAL sum=alpha+beta, target=alpha/sum;
    REAL decay=EXP(-(dt*sum));
    return target+(q-target)*decay;
}
#endif
static void reference_initialize(POPULATION *p) {
    for (int32_t j=0;j<p->size;++j) {
        REAL v=p->v_init+(REAL)(j%17)*R(0.125);
        p->v[j]=v;
#if MODEL == 3
        p->w[j]=p->w_init;
#elif MODEL == 4
        REAL am,bm,ah,bh,an,bn;
        reference_rates(v,&am,&bm,&ah,&bh,&an,&bn);
        p->m[j]=am/(am+bm);p->h[j]=ah/(ah+bh);p->n[j]=an/(an+bn);
#endif
    }
}
static int32_t reference_step(POPULATION *p) {
    const POPULATION q=*p;
    REAL * restrict voltage=p->v;
#if MODEL == 3
    REAL * restrict adaptation=p->w;
#elif MODEL == 4
    REAL * restrict m=p->m,* restrict h=p->h,* restrict n=p->n;
#endif
    int32_t count=0;
    for(int32_t j=0;j<q.size;++j) {
        REAL old=voltage[j];
#if MODEL == 0
        REAL next=old+q.dt*(q.current/q.capacitance);
#elif MODEL == 1
        REAL drive=-q.g_leak*(old-q.v_rest)+q.current;
        REAL next=old+q.dt*(drive/q.capacitance);
#elif MODEL == 2
        REAL drive=(q.k*(old-q.v_rest))*(old-q.v_critical)+q.current;
        REAL next=old+q.dt*(drive/q.capacitance);
#elif MODEL == 3
        REAL w=adaptation[j];
        REAL exponential=(q.g_leak*q.delta_t)*EXP((old-q.v_t)/q.delta_t);
        REAL drive=((-q.g_leak*(old-q.v_rest)+exponential)-w)+q.current;
        REAL next=old+q.dt*(drive/q.capacitance);
        REAL next_w=w+q.dt*((q.a*(old-q.v_rest)-w)/q.tau_w);
#elif MODEL == 4
        REAL om=m[j],oh=h[j],on=n[j];
        REAL sodium=((((q.g_na*om)*om)*om)*oh)*(old-q.e_na);
        REAL potassium=((((q.g_k*on)*on)*on)*on)*(old-q.e_k);
        REAL leak=q.g_leak*(old-q.e_leak);
        REAL next=old+q.dt*(((q.current-sodium)-potassium-leak)/q.capacitance);
        REAL am,bm,ah,bh,an,bn;
        reference_rates(old,&am,&bm,&ah,&bh,&an,&bn);
        m[j]=reference_gate(om,am,bm,q.dt);
        h[j]=reference_gate(oh,ah,bh,q.dt);
        n[j]=reference_gate(on,an,bn,q.dt);
#endif
#if MODEL == 4
        int fired=old<q.v_threshold && next>=q.v_threshold;
        voltage[j]=next;
#else
        int fired=next>=q.v_threshold;
        voltage[j]=fired ? q.v_reset : next;
#if MODEL == 3
        adaptation[j]=fired ? next_w+q.b : next_w;
#endif
#endif
#if MODEL == 3
        if(!isfinite(voltage[j]) || !isfinite(adaptation[j])) {
            fputs("Myrk runtime error: nonfinite AdEx state; check parameters and dt\n",stderr);exit(70);
        }
#elif MODEL == 4
        if(!isfinite(next) || !isfinite(m[j]) || !isfinite(h[j]) || !isfinite(n[j])) {
            fputs("Myrk runtime error: nonfinite HH state; check parameters and dt\n",stderr);exit(70);
        }
#endif
        count+=fired;
    }
    return count;
}
