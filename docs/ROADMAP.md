# Roadmap SNN — prioridades revisadas em 2026-10-04

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
| M3 | Population/UniformParameter na IR, Izhikevich Euler explícito, oráculos C/Python, trajetórias e spikes | Implementado/testado Linux; exemplo nativo; validação Android pendente |
| M4 | Lab 1K→10M, memória, throughput, timestep, realtime, estados e precisão | Sweep CPU x86 realizado; tabela no MILLION_NEURON_PLAN; Termux pendente |
| M5 | Layout SoA/AoSoA, especialização e NEON/SIMD | SoA baseline; assembly AArch64 confirma autovetorização Clang; escolher mudanças após medições reais no celular |
| M6 | SpikeSet: máscara, bitset, compactação | Medir atividade/custo de conversão; equivalência e throughput de compactação |
| M7 | Pool persistente, owner-computes, buffers locais, scheduling | Ganho sobre single-thread por população e topologia; testar big.LITTLE e aquecimento |
| M8 | Sinapses reais: CSR, índices menores, propagação | Eventos/s, bytes/sinapse, oracle de conectividade; comparar formatos/ordens e conectividade procedural |
| M9 | Delays limitados, ring/buckets; rede conectada | Spike trace e delays corretos; 1M/fanout 10→100→1000 conforme orçamento |
| M10 | Estratégias por população/projeção, híbrido/event/time | Crossover medido e semântica preservada; Izhikevich não pode pular passos por ausência de spikes |
| M11 | Plasticidade, LIF compilado e outros modelos/solvers/monitores | Precisão equivalente e custo explícito de monitoramento; referência LIF existente mantida |
| M12+ | Autotuning cacheado, tensores/BLAS/autodiff, GPU | Somente após kernels e workloads sólidos; nenhum requisito CUDA |

A IR preservará progressivamente modelo, solver, clock, precisão, uniformidade,
layout, projeção, conectividade, delays e monitores. Não se criam camadas vazias.
Compiler metadata deve eliminar arrays de parâmetros repetidos, alocações por
passo e recording não solicitado; novas eliminações de trabalho exigem prova.

Termux precisa de execução real por etapa. Cross compilation/CI x86 não garantem
Android. As medições do usuário em modelo 25078PC3EG, Python 3.14.6 e Clang
21.1.8 continuam válidas para a versão testada; não abrangem automaticamente
os buffers e populações acrescentados depois.
