# Roadmap baseado em gates

Versão 0.x é experimental; sintaxe e IR podem mudar com documentação no
changelog. Um gate exige código, testes, exemplo executável, documentação,
benchmark quando pertinente e commit.

| Etapa | Entrega | Gate |
| --- | --- | --- |
| M0 | Pesquisa, semântica mínima, ADR e benchmark escalar C/Myrk | decisões registradas; checksum idêntico |
| M1 | Lexer, parser, análise de tipos, IR e executável nativo | exemplos e CI passam em Linux x86-64 |
| M2 | Buffers contíguos `f32/f64`, acesso seguro, funções numéricas | testes de limites e diferencial com C |
| M3 | Redução, dot, SAXPY, IR de laço e baseline C/OpenBLAS onde cabível | medidas iguais em dtype, shape e threads |
| M4 | Tensor estático e fusão elementwise limitada | prova de equivalência e ablação de temporários |
| M5 | LIF time-driven: oráculo Python/C, estado SoA, modelo na IR | trajetórias/spikes equivalentes e throughput medido |
| M6 | Esparsidade real em CSR e delays | memória e eventos medidos contra denso |
| M7 | CPU NEON/AVX2 e pool persistente, quando perfil justificar | ganho por target sem regressão de correção |
| M8 | Event-driven/híbrido e monitoração por consulta | crossover demonstrado e custos de conversão incluídos |
| M9+ | Plasticidade, treino/autodiff, autotuning e GPU por demanda | experimento e ADR antes de cada grande subsistema |

Termux/AArch64 precisa de teste real em todas as etapas. CI x86-64 não equivale
a validação Android. Não se deve marcar uma etapa como concluída somente pela
existência de arquivos; verificar o gate no hardware relevante.
