# Million neuron plan

Atualizado em 2026-10-04. Meta: milhões de neurônios viáveis em hardware
limitado, com precisão e trabalho explícitos. **Não é uma rede completa**.

## Neuron update: Izhikevich

Medição local: Linux x86-64, Intel Xeon Platinum 8573C, Clang 19.1.7,
-O2 -fwrapv -fno-fast-math -ffp-contract=off. Uma thread; ambiente cloud
compartilhado com quota de 2 CPUs e limite de 8 GiB. 100 passos, dt=0,5 ms
(50 ms simulados), 1 warmup e 3 amostras alternando Myrk/C. Não é benchmark
sustentado/termal. Sem pinning, isolamento ou contadores de hardware.

RAM teórica = v+u; RAM medida = pico RSS do processo nativo, lido em
/proc/self/status. dt/threads/hardware são os mesmos em todas as linhas.
Erro=0 significa todos os estados e contagens idênticos ao C da mesma
precisão em cada passo; não significa erro zero frente ao modelo contínuo.
Realtime = tempo biológico/tempo do kernel, excluindo alocação, checksums e IO.

| Neurônios | dtype | bytes/neuron | RAM estado MiB | RSS MiB | dt ms | M updates/s | ms/passo | realtime | threads | erro vs C | status/hardware |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1,000 | f32 | 8 | 0.008 | 0.621 | 0,5 | 1400.5 | 0.0007 | 700.251 | 1 | 0 | medido / Xeon |
| 10,000 | f32 | 8 | 0.076 | 0.695 | 0,5 | 1289.4 | 0.0078 | 64.468 | 1 | 0 | medido / Xeon |
| 100,000 | f32 | 8 | 0.763 | 1.387 | 0,5 | 1197.6 | 0.0835 | 5.988 | 1 | 0 | medido / Xeon |
| 1,000,000 | f32 | 8 | 7.629 | 8.254 | 0,5 | 1117.4 | 0.8949 | 0.559 | 1 | 0 | medido / Xeon |
| 2,000,000 | f32 | 8 | 15.259 | 15.883 | 0,5 | 1126.0 | 1.7761 | 0.282 | 1 | 0 | medido / Xeon |
| 5,000,000 | f32 | 8 | 38.147 | 38.766 | 0,5 | 1139.4 | 4.3882 | 0.114 | 1 | 0 | medido / Xeon |
| 10,000,000 | f32 | 8 | 76.294 | 76.918 | 0,5 | 828.0 | 12.0777 | 0.041 | 1 | 0 | medido / Xeon |
| 1,000 | f64 | 16 | 0.015 | 0.633 | 0,5 | 554.7 | 0.0018 | 277.354 | 1 | 0 | medido / Xeon |
| 10,000 | f64 | 16 | 0.153 | 0.766 | 0,5 | 452.3 | 0.0221 | 22.613 | 1 | 0 | medido / Xeon |
| 100,000 | f64 | 16 | 1.526 | 2.152 | 0,5 | 278.7 | 0.3588 | 1.393 | 1 | 0 | medido / Xeon |
| 1,000,000 | f64 | 16 | 15.259 | 15.887 | 0,5 | 526.7 | 1.8986 | 0.263 | 1 | 0 | medido / Xeon |
| 2,000,000 | f64 | 16 | 30.518 | 31.141 | 0,5 | 508.8 | 3.9306 | 0.127 | 1 | 0 | medido / Xeon |
| 5,000,000 | f64 | 16 | 76.294 | 76.918 | 0,5 | 520.9 | 9.5991 | 0.052 | 1 | 0 | medido / Xeon |
| 10,000,000 | f64 | 16 | 152.588 | 153.215 | 0,5 | 438.8 | 22.7896 | 0.022 | 1 | 0 | medido / Xeon |

Todos os estados foram realmente atualizados, com condições iniciais variadas.
Dados completos (amostras, spikes, hashes, checksums, compilação):
[Clang O2](measurements/2026-10-04-izh-clang-o2.json),
[GCC O2](measurements/2026-10-04-izh-gcc-o2.json),
[GCC O3](measurements/2026-10-04-izh-gcc-o3.json).

A comparação f32/f64 para 97 estados iniciais × 100 passos encontrou
max |Δv|=0,00673084 e max |Δu|=0,0000266952, sem diferença de spikes nesse
caso. Não generalizar para longas simulações, outras correntes ou redes.

**Termux/AArch64: todas estas escalas ainda aguardam medição real.** Hardware
já identificado pelo usuário: modelo 25078PC3EG, Android 15, Python 3.14.6,
Clang 21.1.8. Evidência anterior cobre scalar/LIF baseline, não este kernel.

Próximo gate: rodar primeiro 1K/10K/100K/1M f32 no celular; registrar raw JSON,
versão Termux, condições térmicas, energia e afinidade se controlada. Repetir
sessões antes de comparar variantes. Só então escalar 2M/5M/10M respeitando
memória. Não presumir que usar todos os cores melhora um big.LITTLE.

## Full SNN: redes conectadas — ainda não implementadas

Estimativa mínima ilustrativa: v/u f32, CSR com destino u32 + peso f32
(8 B/sinapse) e offsets u32 (4*(N+1) B). 1 bilhão de conexões cabe em u32
para offsets, mas um formato futuro pode exigir offsets u64. Não inclui
spikes, delays, filas, plasticidade, alinhamento ou espaço de construção.

| Rede | Sinapses | RAM teórica mínima GiB | RAM medida | dtype/dt | eventos/s | realtime | threads/hardware | erro | status |
| --- | ---: | ---: | --- | --- | --- | --- | --- | --- | --- |
| 1M / fanout 10 | 10M | 0,086 | — | f32 / a definir | — | — | — | — | infraestrutura pendente |
| 1M / fanout 100 | 100M | 0,756 | — | f32 / a definir | — | — | — | — | infraestrutura pendente |
| 1M / fanout 1000 | 1B | 7,462 | — | f32 / a definir | — | — | — | — | infraestrutura pendente |

Esses mínimos já mostram por que bytes/sinapse e eventos/s são centrais.
Experimentos planejados: CSR por origem, particionamento por destino,
índices comprimidos, conectividade procedural determinística e filas por
bucket/delay. Reconstrução só ganha se custo computacional compensar tráfego.

## Gates seguintes

1. Medição Android + streaming memory baseline para separar compute/bandwidth.
2. Ablação SoA/AoSoA, vetor e fusão; medir spills e verificar assembly real.
3. SpikeSet/compactação com atividade variável; contabilizar conversões.
4. Pool persistente e scheduling estático/dinâmico, com baseline single-thread.
5. CSR, propagação, delays e rede conectada; não substituir métricas de rede
   pelas de neurônios independentes.


## Incremento multicore (mesmo modelo; 200 passos, 100 ms simulados)

1M f32 no Xeon/Clang19, 2 threads: 90,475 ms, 2210,5 M updates/s, realtime
1,105×, ganho 1,98× sobre Myrk antigo single-thread da mesma sessão. C paralelo:
96,506 ms. F64/2 threads: 202,799 ms, 986,2 M updates/s, realtime 0,493×.
As tabelas iniciais acima continuam sendo resultados históricos single-thread
com 100 passos. Não misturar durações/custos. O pool ainda não foi medido no
Android. Ver experimento 0004 em PERFORMANCE e raw JSON pool-1/pool-2/pool-4.
