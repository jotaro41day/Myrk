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


def initialize(model, parameters, dtype='f64'):
    r=rounding(dtype)
    return (r(parameters['v_init']),)


def step(model, state, parameters, dtype='f64'):
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
