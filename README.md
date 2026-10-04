# Myrk

Myrk é uma linguagem experimental para computação neural e científica. A versão
0.1.0 implementa apenas uma fatia inicial: código fonte → lexer/parser → análise
semântica → IR tipada → C gerado → executável nativo por Clang ou GCC. O binário
gerado não precisa de Python. Myrk é um projeto independente, inspirado em
questões de desempenho levantadas pelo [AresY](https://github.com/Jotaroofdioinbrando/AresY).

**Estado atual:** funções, `i32`, `f32`, `f64`, `bool`, variáveis imutáveis (`let`)
e mutáveis (`var`), laços `for` de faixa exclusiva, aritmética, comparações,
`print` e `return`. Ainda não há arrays, tensores, populações neurais, SNN,
SIMD explícito ou paralelismo. Não há alegação de vantagem de desempenho.

## Começar

Requer Python 3.10+ e Clang ou GCC. Na cópia do repositório:

```sh
python3 -m myrk run examples/hello.myrk
python3 -m myrk check examples/sum.myrk
python3 -m myrk build examples/sum.myrk -o /tmp/myrk-sum
/tmp/myrk-sum
python3 -m myrk --version
```

Programa mínimo (`.myrk`):

```myrk
fn main() -> i32 {
    print(42);
    return 0;
}
```

`myrk emit-c arquivo.myrk` mostra o C gerado. `check` não exige compilador C.
`run` compila num diretório temporário. `build` cria um executável no caminho
pedido por `-o`, ou ao lado do fonte sem a extensão. `--help` lista os comandos.

## Termux / Android

Primeiro alvo de desenvolvimento: CPU AArch64. A instalação usa Python e Clang
disponíveis no Termux, sem root ou CUDA. **O processo está preparado para
Termux, mas ainda não foi validado num dispositivo Android real.**

```sh
pkg update
pkg install python clang git coreutils
git clone https://github.com/jotaro41day/myrk.git
cd myrk
./install.sh
myrk run examples/hello.myrk
```

No Termux, `install.sh` usa `$PREFIX` (normalmente
`/data/data/com.termux/files/usr`). Fora dele, instala em `~/.local`. Pode-se
escolher `./install.sh --prefix /caminho/absoluto` ou definir `MYRK_PREFIX`.
Rodar o instalador novamente atualiza os arquivos do Myrk, sem editar arquivos
de configuração do shell. Se o destino personalizado não estiver no `PATH`,
adicione `<prefix>/bin` ao `PATH`. Para desinstalar, remova apenas
`<prefix>/bin/myrk` e `<prefix>/share/myrk`.

O compilador usa `clang` quando disponível, senão `cc`. Defina `CC` para
selecionar outro compilador compatível. O processo de compilação exige Python;
os executáveis produzidos usam somente a biblioteca C padrão.

## Sintaxe atual

Veja [examples/sum.myrk](examples/sum.myrk) e
[examples/numeric.myrk](examples/numeric.myrk). `1.5f32` é `f32`; `1.5` é
`f64`. Não existem conversões numéricas implícitas. `for i in 0..n` percorre
`0` até `n - 1`. Todas as funções devem terminar com `return`. Detalhes e
limitações estão em [docs/LANGUAGE.md](docs/LANGUAGE.md).

## Testes e benchmarks

```sh
python3 -m unittest discover -s tests -v
python3 benchmarks/run.py
python3 -m benchmarks.lif
```

O benchmark inicial compara o mesmo laço `i32` com um baseline C compilado
com as mesmas flags. Ele confere o checksum antes de medir. Isso valida o
instrumento, não mede ainda uma vantagem neural. Há também um baseline LIF
time-driven em C, validado contra um oráculo Python em escala pequena; Myrk
ainda não compila esse modelo. Metodologia e resultados
estão em [docs/PERFORMANCE.md](docs/PERFORMANCE.md).

## Arquitetura e próximos passos

O [ADR 0001](docs/decisions/0001-bootstrap-backend.md) explica a escolha
inicial do backend. O [roadmap](docs/ROADMAP.md) define critérios verificáveis
para introduzir buffers, tensores e LIF antes de testar esparsidade e execução
por eventos. A IR atual é escalar e tipada; operações neurais serão adicionadas
somente junto a semântica, testes diferenciais e um baseline medido.

Licença: MIT. Consulte [CONTRIBUTING.md](CONTRIBUTING.md) antes de alterar a
linguagem ou otimizar kernels.
