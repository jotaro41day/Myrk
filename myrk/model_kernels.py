"""Native kernels for the additional official models; Izhikevich is unchanged."""
import re
from .models import MODELS, population_type, prefix


def hh_helpers(name,real,exp,expm1):
    return f'''static {real} {name}_ratio({real} x) {{
    return x==0.0 ? 1.0 : x / (-{expm1}(-x));
}}
static void {name}_rates({real} v, {real} *am, {real} *bm, {real} *ah,
                         {real} *bh, {real} *an, {real} *bn) {{
    *am={name}_ratio((v+40.0)/10.0);
    *bm=4.0*{exp}(-((v+65.0)/18.0));
    *ah=0.07*{exp}(-((v+65.0)/20.0));
    *bh=1.0/(1.0+{exp}(-((v+35.0)/10.0)));
    *an=0.1*{name}_ratio((v+55.0)/10.0);
    *bn=0.125*{exp}(-((v+65.0)/80.0));
}}
static {real} {name}_gate({real} old, {real} alpha, {real} beta, {real} dt) {{
    const {real} rate=alpha+beta;
    const {real} equilibrium=alpha/rate;
    return equilibrium+(old-equilibrium)*{exp}(-(dt*rate));
}}
'''


def kernel(model,dtype):
    definition=MODELS[model]
    real='float' if dtype=='f32' else 'double'
    exp='expf' if dtype=='f32' else 'exp'
    expm1='expm1f' if dtype=='f32' else 'expm1'
    name=prefix(model,dtype);ctype=population_type(model,dtype)
    params='\n'.join(f'    {real} {field};' for field in definition.parameters)
    states='\n'.join(f'    {real} *{field};' for field in definition.states)
    uniform='\n'.join(f'    const {real} {field}=p->{field};' for field in definition.parameters)
    pointers='\n'.join(f'    {real} * restrict {field}=p->{field};' for field in definition.states)
    helpers='';init_prelude='';init='p->v[i]=p->v_init;'
    if model in ('IF','LIF','QIF'):
        drive={'IF':'current','LIF':'(-g_leak * (old_v - v_rest) + current)',
               'QIF':'((k * (old_v - v_rest)) * (old_v - v_critical) + current)'}[model]
        update=f'''const {real} next_v=old_v + dt * ({drive} / capacitance);
        const int fired=next_v >= v_threshold;
        v[i]=fired ? v_reset : next_v;'''
    elif model=='AdEx':
        init+=' p->w[i]=p->w_init;'
        update=f'''const {real} old_w=w[i];
        const {real} drive=((-g_leak*(old_v-v_rest)
            +(g_leak*delta_t)*{exp}((old_v-v_t)/delta_t))-old_w)+current;
        const {real} next_v=old_v+dt*(drive/capacitance);
        const {real} next_w=old_w+dt*((a*(old_v-v_rest)-old_w)/tau_w);
        const int fired=next_v>=v_threshold;
        v[i]=fired ? v_reset : next_v;
        w[i]=fired ? next_w+b : next_w;
        if (!isfinite(v[i]) || !isfinite(w[i])) {{
            fputs("Myrk runtime error: nonfinite AdEx state; check parameters and dt\\n",stderr); exit(70);
        }}'''
    elif model=='HH':
        helpers=hh_helpers(name,real,exp,expm1)
        init_prelude=f'''{real} am,bm,ah,bh,an,bn;
    {name}_rates(p->v_init,&am,&bm,&ah,&bh,&an,&bn);
    const {real} m0=am/(am+bm),h0=ah/(ah+bh),n0=an/(an+bn);
    if (!isfinite(m0) || !isfinite(h0) || !isfinite(n0)) {{
        fputs("Myrk runtime error: nonfinite HH initial gates; check v_init\\n",stderr); exit(70);
    }}'''
        init+=' p->m[i]=m0; p->h[i]=h0; p->n[i]=n0;'
        update=f'''const {real} old_m=m[i],old_h=h[i],old_n=n[i];
        const {real} ina=((((g_na*old_m)*old_m)*old_m)*old_h)*(old_v-e_na);
        const {real} ik=((((g_k*old_n)*old_n)*old_n)*old_n)*(old_v-e_k);
        const {real} leak=g_leak*(old_v-e_leak);
        const {real} next_v=old_v+dt*(((current-ina)-ik-leak)/capacitance);
        {real} am,bm,ah,bh,an,bn;
        {name}_rates(old_v,&am,&bm,&ah,&bh,&an,&bn);
        m[i]={name}_gate(old_m,am,bm,dt);
        h[i]={name}_gate(old_h,ah,bh,dt);
        n[i]={name}_gate(old_n,an,bn,dt);
        v[i]=next_v;
        const int fired=old_v<v_threshold && next_v>=v_threshold;
        if (!isfinite(next_v) || !isfinite(m[i]) || !isfinite(h[i]) || !isfinite(n[i])) {{
            fputs("Myrk runtime error: nonfinite HH state; check parameters and dt\\n",stderr); exit(70);
        }}'''
    else:
        raise ValueError(model)
    result=f'''typedef struct {{
    int32_t size,spikes;
{states}
{params}
}} {ctype};
{helpers}
static void {name}_initialize({ctype} *p) {{
    if (!p->size) return;
    {init_prelude}
    for (int32_t i=0;i<p->size;++i) {{ {init} }}
}}
static int32_t {name}_step({ctype} *p) {{
{uniform}
{pointers}
    int32_t spikes=0;
    for(int32_t i=0;i<p->size;++i) {{
        const {real} old_v=v[i];
        {update}
        spikes+=fired;
    }}
    return spikes;
}}
'''
    if dtype=='f32':
        result=re.sub(r'(?<![\w.])(\d+\.\d+)(?![\w.])',r'\1f',result)
    return result
