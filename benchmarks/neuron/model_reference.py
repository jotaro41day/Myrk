"""Independent scalar model oracle and explicit benchmark parameter fixtures.

Not imported by the compiler. Each elementary operation is rounded for f32.
"""
from .reference import rounding

DEFAULTS = {
    'IF': dict(dt=0.1,current=500.0,capacitance=200.0,v_init=-65.0,v_reset=-65.0,v_threshold=-50.0),
    'LIF': dict(dt=0.1,current=500.0,capacitance=200.0,g_leak=10.0,v_rest=-65.0,
                v_init=-65.0,v_reset=-65.0,v_threshold=-50.0),
    'QIF': dict(dt=0.1,current=500.0,capacitance=200.0,k=0.7,v_rest=-60.0,v_critical=-40.0,
                v_init=-65.0,v_reset=-65.0,v_threshold=30.0),
}


def initialize_basic(model, parameters, dtype='f64'):
    r=rounding(dtype)
    return (r(parameters['v_init']),)


def step_basic(model, state, parameters, dtype='f64'):
    r=rounding(dtype);p={k:r(v) for k,v in parameters.items()};v=state[0]
    if model=='IF':
        drive=p['current']
    elif model=='LIF':
        drive=r(r(-p['g_leak']*r(v-p['v_rest']))+p['current'])
    elif model=='QIF':
        drive=r(r(r(p['k']*r(v-p['v_rest']))*r(v-p['v_critical']))+p['current'])
    else:
        raise ValueError(model)
    next_v=r(v+r(p['dt']*r(drive/p['capacitance'])))
    fired=next_v>=p['v_threshold']
    return (p['v_reset'] if fired else next_v,),int(fired)


def declaration(model, dtype='f64', n=9, **overrides):
    parameters={**DEFAULTS[model],**overrides}
    args=', '.join(f'{name}={value}{dtype}' for name,value in parameters.items())
    return f'population p: {model}<{dtype}>(size={n}, {args});'

# Point AdEx: pF/nS/pA/mV/ms. HH: uF/cm², mS/cm², uA/cm², mV, ms.
DEFAULTS.update({
    'AdEx': dict(dt=0.1,current=500.0,capacitance=200.0,g_leak=10.0,v_rest=-70.0,
                 v_t=-50.0,delta_t=2.0,tau_w=100.0,a=2.0,b=40.0,
                 v_init=-70.0,w_init=0.0,v_reset=-58.0,v_threshold=20.0),
    'HH': dict(dt=0.01,current=10.0,capacitance=1.0,g_na=120.0,g_k=36.0,g_leak=0.3,
               e_na=50.0,e_k=-77.0,e_leak=-54.387,v_init=-65.0,v_threshold=0.0),
})



def hh_rates(v,dtype='f64'):
    import math
    r=rounding(dtype)
    def ratio(x):
        return r(1.0) if x==0 else r(x/r(-r(math.expm1(r(-x)))))
    am=ratio(r(r(v+r(40.0))/r(10.0)))
    bm=r(r(4.0)*r(math.exp(r(-r(r(v+r(65.0))/r(18.0))))))
    ah=r(r(0.07)*r(math.exp(r(-r(r(v+r(65.0))/r(20.0))))))
    bh=r(r(1.0)/r(r(1.0)+r(math.exp(r(-r(r(v+r(35.0))/r(10.0)))))))
    an=r(r(0.1)*ratio(r(r(v+r(55.0))/r(10.0))))
    bn=r(r(0.125)*r(math.exp(r(-r(r(v+r(65.0))/r(80.0))))))
    return am,bm,ah,bh,an,bn


def initialize(model, parameters, dtype='f64'):
    r=rounding(dtype);v=r(parameters['v_init'])
    if model=='AdEx':return v,r(parameters['w_init'])
    if model=='HH':
        am,bm,ah,bh,an,bn=hh_rates(v,dtype)
        return v,r(am/r(am+bm)),r(ah/r(ah+bh)),r(an/r(an+bn))
    return initialize_basic(model,parameters,dtype)


def step(model, state, parameters, dtype='f64'):
    import math
    if model not in ('AdEx','HH'):return step_basic(model,state,parameters,dtype)
    r=rounding(dtype);p={k:r(v) for k,v in parameters.items()};v=state[0]
    if model=='AdEx':
        w=state[1]
        exponential=r(math.exp(r(r(v-p['v_t'])/p['delta_t'])))
        drive=r(r(r(r(-p['g_leak']*r(v-p['v_rest']))+
                       r(r(p['g_leak']*p['delta_t'])*exponential))-w)+p['current'])
        nv=r(v+r(p['dt']*r(drive/p['capacitance'])))
        nw=r(w+r(p['dt']*r(r(r(p['a']*r(v-p['v_rest']))-w)/p['tau_w'])))
        fired=nv>=p['v_threshold']
        return (p['v_reset'] if fired else nv,r(nw+p['b']) if fired else nw),int(fired)
    m,h,n=state[1:]
    ina=r(r(r(r(p['g_na']*m)*m)*m)*h);ina=r(ina*r(v-p['e_na']))
    ik=r(r(r(r(p['g_k']*n)*n)*n)*n);ik=r(ik*r(v-p['e_k']))
    leak=r(p['g_leak']*r(v-p['e_leak']))
    nv=r(v+r(p['dt']*r(r(r(r(p['current']-ina)-ik)-leak)/p['capacitance'])))
    rates=hh_rates(v,dtype)
    gates=[]
    for gate,alpha,beta in zip((m,h,n),rates[::2],rates[1::2]):
        rate=r(alpha+beta);equilibrium=r(alpha/rate)
        decay=r(math.exp(r(-r(p['dt']*rate))))
        gates.append(r(equilibrium+r(r(gate-equilibrium)*decay)))
    return (nv,*gates),int(v<p['v_threshold'] and nv>=p['v_threshold'])
