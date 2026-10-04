# Changelog

## 0.1.0 (experimental, unreleased)

- Initial lexer, parser, semantic checker, typed IR, C backend and native CLI.
- Scalar `i32`, `f32`, `f64`, `bool`, functions, variables and range loops.
- Source installation script, comparable scalar C baseline and LIF C/Python
  reference workload.

## Unreleased

- Buffers locais contíguos f32/f64, índices verificados e liberação por escopo.
- Prioridade SNN/Izhikevich documentada no ADR 0002.
- Populações Izhikevich f32/f64 na IR e no backend CPU; referência arredondada por operação.
- Laboratório Izhikevich com gate C/Python, escala 1K–10M, memória, tempo nativo e artefatos de assembly.
- Roadmap SNN e MILLION_NEURON_PLAN com medições x86 e validação Android pendente.
- Correção de duplo arredondamento em parâmetros f32.
