# SNN foundation implementation plan

Execution: native, incremental, under the user's explicit authorization to
continue implementing without stopping for routine design approval.
Goal: native contiguous buffers and typed Izhikevich populations, with a
correctness-gated scale benchmark. Spec: ../../decisions/0002-snn-populations.md.
Stack: existing Python 3.10+, C11, Clang/GCC; no extra runtime dependency.

## Review focus

Zero/negative sizes; negative/out-of-range indices; nested scopes and early
returns; type/precision mismatches; exact threshold/reset order and vector tails.

## Tasks

- [ ] Buffers: extend lexer/parser, add typed IR buffer allocate/load/store;
  codegen owns/free storage at lexical boundaries and return. Add frontend and
  native tests (zero, bounds, wrong types, return cleanup), watch failures,
  implement, run full suite, document and commit.
- [ ] Population: explicit PopulationSpec/UniformParameter in IR and model
  kernel in myrk/neural.py; parser declaration and step, scalar state queries.
  Tests compare native steps to independent rounded f32/f64 Python reference,
  including tails and resets. Run suite and executable example, commit.
- [ ] Performance lab: benchmarks/neuron/izhikevich.py, independent C oracle,
  native monotonic kernel timing, all-state differential check before timing,
  bounded scale sweep, compiler/hardware/flags/raw samples, RSS and memory model.
  Compare strict variants, inspect assembly, record evidence, commit.
- [ ] Revise ROADMAP, PERFORMANCE, MILLION_NEURON_PLAN, README and CI. Publish
  exact commits to existing GitHub repository and verify remote CI.

Deferred: connected SNN, spike representations, multicore, NEON intrinsics,
procedural connectivity, delay/plasticity, autotuning. No speed claim from
comparison to Python, from lower precision, or from independent neurons alone.
