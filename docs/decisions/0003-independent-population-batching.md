# ADR 0003 — Batching independente e pool CPU persistente

## Context / evidence

Pedido: acelerar fortemente o caminho SNN preservando precisão e solver.
Usuário relatou trecho de medição Android com 391,197 M updates/s, 511,251 ms,
3M spikes e hash 3bbedd68576516eb; o recorte não identifica variante/configuração
completa, portanto não será comparado diretamente com medições cloud.
Probe local descartável (Clang19/Xeon, 1M f32, 200 passos): baseline ~192 ms,
tile256 ~288 ms, SIMD manual mantendo estado em registradores com 1/2/4 grupos
~781/338/201 ms. Não há evidência para manter essa complexidade.

## Decision

Adicionar uma transformação conservadora de IR para loops cujo corpo seja
exatamente `step(p);`, ou `step(p); total = total + spikes(p);` com total i32.
Somente Izhikevich independente, corrente uniforme/constante e estado local sem
escape existem hoje. A ausência de outras instruções prova que não há monitor,
propagação, efeitos externos ou dependência de outro neurônio entre passos.
Preservar ordem/avaliação única de bounds, ranges vazios, estado final,
spikes do último passo e soma modular i32 dos spikes. Observações no corpo
impedem batching. Nada pula integração ou muda o solver/dtype.

O batch divide o intervalo de neurônios em blocos disjuntos, executa todos os
passos de cada bloco e faz redução somente ao final. Uma thread é default.
`MYRK_THREADS=1..64` escolhe explicitamente CPU threads. Pool pthread criado
uma vez por processo, reutilizado entre batches e encerrado via atexit; main
participa. Sem alocações, criação de threads, atomics globais por spike ou
barreiras por timestep. Estados e acumuladores são privados por partição.

## Options / consequences

Bloqueio temporal/SIMD manual foi rejeitado no probe. Multicore pode beneficiar
populações grandes, mas aquecimento, big.LITTLE e limite de CPU podem limitar
ou inverter ganho. Não ativar todos os cores automaticamente. Não há requisito
OpenMP, CUDA ou root: pthread está disponível em Linux/Android.

C de referência usa o mesmo pool, particionamento, contagens e trabalho.
Registrar compilação, threads e custos de startup do pool separados do kernel;
medição nativa pode incluir startup na primeira chamada, explicitamente.
Testes: lote vs sequência de passos, ambos dtypes, contagem total/último passo,
tails, população vazia/menor que pool, batch vazio, chamadas consecutivas,
wrap i32, bounds com efeitos e rejeição de loops com observação.

## Safety gate for future features

Este passe só é válido para o modelo independente atual. Adicionar corrente
por timestep, sinapses, delays, callbacks, monitores ou alias exige estender a
prova de dependências antes de permitir batching. Nunca aplicá-lo a uma rede
conectada apenas porque seu modelo neuronal é Izhikevich.
