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
