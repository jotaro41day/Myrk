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

Não há ainda arrays, buffers, módulos, imports, strings, threads, tensores ou
construções SNN. Os programas são compilados AOT para C11 e depois para um
executável nativo por um compilador C externo.
