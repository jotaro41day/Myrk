# Contrato da linguagem 0.1.0

- Entrada obrigatória: `fn main() -> i32`; o valor retornado é o código de saída.
- Tipos: `i32`, `f32`, `f64`, `bool`. Tipos em parâmetros, variáveis e retornos
  são obrigatórios. Literais inteiros são `i32`, decimais são `f64`, e o sufixo
  `f32` cria um literal `f32`. Não há promoção ou conversão implícita.
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
- Chamadas usam assinaturas declaradas e aceitam funções definidas depois da
  chamada. `print` aceita um escalar e adiciona uma quebra de linha.
- Subexpressões e argumentos de chamadas são avaliados da esquerda para a
  direita. O backend materializa valores intermediários para preservar a ordem.
- O compilador informa arquivo, linha e coluna nos erros de sintaxe e tipos.
  O runtime só informa a categoria da falha de divisão.

Não há ainda módulos, imports, strings, threads ou tensores. Os programas são compilados AOT para C11 e depois para um
executável nativo por um compilador C externo.

## Buffers locais

`buffer x: f32[n];` ou `buffer x: f64[n];` aloca n elementos contíguos,
zerados. n é i32 e avaliado uma vez. `x[i]` lê e `x[i] = valor;` escreve.
Índice i32 fora de `[0,n)`, tamanho negativo ou falha de alocação encerram
com código 70. Um buffer vazio é válido. O índice é avaliado/verificado antes
do valor a armazenar. Buffers são liberados no fim do escopo, inclusive em
retornos antecipados; não podem ser copiados, passados ou retornados ainda.
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
