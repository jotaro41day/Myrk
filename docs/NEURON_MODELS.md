# Official neuron models

Native population models use explicit named uniform parameters and contiguous
owned SoA state. Precision is f32 or f64. A model name is case-insensitive;
canonical spelling is retained in typed IR. No per-neuron objects/parameter
arrays, hidden recording, allocation per timestep or global fast-math.

The initial IF/LIF/QIF examples use capacitance in pF, current in pA, voltage
in mV, time in ms and conductance in nS. QIF k is nS/mV. Parameters are all
required; examples choose illustrative values, not implicit defaults.

| Model | Parameters (besides i32 size) | State | Solver |
| --- | --- | --- | --- |
| IF | dt, current, capacitance, v_init, v_reset, v_threshold | v | Euler (constant-current subthreshold integration is exact in real arithmetic) |
| LIF | dt, current, capacitance, g_leak, v_rest, v_init, v_reset, v_threshold | v | Euler |
| QIF | dt, current, capacitance, k, v_rest, v_critical, v_init, v_reset, v_threshold | v | Euler |
| Izhikevich | a, b, c, d, dt, current | v, u | simultaneous Euler (unchanged) |
| AdEx | dt, current, capacitance, g_leak, v_rest, v_t, delta_t, tau_w, a, b, v_init, w_init, v_reset, v_threshold | v, w | simultaneous Euler |
| HH | dt, current, capacitance, g_na, g_k, g_leak, e_na, e_k, e_leak, v_init, v_threshold | v, m, h, n | Euler voltage + Rush–Larsen gates |

IF is perfect integrate-and-fire: v_next = v + dt*(current/capacitance).
LIF: v_next = v + dt*((-g_leak*(v-v_rest)+current)/capacitance).
QIF: v_next = v + dt*(((k*(v-v_rest))*(v-v_critical)+current)/capacitance).
After integration, v_next >= v_threshold emits one spike and sets v=v_reset.
No refractory period or interpolation of spike time is implied. Initial v=v_init.
Spikes(p) counts the last step; voltage(p,i) checks indices for all models.
Recovery(p,i) is only valid for Izhikevich. Builtins use lowercase spelling.

All parameters must be finite literals of the chosen precision; dt and
capacitance must remain positive after target rounding. LIF g_leak and QIF k
are also positive. Other values may be any finite literal; a reset at/above
threshold can cause repetitive firing and is not silently changed.

```sh
myrk run examples/if.myrk
myrk run examples/lif.myrk
myrk run examples/qif.myrk
myrk run examples/izhikevich.myrk
myrk run examples/adex.myrk
myrk run examples/hh.myrk
```

New-model timestep loops remain sequential; MYRK_THREADS/MYRK_TILE currently
optimize only eligible Izhikevich loops. Solvers and models need individual
optimization/equivalence evidence. These are neuron-update models; connected
networks, delays and plasticity are separate pending features. Linux tests do
not establish Android execution or scientific validity at arbitrary dt.

## AdEx

Adaptive exponential integrate-and-fire uses pF/nS/pA/mV/ms as above; a is nS,
b and w are pA. At each step both derivatives use OLD v/w:

```
drive = ((-g_leak*(v-v_rest) + (g_leak*delta_t)*exp((v-v_t)/delta_t))-w)+current
v_next = v + dt*(drive/capacitance)
w_next = w + dt*((a*(v-v_rest)-w)/tau_w)
```

Then v_next >= v_threshold fires, resets v=v_reset and sets w=w_next+b.
Otherwise v=v_next, w=w_next. Initialization is v_init/w_init; adaptation(p,i)
reads w with a checked index. dt/capacitance/g_leak/delta_t/tau_w are positive,
a/b nonnegative. Exponentials use target expf/exp, without clipping or fast
approximations. A nonfinite stored state fails with runtime code70. A voltage
overflow that crosses threshold and resets to a finite value is still a spike.

## HH — Hodgkin–Huxley

Classic squid-axon rates at 6.3 C, with absolute mV, ms, capacitance in uF/cm²,
conductances in mS/cm² and current in uA/cm². No temperature scaling or point
neuron pF conversion is automatic. At OLD v/m/h/n:

```
I_Na = ((((g_na*m)*m)*m)*h)*(v-e_na)
I_K  = ((((g_k*n)*n)*n)*n)*(v-e_k)
I_L  = g_leak*(v-e_leak)
v_next = v + dt*(((current-I_Na)-I_K-I_L)/capacitance)
```

Rates (per ms):

```
alpha_m = ratio((v+40)/10)       beta_m = 4*exp(-(v+65)/18)
alpha_h = .07*exp(-(v+65)/20)    beta_h = 1/(1+exp(-(v+35)/10))
alpha_n = .1*ratio((v+55)/10)    beta_n = .125*exp(-(v+65)/80)
ratio(x) = x / (-expm1(-x)); ratio(0) = 1
```

For each gate q: rate=alpha+beta, q_inf=alpha/rate,
q_next=q_inf+(q-q_inf)*exp(-(dt*rate)). Rates are frozen at OLD voltage;
the voltage step uses OLD gates. Rush–Larsen is exact for that frozen linear
gate equation, not for the entire nonlinear HH system. Initial gates equal
q_inf(v_init), computed once for the uniform population. gate_m(p,i), gate_h
and gate_n expose checked state queries. dt/capacitance are positive;
conductances are nonnegative. Nonfinite initial gates/stored state fail code70.

A spike is **old_v < v_threshold and v_next >= v_threshold**. HH has no reset
or added adaptation. The example uses dt=.01 ms, not the .1 ms of the point
models. Solver convergence/scientific accuracy still need problem-specific
assessment; a large positive dt is not a guarantee of stability. Library exp/
expm1 can differ by an ULP between targets even in strict mode.
