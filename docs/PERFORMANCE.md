# Performance journal

## Regras

Testar correção antes de medir velocidade. Baselines devem ter mesma operação,
algoritmo, dtype, tamanho, modo numérico e número de threads. Registrar versões,
hardware, flags, warmup, amostras, mediana, variação, checksum, tempo de
compilação e tamanho do binário. Não extrapolar um microbenchmark para redes
neurais ou para Termux. Em Android, registrar condições térmicas.

## Baseline 0001 — laço escalar `i32`

Hipótese: validar a infraestrutura de compilação e medição, sem hipótese de
vantagem. O programa soma `i % 7` para `i` em `[0, 50_000_000)` e imprime
`149999997`. Myrk e C usam a mesma função de trabalho e `-O2 -fwrapv
-fno-fast-math -ffp-contract=off`. `benchmarks/run.py` mede processo completo
incluindo startup, após warmup, e registra tempo de compilação separadamente.

O benchmark mede pico RSS por filho via `wait4` onde disponível e usa um
programa separado que imprime `42` como aproximação de startup (inclui I/O).
Ainda não mede throughput multithread nem estados neurais.
Executar `python3 benchmarks/run.py` para produzir JSON reproduzível. Resultados
locais devem ser acrescentados abaixo com ambiente e data, sem tratar um único
host como evidência geral.

### Execução local — 2026-10-04

Linux x86-64, Intel Xeon Platinum 8573C (3 CPUs visíveis), GCC 14.2.0,
7 amostras após 2 warmups. Checksum idêntico `149999997`.

| Variante | Mediana | Faixa | Compile time | Pico RSS | Binário |
| --- | ---: | ---: | ---: | ---: | ---: |
| Myrk | 48,594 ms | 42,436–69,207 ms | 131,446 ms | 12.928 KiB | 15.960 B |
| C direto | 44,555 ms | 42,219–78,138 ms | 48,934 ms | 12.928 KiB | 15.952 B |

O tempo de compilação Myrk inclui iniciar Python, analisar e invocar GCC; o
tempo C começa diretamente no GCC. O proxy de startup (`print 42`) teve
medianas 1,803 ms (Myrk) e 1,462 ms (C). A variação entre amostras é maior
que a diferença de desempenho observada; não há conclusão de vantagem.

### Termux/AArch64 — execução relatada em 2026-10-04

Android 15, AArch64, modelo `25078PC3EG`, Python 3.14.6 e Clang 21.1.8 em
`/data/data/com.termux/files/usr/bin/clang`. Versão do aplicativo Termux e
estado térmico ainda não informados. Os 17 testes passaram em 5,572 s.
Benchmark: 7 amostras após 2 warmups; checksum
`149999997` para Myrk e C.

| Variante | Mediana | Faixa | Compile time | Pico RSS | Binário |
| --- | ---: | ---: | ---: | ---: | ---: |
| Myrk | 93,203 ms | 90,652–96,201 ms | 1.118,390 ms | 19.924 KiB | 6.224 B |
| C direto | 95,039 ms | 87,603–115,373 ms | 751,634 ms | 19.924 KiB | 6.224 B |

A mediana corresponde a 536,5 milhões de iterações/s no Myrk e 526,1 milhões
no C. As faixas se sobrepõem e há apenas uma sessão; não se infere vantagem.
O proxy de startup (`print 42`, incluindo lançamento e I/O) teve medianas
21,412 ms (Myrk) e 15,699 ms (C), também com variação relevante.

## Baseline 0002 — LIF time-driven sem sinapses

`python3 -m benchmarks.lif` compila um loop C `f64` sobre um buffer contíguo
de tensões. Cada neurônio tem corrente constante dependente de `i`, Euler com
`dt/tau=0.05`, threshold `1.0` e reset `0.0`. Um oráculo Python executa o
mesmo modelo para 64 neurônios e 200 passos; a contagem de spikes precisa ser
exata e a soma final das tensões difere por no máximo `1e-8`. A medição padrão
usa 50.000 neurônios × 200 passos e relata updates/s, tempo, RSS, binário e
compile time do C. Ainda não há implementação Myrk equivalente. Comparar esse
baseline com Myrk será o gate do M5, sem usar Python puro como adversário de
desempenho.

