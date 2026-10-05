# ADR 0005 — General language foundation without erasing neural semantics

## Context

Myrk must support ordinary programs as well as SNN kernels. The existing typed
IR, native backend, buffers and population operations remain the foundation.
General control flow must not bypass ownership cleanup or make neural batching
unsafe. Adding every general-purpose subsystem at once would make these
contracts difficult to verify.

## Options

1. Replace the frontend with a large general-purpose framework.
2. Add general constructs incrementally to the existing AST and typed IR.
3. Desugar everything to strings of C before semantic analysis.

## Decision

Choose option 2. First add nested block comments, scientific literals and local
type inference from the initializer's exact checked type. Function interfaces
stay explicit. Add bool-only if/else and while, short-circuit logical operators,
loop exits and all-path return checking. IR retains structured branches/loops
alongside PopulationSpec; batching remains conservative and model-specific.

Next add compound assignments, explicit checked numeric casts, statement calls
and unit-returning functions. A missing function result annotation means unit;
main still requires `-> i32`. No numeric promotion is implicit. Float-to-i32
casts truncate toward zero and reject nonfinite or unrepresentable results.
Narrowing f64 to f32 rejects finite overflow; IEEE infinities/NaNs are preserved.

Buffer/population cleanup occurs on every exit from an owning scope, including
return, break and continue. Logical RHS effects happen only when required.
Existing source programs and strict floating-point flags remain valid.

Modules, strings, structs/enums, collection ownership, other integer widths,
standard library, FFI and package tooling require separate tested milestones.
These are roadmap items, not features advertised as implemented.

## Consequences

The C backend stays small and usable with Python/Clang in Termux. Structured
control flow remains available for later optimization. Local inference removes
repeated annotations without heuristic inference or hidden conversions.
Checked casts and resource exits require native regression tests; LLVM/C
optimization must not move observable work across a short-circuit boundary.

## Evidence

Existing compiler, ownership and six-model differential suites provide a
regression baseline. New tests must cover RHS traps/effects, nested loop exits,
scope visibility, branch returns, cast limits, model discovery inside branches
and conservative batching. Linux GCC/Clang evidence does not imply Android
execution; platform validation remains explicit.
