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

## Experimento 0004 — batches independentes e pool persistente

Hipótese: quando não há observação ou comunicação entre passos, cada partição
pode executar todos os timesteps sem barreiras globais. Isso preserva trabalho
e aritmética, remove sincronização por timestep e permite multicore. É válido
somente para o modelo independente atual. Ver ADR 0003 para a prova/limites.

Probe descartável anterior com Clang/Xeon, 1M f32/200 passos: loop convencional
~192 ms; tile256 ~288 ms; manter estado em vetores durante muitos passos com
1/2/4 grupos ~781/338/201 ms. O gargalo de dependência e paralelismo dentro do
núcleo anulou a redução de tráfego nesse probe. Não mantivemos SIMD manual
nem anunciamos ganho; isso não descarta futuras variantes medidas em Android.

Mudança: passe de IR reconhece somente loop com step(p) ou step+acumulação
modular i32 de spikes. Bounds têm avaliação única e ordenada. O runtime
MYRK_THREADS=1..64 divide índices contíguos entre workers pthread persistentes;
main participa; redução só ao final. Não há alocação, thread creation, atomics
globais por spike ou barreira por timestep. Estado segue SoA e parâmetros são
uniformes. Workers anunciam prontidão antes de cronometrar o kernel.

Gate: C sequencial por timestep, batch vs C com **todos** os estados e contagens,
prefixos 1/2/7/31/80; f32/f64, tails, população menor que pool, reutilização,
range vazio/negativo, bounds com efeitos e overflow modular. 47 testes passaram
com GCC14.2 e Clang19.1.7. Exemplo Izhikevich com quatro threads passou em GCC
ThreadSanitizer. Revisão independente não encontrou corrida após acrescentar
handshake de prontidão. Assembly cross AArch64 do callback mantém NEON .4s,
width4/interleave2, sem FMA; ainda não é execução Android.

Medição final: código f89a252, Xeon Platinum 8573C, Linux cloud com quota de
**2 CPUs**, Clang19.1.7 O2 estrito, 1M neurônios × 200 passos, dt=.5 ms,
100 ms biológicos, 2 warmups e 5 amostras. Ordem das variantes gira. Pool
criado fora do timer, custo separado no JSON; wall/process inclui tudo.
Não comparamos com um antigo resultado em outro dispositivo.

| dtype | threads Myrk/C | Myrk ms | C mesmos recursos ms | Myrk antigo 1 thread ms | M updates/s | ganho vs antigo | realtime |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| f32 | 1 | 178.559 | 173.957 | 190.449 | 1120.1 | 1.07× | 0.560 |
| f64 | 1 | 391.992 | 380.841 | 379.939 | 510.2 | 0.97× | 0.255 |
| f32 | 2 | 90.475 | 96.506 | 179.536 | 2210.5 | 1.98× | 1.105 |
| f64 | 2 | 202.799 | 193.299 | 391.916 | 986.2 | 1.93× | 0.493 |
| f32 | 4 | 92.885 | 102.888 | 176.920 | 2153.2 | 1.90× | 1.077 |
| f64 | 4 | 239.703 | 261.629 | 384.983 | 834.4 | 1.61× | 0.417 |

Uma thread preserva o loop original, sem chamar o executor paralelo; pequenas
diferenças nessa linha não são otimização, mas variação das medições. O piloto
do caminho de uma thread via callback regrediu (~7%) e foi restringido: o
compilador mantém o loop original quando MYRK_THREADS=1. Quatro threads não
superaram duas neste host limitado a duas CPUs; Android requer medição própria.

Os ~1,98× em f32 / ~1,93× em f64 são ganhos sobre Myrk **single-thread**,
não sobre C paralelo. C com o mesmo pool é competitivo; não há prova de
liderança sobre simuladores fortes. Em f32/2 threads, 1M updates independentes
atinge realtime >1 neste Xeon, **não** numa rede conectada ou num celular.

