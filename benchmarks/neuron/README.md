# Izhikevich neuron-update lab

Execute from the checkout (Python 3.10+, Clang or GCC):

```sh
python3 -m benchmarks.neuron.izhikevich --sizes 1000 10000 100000 1000000
python3 -m benchmarks.neuron.izhikevich --all-scales --dtype f32 --max-mib 256
python3 -m benchmarks.neuron.izhikevich --sizes 1000000 --opt O3 --artifacts benchmarks/results/izh-o3
```

Defaults: both f32/f64, 200 timesteps, dt=0.5 ms, 2 process warmups and 5
samples, single thread. `--all-scales`: 1K, 10K, 100K, 1M, 2M, 5M, 10M.
`--max-mib` limits **array payload during validation**, not RSS or all system
memory. Validation holds two populations (16N bytes f32 / 32N f64). A measured
run holds one (8N / 16N). Leave room for the OS and other apps; no root needed.

## Numerical contract and fairness

See [ADR 0002](../../docs/decisions/0002-snn-populations.md). Euler simultaneous,
not two half steps. Constant a=.02,b=.2,c=-65,d=8,dt=.5,current=10. Initial
v[i]=-70+(i%97)*.125 and u[i]=b*v[i] introduce varied trajectories and SIMD
tails. Every state element is updated every timestep; no grouping, sampling,
lazy update or extrapolation. The compiler generates the population kernel
from real parsed Myrk source. The C driver calls that emitted kernel with
heterogeneous initial state; setting such state is not yet source-language API.
This isolates kernel execution from frontend, allocation, initialization,
checksum and I/O. Full-program startup is in the existing scalar harness;
`process_median_ms` here includes all work of the benchmark process.

The native C reference is independent code, with exactly the same arithmetic,
precision, parameters, initialization, flags and thread count. It is allowed
to vectorize. It is a baseline, not a claim of competitiveness with all SNN
simulators. Python is only an oracle, never a timing competitor.

Before any timings are reported:

1. Compare every neuron state and every timestep count against Python for 17
   varied neurons × 80 steps, rounding each f32 primitive operation.
2. At **each requested scale**, compare all v/u elements and spike counts with
   independent C after **every requested timestep**, rejecting nonfinite values.
3. Every timed run must reproduce validation spike count, final sums and full
   state hash. A failing gate exits nonzero without a performance JSON report.

Order alternates Myrk/C between repetitions. Native CLOCK_MONOTONIC measures
only updates and spike counting, including timestep loop/control. One native
process per sample; time does not include allocation or checksums. State hash
is FNV-1a over both raw state buffers, meaningful within the same target/dtype.
RSS is native `/proc/self/status` VmHWM where available, not Python's inherited
`wait4` high-water reading. It includes executable/runtime/allocator pages.

`frontend_ms` measures parse/typecheck/codegen in the already-running Python
process; `native_compile_ms` measures the C driver build. Neither is a full
CLI cold compilation metric. Compiler version, flags, native binary size,
samples and hardware metadata accompany results. `realtime_factor` is
(steps × dt seconds)/kernel seconds; >1 is faster than biological real time
**for independent neuron updates only**. No synapse or propagation work exists.

The Python f32/f64 sensitivity report records max trajectory deviations and
spike neuron/timestep mismatches (up to 200 steps). Same-dtype correctness is
separate from scientific accuracy and solver convergence; zero error against
a discrete oracle does not establish continuous-model accuracy.

## Memory / arithmetic model

Two loads plus two stores: **16 B/update f32**, **32 B/update f64** at the
state-array interface. State working set: 8N / 16N bytes. Uniform parameters
are registers/scalars, not per-neuron arrays. No spike mask or monitor array.
Approximately 14 floating operations before reset, plus one recovery addition
when fired (or for every lane in a vector select), comparison, selection and
integer spike reduction. Intensity about 0.875–0.938 FLOP/B f32, 0.438–0.469 f64.

`effective_state_gb_s` is this model divided by runtime, **not measured DRAM
bandwidth**. Cache residency, write allocation, spills, prefetch and branch
execution change physical traffic. At realtime with dt=.5 ms, 1M f32 neurons
require about 32 GB/s of modeled state traffic; 10M require 320 GB/s. Cache
reuse may help smaller populations; phone feasibility needs actual measurements.
Do not label a kernel bandwidth-bound without hardware/counter or streaming
baseline evidence. No per-step allocations or hidden recording.

## Assembly

`--artifacts DIR` retains generated C, driver, reference, binary and native
assembly for review. Recompile that driver with target-specific diagnostics:

```sh
# Termux/Clang, preserves strict numerics:
clang -std=c11 -O3 -fwrapv -fno-fast-math -ffp-contract=off \
  -Rpass=loop-vectorize -Rpass-missed=loop-vectorize \
  -S benchmarks/results/izh-o3/bench-f32.c -o benchmarks/results/izh-o3/arm.s
```

Look inside the **update loop**, not initialization/checksum: AArch64 `fmul`,
`fadd`, `fsub` on `.4s` or `.2d`, compare/select masks, vector loads/stores,
then scalar tails. Scalar `fmul sN` alone is not NEON vectorization. Record
vectorization misses, spills and branch behavior before choosing intrinsics.
No global fast-math. Android thermal state/big.LITTLE placement are manual
metadata for now; repeated sessions and sustained workloads are still needed.
