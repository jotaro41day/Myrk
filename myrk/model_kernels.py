"""Native kernels for the additional official models; Izhikevich is unchanged."""
from .models import MODELS, population_type, prefix


def kernel(model,dtype):
    definition=MODELS[model]
    real='float' if dtype=='f32' else 'double'
    name=prefix(model,dtype);ctype=population_type(model,dtype)
    params='\n'.join(f'    {real} {p};' for p in definition.parameters)
    states='\n'.join(f'    {real} *{s};' for s in definition.states)
    uniform='\n'.join(f'    const {real} {p}=p->{p};' for p in definition.parameters)
    pointers='\n'.join(f'    {real} * restrict {s}=p->{s};' for s in definition.states)
    if model=='IF':
        drive='current'
    elif model=='LIF':
        drive='(-g_leak * (old_v - v_rest) + current)'
    elif model=='QIF':
        drive='((k * (old_v - v_rest)) * (old_v - v_critical) + current)'
    else:
        raise ValueError(model)
    return f'''typedef struct {{
    int32_t size,spikes;
{states}
{params}
}} {ctype};
static void {name}_initialize({ctype} *p) {{
    for (int32_t i=0;i<p->size;++i) p->v[i]=p->v_init;
}}
static int32_t {name}_step({ctype} *p) {{
{uniform}
{pointers}
    int32_t spikes=0;
    for(int32_t i=0;i<p->size;++i) {{
        const {real} old_v=v[i];
        const {real} next_v=old_v + dt * ({drive} / capacitance);
        const int fired=next_v >= v_threshold;
        v[i]=fired ? v_reset : next_v;
        spikes+=fired;
    }}
    return spikes;
}}
'''