### Execução local — 2026-10-04

Mesmo Xeon/GCC acima. Validação C/Python passou em 64 × 200. Em 50.000 × 200,
o checksum C foi `435711 19588.354593350865`. Após 2 warmups e 5 amostras,
mediana de 20,889 ms (faixa 19,602–24,316 ms), equivalente a aproximadamente
478,7 milhões de atualizações de neurônio por segundo. Pico RSS mediano:
12.672 KiB; compile time: 62,631 ms. Este número pertence ao baseline C,
sem comparação com Myrk ou validação Android.

### Termux/AArch64 — execução relatada em 2026-10-04

Mesmo Android 15/AArch64 e Clang acima. O oráculo Python/C passou; checksum
`435711 19588.354593350865` para 50.000 neurônios × 200 passos. Após 2
warmups e 7 amostras, a mediana C foi 94,684 ms (faixa 86,056–100,413 ms),
aproximadamente 105,6 milhões de atualizações de neurônio/s. Pico RSS mediano:
18.660 KiB; binário: 7.224 B; compile time: 704,266 ms. É um baseline C;
Myrk ainda não compila esse modelo LIF.

## Experimento 0003 — Izhikevich nativo, escala e autovetorização

### Hipótese e baseline

Preservar população, precisão e uniformidade na IR permite emitir dois arrays
SoA, parâmetros escalares, nenhuma alocação por passo e uma passagem fundida
para integração/threshold/reset/contagem. Não há hipótese de vencer C pelo
simples uso de compilação nativa. Primeiro precisamos comparar trabalho igual.

Contrato: Euler simultâneo, threshold >=30 após passo, reset v=c/u+=d;
a=.02,b=.2,c=-65,d=8,dt=.5 ms,current=10. Estado inicial heterogêneo com 97
padrões repetidos, mas cada elemento é atualizado a cada passo. Sem sinapses,
listas de spikes ou monitores. Referência C independente e oráculo Python que
arredonda cada operação f32. A referência pode ser otimizada com as mesmas flags.

### Implementação e corretude

`PopulationSpec` e `UniformParameter` chegam ao backend sem perder modelo,
solver, dtype ou uniformidade. Kernel lê v/u, calcula os dois novos estados,
faz threshold/reset e conta spikes. Dados: 8 B/neuron f32 ou 16 B f64;
tráfego lógico: 16/32 B/update, cerca de 14–15 FLOPs, sem arrays a/b/c/d.
Não há cópia/escape de populações nesta versão. Consultas de estado verificam
índices. Buffers locais genéricos têm ownership por escopo e retorno.

Python confere 17 neurônios × 80 passos, cada estado e contagem. Para cada
escala, C confere todos os elementos e spikes em **cada timestep**; zero erro
na mesma precisão em todas as escalas. Toda amostra cronometrada também
confere contagem, somas e hash final. Teste de mutação troca .04 por .05 e
confirma que o gate rejeita o kernel errado. Exemplos vector/izhikevich
passaram com AddressSanitizer e UBSan em GCC. Revisão independente encontrou
duplo arredondamento de literais f32; corrigido preservando decimal original,
com limites exatos por frações e regressão automatizada.

### Hardware e execução

2026-10-04: Xeon Platinum 8573C, Linux x86-64, cloud compartilhada, quota de
2 CPUs, limite 8 GiB; **uma thread por kernel**. Sem pinning/perf counters ou
controle térmico. 1K/10K/100K/1M/2M/5M/10M, f32 e f64, 100 passos (50 ms
simulados), 1 warmup, 3 amostras alternando ordem Myrk/C. Temporização nativa
CLOCK_MONOTONIC exclui init/checksum/IO. RSS lido no próprio processo em
/proc/self/status; não usar o high-water herdado do pai Python como RAM do kernel.

