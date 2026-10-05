# ADR 0004 — Official CPU neuron models

## Context

The user requires official LIF, IF, Izhikevich, QIF, AdEx and HH support.
They are source/semantic-IR concepts with native CPU kernels, not Python-only
library names. Preserve the existing Izhikevich solver, ABI, benchmarks and
independent batch proof. Termux/AArch64 and strict f32/f64 remain first-class.

## Options

A universal runtime model switch would obscure specialization. Separate full
compiler paths would duplicate ownership/types. Instead, a small static model
catalog describes uniform parameters, SoA states, queries and solver identity;
semantic analysis selects the model and codegen emits only needed kernels.

## Decision

Canonical names: IF, LIF, Izhikevich, QIF, AdEx, HH. Case-insensitive model
names; no misspelling aliases. IF is perfect integrate-and-fire. IF/LIF/QIF
use one v buffer; AdEx uses v/w; Izhikevich keeps v/u; HH uses v/m/h/n.
All parameters are required named finite literals of the selected precision.
Size remains an i32 expression. Positive denominators/time constants are
validated in target precision. States are local, owned, nonescaping SoA arrays.

IF: dv/dt=I/C. LIF: dv/dt=(-gL*(v-EL)+I)/C.
QIF: dv/dt=(k*(v-v_rest)*(v-v_critical)+I)/C.
AdEx: dv/dt=(-gL*(v-EL)+gL*deltaT*exp((v-VT)/deltaT)-w+I)/C;
dw/dt=(a*(v-EL)-w)/tau_w. These use simultaneous Euler and threshold/reset
after integration, one spike maximum per timestep. AdEx resets v and adds b to
updated w. No refractory period or clipped exponential is silently added.
Izhikevich is unchanged (simultaneous Euler, v=c/u+=d after threshold).

HH uses classic squid-axon absolute-mV rates at 6.3 C (no temperature scaling),
Euler voltage using OLD gates and Rush–Larsen gates with rates frozen at OLD v.
Initial gates are equilibrium values at v_init, calculated once per population.
Stable expm1 formulas handle alpha_m(-40) and alpha_n(-55) exactly. HH spikes
are upward crossings old_v < threshold <= new_v, without voltage reset.
Queries expose voltage for all models, recovery for Izhikevich, adaptation for
AdEx and gate_m/gate_h/gate_n for HH; incompatible queries are type errors.

New models initially execute ordinary timestep loops. The existing batch pass
is explicitly restricted to Izhikevich until other model/solver dependencies
are independently proven. This avoids inheriting a proof by accident.
Use libm exp/expf/expm1/expm1f; no approximation, FMA or fast-math default.

## Consequences / verification

One to four contiguous state buffers, scalar uniform parameters, no objects or
allocations inside step. This supplies correct baselines, not optimized-HH or
scientific validation claims. Transcendentals are target libm and may differ by
an ULP across toolchains. Differential tests compare every exposed state/count;
closed-form subthreshold checks and HH rate singularities supplement oracles.
Add independent C baselines, correctness-gated timings and executable examples.
Connected networks, refractory periods, temperature scaling, alternative solvers
and new-model multicore remain explicit future work. Android execution is
pending even if Linux tests and AArch64 cross compilation pass.
