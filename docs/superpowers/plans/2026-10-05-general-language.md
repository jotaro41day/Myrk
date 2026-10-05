# General Language Foundation Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, task by task.

**Goal:** Make ordinary numerical Myrk programs practical without changing SNN contracts.

**Architecture:** Extend the current AST and typed IR with structured control
flow. Keep the C11 AOT backend, exact scalar types and scoped buffer ownership.
Population metadata and strict numeric kernels remain intact.

**Tech Stack:** Python 3.10+ standard library, C11, Clang/GCC, unittest.

**Spec:** [ADR 0005](../../decisions/0005-general-language-foundation.md).

## Global Constraints

- Same repository and architecture; preserve existing programs.
- Termux/AArch64 first-class; no new mandatory dependency or root requirement.
- No implicit numeric conversions or fast-math.
- Commit and publish each verified increment.

## Review Focus

- Short-circuit RHS must not execute effects or runtime traps unnecessarily.
- Loop exits free inner allocations and preserve outer allocations.
- Neural declarations in nested control flow still generate their kernels.
- Return analysis rejects scalar paths without a result.
- Cast limits and signed zero/nonfinite values avoid C undefined behavior.

### Task 1: Literal syntax and safe local inference

Files: lexer.py, parser.py, semantics.py, tests/test_language.py, LANGUAGE.md.

- [x] Add and run failing tests for nested comments, locations, exponent forms,
  malformed exponents and inferred exact local types.
- [x] Implement lexical changes and optional local annotation.
- [x] Run focused tests and complete regression suite; document and publish.

### Task 2: Structured control flow

Files: parser.py, semantics.py, codegen_c.py, optimize.py, test_language.py.

- [x] Add failing tests for branches, while, nested break/continue, bool-only
  conditions, all-path returns, scope cleanup and lazy &&/||.
- [x] Implement structured IR and C lowering, loop scope cleanup and recursive
  neural discovery/optimization.
- [x] Run regressions and native sanitizers; document and publish.

### Task 3: Functions and numeric ergonomics

Files: parser.py, semantics.py, codegen_c.py, tests, examples, docs, CI.

- [x] Add failing tests for unit functions, ignored call results, compound scalar
  assignments, numeric casts with boundary/nonfinite errors and evaluation order.
- [x] Implement exact-type operations, checked casts and unit-returning calls.
- [x] Add executable ordinary-program examples and CI coverage.
- [x] Verify both compilers, examples, SNN benchmark correctness and publish.

### Task 4: Development continuity

- [x] Update language specification, README, changelog, roadmap and saved state.
- [x] Record remaining general-language milestones as GitHub issues #8–#12 / #2.
- [x] Review final diff; code commits published with exact verified SHAs.
  CI 37354518564 passed on 438c67c; final continuity commit is documentation only.

## Evidence and rulings

- Task 1: 7 new tests first failed, then 81 full-suite tests passed; published d9bb29e.
- Task 2: 11 new tests first failed, then 92 full-suite tests passed. Six native
  tests passed ASan/UBSan/LSan; examples fibonacci=55, control_flow=16; d97adb3.
- Task 3: 14 new tests first failed; final 110 tests pass with GCC14.2/Clang19.
  Nine native cast/function tests passed address/UB checks; success paths also
  pass leak checking. Fatal bounds termination has no resource unwinding, so
  only that exit(70) test disables LSan (address/UB checks remain active).
- Ruling: extend scalar buffers to i32/bool and expose len now — existing
  contiguous ownership/runtime is sufficient; no dynamic collection semantics.
- Ruling: preserve old control-keyword identifiers where syntax is unambiguous
  — review found a compatibility regression; new regression tests prove it.
- Ruling: reject extreme decimal overflow before Fraction construction and
  normalize definite underflow — avoids compiler exhaustion from tiny input.
- Ruling: reserve numeric cast names and len only, document the 0.x break;
  bool/unit remain legal function names because neither is callable builtin.
- Focused independent review found the three cases above; fixes were verified.
- Installed examples outside checkout and README native snippets passed. SNN
  benchmark smokes checked all states/spikes against references; no speed claim.
