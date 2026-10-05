"""C lowering for the explicit Izhikevich population operations in typed IR."""


def kernel(dtype):
    ctype = {'f32': 'float', 'f64': 'double'}[dtype]
    suffix = 'f' if dtype == 'f32' else ''
    def lit(value):
        return value + suffix
    return f'''
typedef struct {{
    int32_t size, spikes;
    {ctype} *v, *u;
    {ctype} a, b, c, d, dt, current;
}} myrk_population_{dtype};

static int32_t myrk_izh_{dtype}_step(int32_t n,
    {ctype} * restrict v, {ctype} * restrict u,
    {ctype} a, {ctype} b, {ctype} c, {ctype} d, {ctype} dt, {ctype} current) {{
    int32_t spikes = 0;
    for (int32_t i = 0; i < n; ++i) {{
        const {ctype} old_v = v[i], old_u = u[i];
        const {ctype} next_v = old_v + dt *
            (((({lit('0.04')} * old_v) * old_v + {lit('5.0')} * old_v)
                + {lit('140.0')} - old_u) + current);
        const {ctype} next_u = old_u + dt * (a * (b * old_v - old_u));
        const int fired = next_v >= {lit('30.0')};
        v[i] = fired ? c : next_v;
        u[i] = fired ? next_u + d : next_u;
        spikes += fired;
    }}
    return spikes;
}}
'''


def batch_kernel(dtype):
    return f'''typedef struct {{
    myrk_population_{dtype} *p;
    uint32_t steps;
    int32_t tile;
    uint64_t totals[MYRK_MAX_THREADS];
    int32_t last[MYRK_MAX_THREADS];
}} myrk_batch_{dtype};
static void myrk_izh_{dtype}_partition(int id, int width, void *context) {{
    myrk_batch_{dtype} *batch = context;
    const myrk_population_{dtype} state = *batch->p;
    const myrk_population_{dtype} *p = &state;
    int32_t begin = (int32_t)((int64_t)p->size * id / width);
    int32_t end = (int32_t)((int64_t)p->size * (id+1) / width);
    uint64_t total = 0;
    int32_t last = 0;
    for (int32_t base=begin; base<end;) {{
        int32_t count=end-base;
        if (batch->tile && batch->tile<count) count=batch->tile;
        int32_t chunk_last=0;
        for (uint32_t t = 0; t < batch->steps; ++t) {{
            chunk_last = myrk_izh_{dtype}_step(count, p->v+base, p->u+base,
                p->a, p->b, p->c, p->d, p->dt, p->current);
            total += (uint64_t)chunk_last;
        }}
        last += chunk_last;
        base += count;
    }}
    batch->totals[id] = total;
    batch->last[id] = last;
}}
static uint64_t myrk_izh_{dtype}_advance(myrk_population_{dtype} *p, uint32_t steps) {{
    if (!steps) return 0;
    if (!p->size) {{ p->spikes=0; return 0; }}
    const int32_t tile=myrk_cpu_tile();
    if (myrk_cpu_threads() == 1 && !tile) {{
        uint64_t total=0;
        for (uint32_t t=0; t<steps; ++t) {{
            p->spikes=myrk_izh_{dtype}_step(p->size,p->v,p->u,
                p->a,p->b,p->c,p->d,p->dt,p->current);
            total+=(uint64_t)p->spikes;
        }}
        return total;
    }}
    myrk_batch_{dtype} batch = {{.p=p, .steps=steps, .tile=tile}};
    myrk_parallel(myrk_izh_{dtype}_partition, &batch);
    uint64_t total=0;
    p->spikes=0;
    for (int i=0; i<myrk_cpu_threads(); ++i) {{
        total += batch.totals[i];
        p->spikes += batch.last[i];
    }}
    return total;
}}
'''