JSON completo: [1 thread](measurements/2026-10-04-pool-1.json),
[2 threads](measurements/2026-10-04-pool-2.json),
[4 threads](measurements/2026-10-04-pool-4.json).

```sh
for threads in 1 2 4; do
  CC=clang python3 -m benchmarks.neuron.izhikevich --sizes 1000000 --steps 200 \
    --repeat 5 --warmup 2 --threads "$threads" --summary --output "izh-$threads.json"
done
```

Trecho Android fornecido pelo usuário antes desta mudança: mediana 511,251 ms,
391,197 M updates/s, 3M spikes, hash `3bbedd68576516eb`. O hash coincide com o
caso local f32/1M/200. Faltam no recorte os cabeçalhos e identificação Myrk/C;
não atribuímos essa medição ao pool nem inferimos ganho Android a partir dela.

Decisão: manter pool opcional, default uma thread e fallback original;
publicar comparação 1/2/4 com JSON e resumo curto. Medir no Termux antes de
selecionar número de threads/afinidade ou agendamento para big.LITTLE.

## Experimento 0005 — cache blocking temporal explícito
Hipótese: a independência comprovada no ADR 0003 permite trocar a ordem de
blocos e timesteps. Avançar um bloco por todos os passos pode reutilizar v/u
em cache e diminuir tráfego entre cache/DRAM, mantendo todas as atualizações.
Não é skip-ahead, agrupamento dos 97 estados repetidos ou mudança de precisão.

Mudança: `MYRK_TILE` / `--tile` limita neurônios por bloco dentro de cada
partição. `0` continua default e mantém o caminho existente. Cada bloco retorna
total e último count; o último count da população é a soma dos últimos counts
**de todos os blocos**, não apenas do último bloco. Configuração lida no thread
de controle e copiada para o job. Não há armazenamento ou alocação adicionais
proporcionais a N. C de referência usa o mesmo blocking e recursos.

Gate: C sequencial continua conferindo todo estado/count por timestep; o lote
com blocos é conferido contra o estado final, total e último count. Gates Python,
prefixos, hashes e ambos dtypes permanecem. Testes incluem tile1, tiles ímpares,
tails, blocos maiores que partição, chamadas repetidas e mais workers que
neurônios. Um teste com todos os 19 neurônios disparando em cada passo rejeitou
explicitamente a mutação `last += chunk_last` para `last = chunk_last`.
51 testes passaram em GCC14.2 e Clang19.1.7; revisão independente não encontrou
defeitos na mudança de blocking/contagens.

Medição: código 7530954, 2026-10-05, Xeon Platinum 8573C, Clang19.1.7 O2,
modo estrito sem FMA, dt=.5 ms, cloud compartilhada com quota de 2 CPUs e
limite de 8 GiB. Sem afinidade, controle térmico ou contadores. Os sweeps são
sequenciais, nunca concorrentes. Há **forte variação**; preservar toda amostra
é essencial. Estes números não foram executados em Android.

Primeiro sweep: 2 threads, 100 passos, 1 warmup, 3 amostras por variante;
Myrk/C/antigo alternam ordem. Tempos abaixo são do kernel em ms.

| N | dtype | tile | Myrk mediana | faixa Myrk | C mesmos recursos |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1,000,000 | f32 | 0 | 83.883 | 45.006–91.600 | 98.813 |
| 10,000,000 | f32 | 0 | 1044.196 | 1016.900–1136.989 | 1119.164 |
| 1,000,000 | f64 | 0 | 99.434 | 95.923–109.439 | 109.653 |
| 10,000,000 | f64 | 0 | 2166.783 | 1511.408–2216.475 | 1303.105 |
| 1,000,000 | f32 | 2048 | 87.789 | 86.479–101.448 | 103.509 |
| 10,000,000 | f32 | 2048 | 990.433 | 892.858–1286.241 | 1011.815 |
| 1,000,000 | f64 | 2048 | 273.539 | 167.510–318.345 | 350.711 |
| 10,000,000 | f64 | 2048 | 2135.280 | 1000.808–2579.556 | 2032.633 |
| 1,000,000 | f32 | 16384 | 59.188 | 47.856–84.885 | 52.891 |
| 10,000,000 | f32 | 16384 | 926.323 | 517.265–954.206 | 945.912 |
| 1,000,000 | f64 | 16384 | 99.115 | 96.810–101.622 | 99.062 |
| 10,000,000 | f64 | 16384 | 1884.119 | 1002.092–1934.815 | 1935.808 |

