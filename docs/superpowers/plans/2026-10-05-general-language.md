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

- [ ] Add failing tests for branches, while, nested break/continue, bool-only
  conditions, all-path returns, scope cleanup and lazy &&/||.
- [ ] Implement structured IR and C lowering, loop scope cleanup and recursive
  neural discovery/optimization.
- [ ] Run regressions and native sanitizers; document and publish.

### Task 3: Functions and numeric ergonomics

Files: parser.py, semantics.py, codegen_c.py, tests, examples, docs, CI.

- [ ] Add failing tests for unit functions, ignored call results, compound scalar
  assignments, numeric casts with boundary/nonfinite errors and evaluation order.
- [ ] Implement exact-type operations, checked casts and unit-returning calls.
- [ ] Add executable ordinary-program examples and CI coverage.
- [ ] Verify both compilers, examples, SNN benchmark correctness and publish.

### Task 4: Development continuity

- [ ] Update language specification, README, changelog, roadmap and saved state.
- [ ] Record remaining general-language milestones as GitHub issues.
- [ ] Review final diff, verify remote SHA and CI, report only proven features.
