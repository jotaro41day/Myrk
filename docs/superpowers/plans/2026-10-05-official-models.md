# Official neuron models implementation plan

Goal: native typed IF/LIF/Izhikevich/QIF/AdEx/HH populations with documented
numerical contracts, tests, runnable examples and fair CPU benchmarks.
Architecture: static model catalog + existing semantic IR/C backend; preserve
Izhikevich code and restrict its batch optimization explicitly by model.
Tech: Python stdlib, C11, Clang/GCC, libm, pthread; Termux compatible.
Spec: docs/decisions/0004-official-neuron-models.md.
User has authorized autonomous implementation and frequent publication.

- [x] Write failing IF/LIF/QIF type/native/reference tests.
- [x] Add catalog, model-aware symbols/steps, generic owned states and kernels.
- [x] Verify full suite, add examples/contracts, commit and publish basic models.
- [x] Write failing AdEx/HH query/rate/trajectory tests.
- [x] Add exponential adaptation, stable HH rates and Rush–Larsen gates.
- [x] Verify full suite, add examples/contracts, commit and publish AdEx/HH.
- [x] Add independent C reference and correctness-gated model-update benchmark.
- [x] Validate all models/dtypes, update README/roadmap/CI/development state.
- [x] Run GCC/Clang checks and review; publish final verified increment.
