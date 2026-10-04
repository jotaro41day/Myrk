# Contributing to Myrk

Myrk is experimental. Open an issue before making a large syntax or IR change.
Keep changes small, with a correctness test and a runnable example when behavior
changes. Performance work also needs a reference implementation, an equivalence
check, before/after measurements, hardware details, and an entry in
`docs/PERFORMANCE.md`.

Local checks:

```sh
python3 -m unittest discover -s tests -v
python3 benchmarks/run.py
```

Use clear commits such as `feat(parser): support typed parameters`. Never remove
a failing test just to make an optimization pass. See `docs/decisions/` for major
architecture choices.
