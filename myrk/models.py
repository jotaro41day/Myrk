"""Static neural semantics: state layout, uniform parameters and solver identity."""
from dataclasses import dataclass


@dataclass(frozen=True)
class NeuronModel:
    parameters: tuple[str,...]
    states: tuple[str,...]
    positive: tuple[str,...]
    nonnegative: tuple[str,...] = ()
    solver: str = 'euler_simultaneous'


MODELS = {
    'Izhikevich': NeuronModel(('a','b','c','d','dt','current'),('v','u'),('dt',)),
    'IF': NeuronModel(('dt','current','capacitance','v_init','v_reset','v_threshold'),('v',),('dt','capacitance')),
    'LIF': NeuronModel(('dt','current','capacitance','g_leak','v_rest','v_init','v_reset','v_threshold'),
                       ('v',),('dt','capacitance','g_leak')),
    'QIF': NeuronModel(('dt','current','capacitance','k','v_rest','v_critical','v_init','v_reset','v_threshold'),
                       ('v',),('dt','capacitance','k')),
    'AdEx': NeuronModel(('dt','current','capacitance','g_leak','v_rest','v_t','delta_t',
                        'tau_w','a','b','v_init','w_init','v_reset','v_threshold'),
                       ('v','w'),('dt','capacitance','g_leak','delta_t','tau_w'),('a','b')),
    'HH': NeuronModel(('dt','current','capacitance','g_na','g_k','g_leak',
                      'e_na','e_k','e_leak','v_init','v_threshold'),
                     ('v','m','h','n'),('dt','capacitance'),('g_na','g_k','g_leak'),
                     'euler_voltage_rush_larsen_gates'),
}

STATE_QUERIES = {'voltage':'v','recovery':'u','adaptation':'w','gate_m':'m','gate_h':'h','gate_n':'n'}
QUERY_MODELS = {'recovery':'Izhikevich','adaptation':'AdEx','gate_m':'HH','gate_h':'HH','gate_n':'HH'}


def canonical_model(name):
    return next((model for model in MODELS if model.casefold()==name.casefold()),None)


def prefix(model,dtype):
    return f'myrk_{"izh" if model=="Izhikevich" else model.lower()}_{dtype}'


def population_type(model,dtype):
    return f'myrk_population_{dtype}' if model=='Izhikevich' else f'myrk_{model.lower()}_population_{dtype}'
