# Estado para retomar o desenvolvimento

Atualizado em 2026-10-05. Continuar **este repositório**; não reinicializar,
criar fork/projeto novo ou repetir o bootstrap. Nome: Myrk. Repositório:
https://github.com/jotaro41day/Myrk. Versão 0.1.0 experimental, adições em
Unreleased. O usuário pediu commit e publicação frequentes de cada incremento
validado para preservar o progresso se a sessão terminar.

## Implementado e publicado

- Pipeline Python stdlib: lexer/parser → IR tipada → C11 → Clang/GCC nativo.
- Escalares i32/f32/f64/bool, funções, loops; exemplos iniciais preservados.
- Inferência local exata, expoentes e sufixos de precisão em números, comentários
  de bloco aninhados. Incremento geral 1: 81 testes passam com GCC.
  ADR 0005/plano general-language registram a expansão em andamento.
- Buffers locais `buffer x: f32[n];` / f64, zerados, índice verificado,
  liberados por escopo e retorno. Sem escape/cópia/empréstimo entre funções.
- `PopulationSpec` / `UniformParameter` na IR; Izhikevich f32/f64 com SoA v/u,
  parâmetros uniformes, solver Euler simultâneo, threshold após passo.
- `step`, `spikes` (último passo), `voltage` e `recovery`; sem sinapses ou
  recording. `examples/izhikevich.myrk` imprime 3000 / -68.0648041 / -5.36637402.
- Referências independentes C e Python com arredondamento por operação.
  Laboratório compara todos os estados e spikes antes de reportar desempenho.
- Sweep 1K/10K/100K/1M/2M/5M/10M f32/f64 em Xeon, GCC O2/O3 e Clang O2.
  Dados preservados em docs/measurements, resumo em PERFORMANCE/MILLION_NEURON_PLAN.
- 74 testes passam localmente com GCC 14.2 e Clang 19.1.7; exemplos buffers/SNN
  passaram com ASan/UBSan. CI Linux passa; matriz GCC/Clang verifica ambos.
- Revisão corrigiu duplo arredondamento de parâmetros f32: preservar decimal
  original no C, limites exatos com Fraction. Não reintroduzir conversão via f64.

## Incremento de desempenho publicado

Loops independentes sem observação intermediária agora têm IR de batch e
pool pthread persistente via MYRK_THREADS=1..64. Uma thread mantém o loop
original; mais threads executam partições sem barreiras por timestep. Não
aplicar isso a futuras redes conectadas sem nova prova de dependências.
`--threads`, `--schedule`, `--summary` e `--output` no laboratório permitem
comparar Myrk/C com mesmos recursos e o Myrk antigo single-thread.
1M f32/200 passos no Xeon com 2 threads: 90,475 ms, 2,21 bilhões updates/s,
1,98× sobre a variante antiga medida na mesma sessão. 4 threads não ganharam
sobre 2 no host com quota de 2 CPUs. Estado/hash/spikes idênticos, sem fast-math.
ThreadSanitizer no exemplo passou. Android do pool ainda precisa de teste.

Cache blocking temporal explícito: MYRK_TILE / --tile, default 0, dentro das
partições independentes. Todos os estados, total/último spikes preservados.
Sweeps 0/2048/16384 com 2 threads e repetição 0/16384 com 1 thread em 1M/10M;
experimento 0005 e raw JSON datado 2026-10-05. Há ruído grande e regressões
com tile2048 f64. Tile16384/1thread/10M f32 ~11% sobre step da mesma sessão;
1M praticamente empatado. Não promover valor automático nem alegar ganho
Android. O callback mantém NEON no cross compile. Próximo gate é ablação no
Termux, não repetir instalação/bootstrap/pesquisa já existentes.

## Modelos oficiais

IF, LIF, Izhikevich, QIF, AdEx e HH nativos em f32/f64. Catálogo estático
myrk/models.py preserva modelo/solver/estados na IR. IF/LIF/QIF usam v; AdEx
v/w; HH v/m/h/n, Euler tensão + Rush–Larsen gates, taxas expm1 estáveis e
spikes por cruzamento sem reset. Adaptação/gates têm consultas tipadas e
índices verificados. Exemplos e contratos em docs/NEURON_MODELS.md. Batching
continua restrito ao Izhikevich. Laboratório complementar benchmarks.neuron.models
tem C independente e Python para os cinco novos modelos, gates de todos os
estados/spikes por timestep e hash por amostra. Baselines Clang em 1K/10K
preservados em docs/measurements/2026-10-05-official-models-clang.json.
LIF nativo também confere o baseline original C/Python (64×200), em sete
populações por corrente; todos os 64 estados são realmente atualizados.
Não confundir unidade point-neuron pF/nS/pA com HH uF/mS/uA por cm².
No HH a temperatura das taxas é 6.3 C, sem scaling implícito.

## Evidência e limites

Clang 1M f32: ~1,12 bilhão de updates/s no Xeon, realtime 0,559× a dt=.5 ms.
C equivalente ~1,10 bilhão; não há evidência de liderança. São somente updates
independentes. Clang gera NEON no cross compile AArch64, mas **novo código
não foi executado no Android**. GCC O3 não melhorou consistentemente; O2
estrito continua default. Nenhum fast-math ou FMA implícito.

Usuário já validou base anterior: Android 15/AArch64, modelo 25078PC3EG,
Python 3.14.6, Clang 21.1.8, 17 testes e scalar/LIF C baseline. Não pedir
novamente esses dados. Versão Termux/estado térmico ainda não informados;
não bloquear desenvolvimento por isso.

## Próximos incrementos

1. [#4](https://github.com/jotaro41day/Myrk/issues/4): validar novo caminho e
   benchmarks 1K→1M no Termux, depois aumentar se a memória permitir.
2. [#6](https://github.com/jotaro41day/Myrk/issues/6): baseline de bandwidth,
   ablação de layouts/fusão e diagnóstico de vetorização GCC estrita.
3. [#5](https://github.com/jotaro41day/Myrk/issues/5): SpikeSet e compactação;
   depois especialização de scheduling do pool existente, sinapses CSR reais, propagação, delays e híbrido.
4. [#2](https://github.com/jotaro41day/Myrk/issues/2): buffers locais feitos;
   benchmark dedicado para acesso genérico de buffers e passagem entre funções
   ainda não estão implementados. Não tratar o benchmark de população como
   prova do desempenho de todos os loops genéricos.
5. LIF/IF/QIF/AdEx/HH básicos implementados; otimizações novas exigem prova,
   baselines e validação Android próprias. HH/AdEx exp/expm1 ainda são libm
   escalar; aproximações futuras devem ser explícitas. GPU/autotuning/AD vêm depois.

## Comandos de verificação

```sh
CC=gcc python3 -m unittest discover -s tests -v
CC=clang python3 -m unittest discover -s tests -v
python3 -m compileall -q myrk benchmarks tests
sh -n install.sh
python3 -m myrk run examples/izhikevich.myrk
python3 -m benchmarks.neuron.izhikevich --sizes 17 1000 --steps 80 --repeat 1 --warmup 0
python3 -m benchmarks.neuron.models --sizes 17 --steps 40 --repeat 1 --warmup 0 --summary
```

Para retomar: `git status`, ler ADR 0002/ROADMAP/PERFORMANCE e verificar
issues/CI antes de mudar código. Preferir incrementos pequenos com teste,
commit e publicação imediata. Não executar sweeps concorrentes nem apresentar
cross compilation como execução real. Não comparar Python puro como adversário.