Reprodução de cada relatório (selecionar CC/versão correspondente):

```sh
CC=cc python3 -m benchmarks.neuron.izhikevich --all-scales --steps 100 --repeat 3 --warmup 1 --opt O2
CC=cc python3 -m benchmarks.neuron.izhikevich --all-scales --steps 100 --repeat 3 --warmup 1 --opt O3
CC=clang python3 -m benchmarks.neuron.izhikevich --all-scales --steps 100 --repeat 3 --warmup 1 --opt O2
```

### Resultado (1M, f32, mediana)

| Toolchain/flags | Myrk M updates/s | C M updates/s | Myrk ms/passo | realtime |
| --- | ---: | ---: | ---: | ---: |
| GCC 14.2 O2 | 441,2 | 458,5 | 2,267 | 0,221 |
| GCC 14.2 O3 | 407,5 | 430,0 | 2,454 | 0,204 |
| Clang 19.1.7 O2 | 1117,4 | 1095,3 | 0,895 | 0,559 |

Com Clang, 10M f32: 828,0 M updates/s, RSS 76,92 MiB, realtime 0,041×.
Isso **não** é tempo real nem rede conectada. Tabelas completas, incluindo
f64, em [MILLION_NEURON_PLAN.md](MILLION_NEURON_PLAN.md). Raw JSON em
[measurements](measurements/); não escolher apenas a melhor amostra.
Diferenças Myrk/C variam com tamanho e ruído; não demonstram liderança.
F32/f64: no oráculo de 97 neurônios × 100 passos, max |Δv| .00673084,
max |Δu| .0000266952, nenhum spike neuron/timestep diferente. Essa é uma
verificação de sensibilidade limitada, não validação científica geral.

### Assembly / análise

GCC O2 e O3: o loop de update continuou escalar (`mulss/addss` para f32).
O3 vetorizou partes da inicialização, o que **não** conta como vetorizar update.
Clang O2: update contém `mulps/addps/subps`, máscara/select e redução inteira,
com resto escalar. Logo não atribuímos resultados apenas à flag -O3.

Cross compilation do kernel de produção com Clang 19.1.7, target
`aarch64-linux-android24`, O2/O3, freestanding e sem fast-math/FMA:

```sh
python3 -m benchmarks.neuron.emit_kernel --dtype f32 > /tmp/myrk-kernel.c
clang --target=aarch64-linux-android24 -ffreestanding -O2 -fno-fast-math \
  -ffp-contract=off -Rpass=loop-vectorize -S /tmp/myrk-kernel.c -o /tmp/myrk-kernel.s
```

Clang reporta width=4/interleave=2; no loop f32, `fmul/fadd/fsub v*.4s`,
`fcmge`, `bit`, loads/stores vetoriais e tail escalar. Sem `fmla` e sem spills
na pilha no loop. F64 O3 usa `.2d`, com múltiplos vetores; saves/restores de
registradores callee-saved aparecem no prólogo/epílogo, não no corpo do loop.
**Cross compilation não executou Android**. Clang do usuário é 21.1.8, portanto
é preciso repetir assembly/benchmark com a toolchain real.

Tráfego efetivo modelado no Clang 1M f32: aproximadamente 17,88 GB/s. Não é
bandwidth DRAM medida. Não concluir memory-bound sem baseline streaming e/ou
contadores. A 1M/dt=.5 ms, realtime exigiria ~32 GB/s lógicos; 10M ~320 GB/s.

### Decisão

Manter O2 estrito e preferência por Clang já existente no CLI. Rejeitar a
troca global para O3 por falta de ganho consistente. Não escrever intrinsics
NEON enquanto o código gerado já vetoriza e falta medição Android. Registrar
GCC como alvo a investigar (if-conversion/cost model), sem fast-math escondida.
Próximo gate: Termux real, layout/memória e SpikeSet antes de multicore/CSR.
