# Roadmap SNN — prioridades revisadas em 2026-10-05

Meta de engenharia: perseguir a toolchain SNN mais rápida possível, com foco
inicial em Android/Termux/AArch64. Não é uma afirmação de liderança medida.
A fundação existente é preservada. Tensores gerais/GPU não bloqueiam SNN.

Versão 0.x experimental. Gates: código funcional + testes + exemplo + docs +
benchmark aplicável + commit. Otimização: baseline → hipótese → implementação
→ equivalência → benchmark → assembly/perfil → decisão. Ganho condicionado
a workload/target deve permanecer condicionado, sem fast-math implícita.

| Etapa | Entrega e critério | Estado |
| --- | --- | --- |
| M0/M1 | Pesquisa, ADR, frontend/IR tipada, C11 nativo, benchmarks iniciais | Base existente; 17 testes e benchmarks relatados no Termux |
| M2 | Buffers locais contíguos f32/f64, limites e ownership por escopo | Implementado/testado Linux; Android novo código pendente; empréstimos entre funções futuros |
| M3 | Modelos oficiais/Population/UniformParameter na IR, solvers explícitos, oráculos C/Python | IF/LIF/Izhikevich/QIF/AdEx/HH f32/f64 implementados/testados Linux; seis exemplos; Android pendente |
| M4 | Lab 1K→10M, memória, throughput, timestep, realtime, estados e precisão | Sweep CPU x86 realizado; tabela no MILLION_NEURON_PLAN; Termux pendente |
| M5 | Layout SoA/AoSoA, especialização e NEON/SIMD | SoA baseline; NEON no cross compile; cache blocking temporal explícito medido em x86, sem valor automático. Ablação Termux pendente |
| M6 | SpikeSet: máscara, bitset, compactação | Medir atividade/custo de conversão; equivalência e throughput de compactação |
| M7 | Pool persistente, partições contíguas, redução ao final | Implementado para batches independentes; ~1,98× f32 com 2 threads no Xeon. Android/big.LITTLE e redes conectadas pendentes |
| M8 | Sinapses reais: CSR, índices menores, propagação | Eventos/s, bytes/sinapse, oracle de conectividade; comparar formatos/ordens e conectividade procedural |
| M9 | Delays limitados, ring/buckets; rede conectada | Spike trace e delays corretos; 1M/fanout 10→100→1000 conforme orçamento |
| M10 | Estratégias por população/projeção, híbrido/event/time | Crossover medido e semântica preservada; Izhikevich não pode pular passos por ausência de spikes |
| M11 | Plasticidade, outros solvers/monitores e extensões de modelos | Seis modelos básicos já implementados no M3. Precisão equivalente, refractory/temperatura e monitoramento explícitos seguem pendentes |
| M12+ | Autotuning cacheado, tensores/BLAS/autodiff, GPU | Somente após kernels e workloads sólidos; nenhum requisito CUDA |

A IR preservará progressivamente modelo, solver, clock, precisão, uniformidade,
layout, projeção, conectividade, delays e monitores. Não se criam camadas vazias.
Compiler metadata deve eliminar arrays de parâmetros repetidos, alocações por
passo e recording não solicitado; novas eliminações de trabalho exigem prova.

## Linguagem geral

A linguagem também deve permitir programas completos fora de SNN. Esta frente
evolui sobre o compilador existente, preservando a prioridade de kernels SNN.
Não representa uma reescrita ou a promessa de que todos os recursos já existem.

| Etapa | Entrega | Estado / gate |
| --- | --- | --- |
| G0 | Inferência local, comentários de bloco, expoentes, if/else/while, break/continue, lógica curta, funções unit, casts, atribuições compostas, buffers escalares e len | Implementado; testes nativos/ownership/diagnósticos; Android pendente |
| G1 | Módulos/imports com resolução determinística e strings UTF-8 imutáveis; impressão textual | Futuro; [#8](https://github.com/jotaro41day/Myrk/issues/8) módulos, [#9](https://github.com/jotaro41day/Myrk/issues/9) strings |
| G2 | Structs/enums, construtores, acesso a campos, match, aliases de tipo | Futuro; [#10](https://github.com/jotaro41day/Myrk/issues/10), layout/valor/ABI explícitos, exhaustividade e diagnósticos |
| G3 | i8/i16/i64/u8/u16/u32/u64 e operadores bitwise | Futuro; [#11](https://github.com/jotaro41day/Myrk/issues/11), wrap, shifts, casts, limites e ABI testados |
| G4 | Views/borrowing de buffers entre funções, arrays estáticos, slices, coleções dinâmicas | Futuro; [#2](https://github.com/jotaro41day/Myrk/issues/2), lifetime/aliasing/limites sem GC no hot path |
| G5 | Biblioteca padrão: matemática, RNG reproduzível, arquivos, argumentos CLI, erros/resultados e tempo | Futuro; [#12](https://github.com/jotaro41day/Myrk/issues/12), efeitos/custos explícitos e operações Termux |
| G6 | FFI C, módulos compilados, formatter, myrk test/bench, tooling e pacotes | Futuro; [#12](https://github.com/jotaro41day/Myrk/issues/12), builds reproduzíveis, símbolos/ABI e instalação |

Toda etapa precisa de programas executáveis, testes, documentação e benchmark
quando alterar runtime ou layout. Recursos genéricos não apagam PopulationSpec,
UniformParameter, solver ou precisão antes do lowering. [ADR 0005](decisions/0005-general-language-foundation.md).

Termux precisa de execução real por etapa. Cross compilation/CI x86 não garantem
Android. As medições do usuário em modelo 25078PC3EG, Python 3.14.6 e Clang
21.1.8 continuam válidas para a versão testada; não abrangem automaticamente
os buffers e populações acrescentados depois.
