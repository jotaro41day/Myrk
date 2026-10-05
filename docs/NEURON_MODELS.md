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
```

New-model timestep loops remain sequential; MYRK_THREADS/MYRK_TILE currently
optimize only eligible Izhikevich loops. Solvers and models need individual
optimization/equivalence evidence. These are neuron-update models; connected
networks, delays and plasticity are separate pending features. Linux tests do
not establish Android execution or scientific validity at arbitrary dt.

AdEx and HH are the next increment under ADR 0004, not yet available here.
