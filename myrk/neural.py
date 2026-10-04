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
