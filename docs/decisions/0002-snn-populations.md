# ADR 0002 — Populações compiláveis e primeiro contrato Izhikevich

## Context

A prioridade passa a ser desempenho SNN em CPU, especialmente Termux/AArch64.
A fundação escalar existente funciona e não há evidência para substituí-la.
O objetivo extremo é uma hipótese de engenharia, nunca um resultado presumido.

## Options

1. Adiar SNN até construir uma linguagem tensorial completa.
2. Usar somente funções sobre arrays e perder a identidade do modelo na IR.
3. Acrescentar buffers locais e operações de população à IR tipada existente.

## Decision

Opção 3. Manter Python → IR tipada → C11 → compilador nativo. Buffers locais
`buffer x: f32[n];` são contíguos, zerados, donos da memória e liberados no
fim do escopo ou retorno. Sem cópia, escape ou empréstimo nesta fatia.
Índices e tamanhos são i32; acessos são verificados. Populações usam dois
buffers SoA, v e u; parâmetros uniformes são escalares explícitos na IR.

`population p: Izhikevich<f32>(size=1000, a=0.02f32, b=0.2f32,
c=-65.0f32, d=8.0f32, dt=0.5f32, current=10.0f32);`

Precisão f32 ou f64, parâmetros literais finitos, dt > 0, size >= 0.
Inicialização v=c, u=b*c. `step(p);` executa **Euler simultâneo**:

```
v_next = v + dt * ((((0.04 * v) * v + 5 * v) + 140 - u) + current)
u_next = u + dt * (a * (b * v - u))
spike = v_next >= 30
v = spike ? c : v_next
u = spike ? u_next + d : u_next
```

Os dois cálculos usam o estado anterior; reset ocorre após integração.
Este NÃO é o esquema de dois meios passos do código clássico de Izhikevich.
Nome de solver na IR: `euler simultaneous / threshold after step`. dt em ms.
Constantes/operações usam a precisão escolhida; sem fast-math/FMA implícitos.
`spikes(p)` conta somente o último passo; `voltage(p,i)` e `recovery(p,i)`
leem estado com checagem. Não há recording escondido ou sinapses nesta etapa.

## Consequences

Kernel funde integração, threshold, reset e contagem em uma passagem, sem
alocação por passo. Sem lista de spikes por enquanto. Referência C independente
+ oráculo Python com arredondamento por operação verificam ambos os dtypes.
Comparações f32/f64 medem erro de trajetória separadamente; identidade do
modelo contínuo não torna solvers discretos diferentes equivalentes.

Não se implementam ainda AoSoA, intrinsics, threads, eventos, sinapses ou
plasticidade. Assembly e benchmarks vão decidir a próxima otimização.
Buffers/projeções futuramente terão metadados de alias, layout e uniformidade;
não criar camadas vazias de IR agora.

## Evidence

Fundação validada pelo usuário: 17 testes, Android 15/AArch64, modelo
25078PC3EG, Python 3.14.6, Clang 21.1.8. Ver PERFORMANCE.md para medições
anteriores e evidências desta implementação. CI Linux não valida Android.