Repetição para separar blocking de multicore: **uma thread**, f32, 200 passos,
2 warmups e 5 amostras. `antigo` é o Myrk step original da mesma sessão,
sem blocos; C usa o mesmo tile da variante Myrk.

| N | tile | Myrk ms | faixa Myrk | C ms | antigo ms | ganho vs antigo |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,000,000 | 0 | 202.847 | 186.542–316.091 | 202.742 | 228.062 | 1.12× |
| 10,000,000 | 0 | 2139.846 | 2055.506–2296.989 | 2210.987 | 2016.921 | 0.94× |
| 1,000,000 | 16384 | 192.689 | 175.124–225.102 | 178.683 | 193.868 | 1.01× |
| 10,000,000 | 16384 | 1929.589 | 1882.122–2074.091 | 1925.379 | 2149.604 | 1.11× |

Assembly: callback com blocos cross-compilado para aarch64-linux-android24
continua com NEON f32 `.4s`, width4/interleave2, compare/select e sem FMA.
Saves/restores no prólogo/epílogo não são spills do loop interno. No x86 f64,
Clang mantém SSE2 width2/interleave2; há reload de um parâmetro uniforme da
pilha no loop, evidência de pressão de registradores. Não atribuir a regressão
inteira a esse reload sem isolamento/contadores. AArch64 tem mais registradores
vetoriais, e cross compilation não é medição Android.

Tráfego lógico continua 16 B/update f32, 32 B f64; cache blocking muda a possível
origem/destino físico desse tráfego. Working set por bloco: tile*8 B f32,
tile*16 B f64 (2048: 16/32 KiB; 16384: 128/256 KiB). Sem arrays extras,
sem compressão de estado; RSS no JSON continua incluindo o processo todo.

Decisão: **não escolher tile automaticamente**. Tile2048 teve regressões
fortes em f64; tile16384 deu ganho pequeno em 10M f32 single-thread (~11%
sobre o antigo contemporâneo), quase nenhum em 1M. Ruído e sobreposição de
faixas impedem concluir ganho robusto/universal. Manter como opção experimental
para ablação no hardware real; nenhuma alegação de aceleração grande ou liderança.
O ganho multicore anterior de ~1,98× continua sendo um experimento separado.

Reprodução (usar Clang19.1.7 para reproduzir a toolchain, ou medir o Clang real
no dispositivo; não misturar hosts):

```sh
for tile in 0 2048 16384; do
  CC=clang python3 -m benchmarks.neuron.izhikevich --sizes 1000000 10000000 \
    --steps 100 --repeat 3 --warmup 1 --threads 2 --tile "$tile" \
    --summary --output "tile-two-$tile.json"
done
for tile in 0 16384; do
  CC=clang python3 -m benchmarks.neuron.izhikevich --sizes 1000000 10000000 \
    --dtype f32 --steps 200 --repeat 5 --warmup 2 --threads 1 --tile "$tile" \
    --summary --output "tile-one-$tile.json"
done
```

Raw JSON: [2 threads / tile0](measurements/2026-10-05-tile-two-threads-0.json),
[tile2048](measurements/2026-10-05-tile-two-threads-2048.json),
[tile16384](measurements/2026-10-05-tile-two-threads-16384.json),
[1 thread / tile0](measurements/2026-10-05-tile-one-thread-0.json),
[tile16384](measurements/2026-10-05-tile-one-thread-16384.json).
