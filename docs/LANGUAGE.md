# Contrato da linguagem 0.1.0

- Entrada obrigatória: `fn main() -> i32`; o valor retornado é o código de saída.
- Tipos: `i32`, `f32`, `f64`, `bool`. Parâmetros e retornos têm tipos explícitos.
  Locais podem usar `let x = 1;` / `var y = 2f32;`: o tipo é exatamente o tipo
  verificado do inicializador, sem heurística. Anotações locais continuam válidas.
  Literais inteiros são `i32`, decimais ou expoentes são `f64`; `f32`/`f64`
  escolhem a precisão (`2f32`, `1e-3f32`, `2.5E2`). Não há promoção implícita.
- Comentários `//` e `/* ... */` são aceitos; comentários de bloco podem aninhar.
- `i32` usa aritmética de 32 bits com wrap em `+`, `-`, `*` e negação, usando
  `-fwrapv` em Clang/GCC. Divisão/modulo por zero e `INT32_MIN / -1` encerram
  o processo com código 70. Divisão inteira trunca em direção a zero.
- Ponto flutuante usa as operações C do target, sem `fast-math` e com contração
  FMA desativada. A versão atual não promete resultados bitwise entre CPUs.
  Divisão por zero segue o comportamento de ponto flutuante do target.
- `let` não pode ser alterado após a declaração. `var` pode. Referências a
  nomes desconhecidos, tipos incompatíveis e duplicatas são erros.
- `for i in start..end` avalia limites uma vez e percorre o intervalo
  semiaberto `[start, end)`. Os limites e o índice são `i32`; o índice é imutável.
- `if condição { ... } else if condição { ... } else { ... }` e
  `while condição { ... }` exigem bool. O while reavalia a condição a cada
  iteração. `break;` encerra o laço mais interno; `continue;` passa à próxima
  iteração (incluindo incremento do for ou reavaliação do while).
- `&&` e `||` usam curto-circuito: o lado direito só executa quando necessário.
  Precedência, da menor à maior: `||`, `&&`, `== !=`, `< <= > >=`, `+ -`,
  `* / %`, unários `! -`. Parênteses escolhem outra ordem.
- Funções escalares devem retornar em todos os caminhos. Um if/else com
  retorno em ambos os ramos satisfaz essa regra; um laço sozinho não satisfaz.
- Chamadas usam assinaturas declaradas e aceitam funções definidas depois da
  chamada. `print` aceita um escalar e adiciona uma quebra de linha.
- Subexpressões e argumentos de chamadas são avaliados da esquerda para a
  direita. O backend materializa valores intermediários para preservar a ordem.
- O compilador informa arquivo, linha e coluna nos erros de sintaxe e tipos.
  O runtime informa a categoria da falha, sem localização de fonte ainda.

Não há ainda módulos, imports, strings, threads gerais ou tensores. Os programas são compilados AOT para C11 e depois para um
executável nativo por um compilador C externo.

## Buffers locais

`buffer x: f32[n];` ou `buffer x: f64[n];` aloca n elementos contíguos,
zerados. n é i32 e avaliado uma vez. `x[i]` lê e `x[i] = valor;` escreve.
Índice i32 fora de `[0,n)`, tamanho negativo ou falha de alocação encerram
com código 70. Um buffer vazio é válido. O índice é avaliado/verificado antes
do valor a armazenar. Buffers são liberados no fim do escopo, inclusive em
retornos antecipados, break e continue. Saídas de laço liberam apenas recursos
dos escopos abandonados; buffers externos continuam válidos. Buffers não podem
ser copiados, passados ou retornados ainda.
Veja `examples/vector.myrk` (resultado 2048).

## Populações Izhikevich

`examples/izhikevich.myrk` compila uma população nativa. A declaração exige
`Izhikevich<f32>` ou `<f64>` e parâmetros nomeados `size`, `a`, `b`, `c`, `d`,
`dt`, `current`. size é uma expressão i32; os demais são literais finitos da
precisão escolhida. dt deve ser positivo. A população possui buffers SoA v/u
inicializados com `v=c`, `u=b*c`, liberados no fim do escopo/retorno.

`step(p);` integra todos os neurônios uma vez, sem alocações. `spikes(p)`
retorna i32 com a contagem **do último passo** (zero antes do primeiro).
`voltage(p,i)`/`recovery(p,i)` consultam estado, com índice verificado.
Somente funções de consulta e step aceitam populações; não há cópia ou escape.
O solver é Euler simultâneo, dt em ms, threshold >=30 após integração e reset
v=c, u=u_next+d. Fórmulas e ordem exatas: [ADR 0002](decisions/0002-snn-populations.md).
Não é o solver clássico com dois meios passos. Não há lista de spikes,
sinapses, delays, monitores automáticos ou seleção de solver ainda.

## Outros modelos oficiais

IF, LIF, QIF, AdEx e HH também são populações nativas f32/f64. Modelo, solver,
parâmetros uniformes e estados SoA chegam explicitamente à IR. Consultas novas:
adaptation(p,i) para AdEx, gate_m/gate_h/gate_n(p,i) para HH. recovery(p,i)
requer Izhikevich; consultas incompatíveis são erros de tipo. Nomes de modelos
são case-insensitive; nomes de builtins são reservados e case-sensitive.
Contratos, unidades, parâmetros, equações e exemplos: [NEURON_MODELS.md](NEURON_MODELS.md).
Só Izhikevich participa do batching/pool nesta versão; outros modelos seguem
loops nativos sequenciais. HH não possui reset: conta cruzamentos ascendentes.

## Execução de populações em lote e CPU threads

O compilador pode agrupar um `for` cujo corpo seja somente `step(p);` ou
`step(p); total = total + spikes(p);`, com acumulador i32. A população atual
é independente e possui corrente uniforme constante. Nenhum passo é pulado;
limites são avaliados uma vez, estado final, último spike count e wrap do
acumulador são preservados. Qualquer observação/instrução adicional no corpo
impede essa transformação. O solver e precisão permanecem iguais.

`MYRK_THREADS=4 myrk run examples/izhikevich.myrk` executa lotes elegíveis
com quatro threads de CPU (incluindo a principal). Default: uma thread.
Valores válidos: 1..64; valor inválido produz runtime error 70 ao usar o pool.
O pool pthread é criado uma vez e reutilizado entre lotes; não há criação de
threads ou barreira por timestep. A contagem é reduzida ao final do lote.
Loops observados permanecem sequenciais mesmo com MYRK_THREADS > 1.

Programas nativos também aceitam MYRK_THREADS. Flags C incluem `-pthread`;
Clang/GCC e pthread em Linux/Android são suficientes, sem OpenMP/CUDA.
Mais threads podem piorar execução pequena ou aquecimento em celulares.
Esta transformação não é válida automaticamente para futuras redes conectadas.

`MYRK_TILE=2048` limita cada bloco de um lote a 2048 neurônios. Cada bloco
executa todos os passos antes do próximo, reutilizando estado em cache; todo
neurônio ainda é integrado exatamente uma vez por passo. Default `0` usa a
partição inteira. É uma opção experimental explícita, não uma escolha automática
para todo hardware. Funciona também com uma thread e não afeta loops observados.
Valores válidos: 0..2147483647; inválidos produzem runtime error 70 ao usar o
caminho elegível. Total e contagem do último passo incluem todos os blocos.
