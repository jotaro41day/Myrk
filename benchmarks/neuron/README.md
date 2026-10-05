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

## Comparar o caminho anterior com batching / multicore

```sh
python3 -m benchmarks.neuron.izhikevich --sizes 1000000 --dtype f32 --threads 1 --summary --output izh-1.json
python3 -m benchmarks.neuron.izhikevich --sizes 1000000 --dtype f32 --threads 2 --summary --output izh-2.json
python3 -m benchmarks.neuron.izhikevich --sizes 1000000 --dtype f32 --threads 4 --summary --output izh-4.json
```

Agora `--schedule batch` é o default. O relatório contém Myrk batch, C batch
com **o mesmo pool e número de threads**, e `myrk_step` com o caminho anterior
single-thread. `speedup_vs_single_thread_step` mede paralelismo + scheduling;
não significa vantagem sobre C com os mesmos recursos. Para reproduzir o
schedule original use `--schedule step --threads 1`. Comparar primeiro 1/2/4,
não presumir que todos os cores vencem em big.LITTLE. Nenhuma afinidade é forçada.

Worker threads têm partições contíguas/disjuntas e avançam todos os passos
sem barreiras entre timesteps; isso só é válido porque não há comunicação ou
monitor intermediário neste workload. O estado não é comprimido em 97 grupos:
cada um dos N neurônios é atualizado exatamente steps vezes.

Há gate adicional de batch vs C sequencial, conferindo **todos os estados**,
total de spikes e contagem do último passo, inclusive prefixos 1/2/7/31/80.
O gate por timestep do kernel original continua ativo. Não alegar que o batch
produz um stream de spikes por timestep; ele só retorna total e último count.

`pool_startup_median_ms` inclui pthread_create e espera de prontidão dos
workers; fica fora do kernel. Uma nova população/processo é criada por amostra,
com pool pronto antes do timer. Process time inclui startup/join/hash/IO.
O runtime do compilador reutiliza o mesmo pool entre lotes; testes cobrem isso.
A ordem das três variantes gira a cada repetição. No schedule step, usa duas
variantes. Os arquivos JSON preservam amostras e comparações; --summary apenas
reduz a impressão no terminal, sem remover os gates de corretude.

## Ablação de cache blocks

`--tile 0` preserva a partição inteira; `--tile 2048` avança grupos menores por
todos os passos, sem criar threads/barreiras por timestep. Os dois dtypes e o
C de referência usam exatamente o mesmo tile. `myrk_step` continua sendo o
baseline original de uma thread, sem tile; o JSON informa as duas configurações.

```sh
for tile in 0 2048 16384; do
  python3 -m benchmarks.neuron.izhikevich --sizes 1000000 --dtype f32 \
    --threads 2 --tile "$tile" --summary --output "izh-tile-$tile.json"
done
```

Para programa compilado: `MYRK_THREADS=2 MYRK_TILE=2048 myrk run examples/izhikevich.myrk`.
Nenhum valor positivo é automaticamente escolhido. Tiles muito pequenos reduzem
vetorização e paralelismo dentro do núcleo; tiles grandes podem exceder cache.
Apenas comparação no mesmo hardware/threads/dtype pode justificar uma escolha.
O tráfego lógico L1 continua 16/32 bytes/update; tiling procura reduzir tráfego
entre níveis de cache/DRAM, sem afirmar que isso já foi medido por contadores.

## Modelos oficiais IF / LIF / QIF / AdEx / HH

```sh
python3 -m benchmarks.neuron.models --sizes 1000 10000 --summary --output models.json
python3 -m benchmarks.neuron.models --models HH --dtype f32 --sizes 100000 --steps 100 --summary
python3 -m benchmarks.neuron.models --models LIF IF QIF AdEx --dtype f32 --sizes 1000000 --artifacts benchmarks/results/models
```

This companion lab uses source-parsed native kernels for the other five official
models; Izhikevich retains the original lab and multicore measurements above.
All new models currently run one thread. It does not compare different models
as equivalent work. Parameters and solver appear in every result. HH uses
Euler voltage / Rush–Larsen gates, dt=.01 ms; the other fixtures use simultaneous
Euler, dt=.1 ms. Units/contracts: [NEURON_MODELS.md](../../docs/NEURON_MODELS.md).
No refractory periods, connectivity, delays or hidden monitors.

Each actual neuron has v_init+(i%17)*.125; HH gates are equilibrium at that
varied initial voltage, AdEx w=w_init. Every state is really updated; the
fixture is not collapsed to 17 trajectories. Before timing: Python checks 17
neurons ×80 steps (every field and exact per-step spike count); native independent
C checks initialization and all states/counts at **every requested timestep
and scale**. State tolerance vs Python libm is .003 in f32 /1e-9 in f64; C at
same precision requires exact equality. Every timed sample must match full-state
hash, sums, total and final count. Failed gates abort without a report; a mutation
test proves the HH voltage gate rejects a wrong integrator.

Native CLOCK_MONOTONIC measures updates/counts, excludes allocate/init/hash/IO;
process_ms includes the whole sample. Myrk/C process ordering alternates.
Default: both precisions, 200 steps, 5 samples, 2 warmups. Memory payload is
N*number_of_states*dtype_width; --max-mib bounds **two-population validation
payload**, not total RSS. Native VmHWM reports the measured process separately.
HH initialization of the Myrk population first uses the production uniform
initializer, then applies fixture variation; that extra work is outside timing.
The C reference computes varied initial gates directly. There is no pool cost
or hidden thread configuration in these single-thread kernels.

State bytes/neuron f32: IF/LIF/QIF4, AdEx8, HH16 (double these for f64).
Logical loads/stores per update are twice these sizes, before possible uniform
reloads/spills; this is not measured DRAM bandwidth. libm exp/expm1 are linked
with -lm, available with ordinary Clang/GCC on Linux/Android. No approximations
or fast-math. Both production and independent C AdEx/HH check finite states
inside their update loops, with the same failure contract. These are correct
starting baselines, not tuned competitive HH kernels.
`--artifacts` retains generated source/binary/assembly for inspection; keep it
under ignored benchmarks/results. Android execution of new models is pending.
