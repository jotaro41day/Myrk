# Myrk

Myrk é uma linguagem experimental com prioridade em simulação SNN de alto
desempenho, especialmente Android/Termux/AArch64. A meta é perseguir o limite
do hardware com evidência; não há alegação de ser a mais rápida. A versão
0.1.0 implementa apenas uma fatia inicial: código fonte → lexer/parser → análise
semântica → IR tipada → C gerado → executável nativo por Clang ou GCC. O binário
gerado não precisa de Python. Myrk é um projeto independente, inspirado em
questões de desempenho levantadas pelo [AresY](https://github.com/Jotaroofdioinbrando/AresY).

**Estado atual:** funções, `i32`, `f32`, `f64`, `bool`, variáveis imutáveis (`let`)
e mutáveis (`var`), inferência local exata, `if`/`else`, `while`, `for`,
`break`/`continue`, operadores lógicos com curto-circuito, aritmética,
atribuições compostas, conversões numéricas explícitas, `print` e `return`.
Funções podem retornar `unit`; chamadas também podem ser instruções.
Há buffers contíguos locais i32/f32/f64/bool com índices verificados e `len`.
Há populações nativas IF, LIF, Izhikevich, QIF, AdEx e HH em f32/f64,
com SoA, parâmetros uniformes e solvers explícitos.
Loops de populações independentes podem usar um pool CPU persistente via
`MYRK_THREADS` e blocos de cache experimentais explícitos via `MYRK_TILE`.
Ainda não há redes conectadas, tensores ou SIMD manual. Não há alegação de vantagem de desempenho.

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
disponíveis no Termux, sem root ou CUDA. **A versão 0.1.0 passou por instalação,
17 testes e os dois benchmarks em um Android 15/Termux AArch64 relatado por um
usuário.** Buffers, modelos e sintaxe acrescentados depois ainda aguardam execução
no Android. Outros dispositivos e versões ainda precisam de validação.

```sh
pkg update
pkg install python clang git coreutils
git clone https://github.com/jotaro41day/Myrk.git
cd Myrk
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

Veja [examples/language_basics.myrk](examples/language_basics.myrk),
[examples/fibonacci.myrk](examples/fibonacci.myrk) e
[examples/control_flow.myrk](examples/control_flow.myrk). `1.5f32` é `f32`;
`1e-3` é `f64`. `let x = 1;` infere i32; `var x = 1f32;` infere f32.
Não existem conversões numéricas implícitas. `for i in 0..n` percorre
`0` até `n - 1`. Funções escalares retornam em todos os caminhos. Detalhes e
limitações estão em [docs/LANGUAGE.md](docs/LANGUAGE.md).

```myrk
fn mostrar(x: f32) { print(x); }

fn main() -> i32 {
    var soma = 0f32;
    for i in 0..8 { soma += f32(i); }
    if soma > 0f32 { mostrar(soma); }
    return 0;
}
```

Strings, módulos/imports, structs/enums e coleções dinâmicas seguem pendentes;
as etapas estão no [roadmap geral](docs/ROADMAP.md#linguagem-geral).

## Testes e benchmarks

```sh
python3 -m unittest discover -s tests -v
python3 benchmarks/run.py
python3 -m benchmarks.lif
python3 -m benchmarks.neuron.izhikevich --sizes 1000 10000 100000 1000000
python3 -m benchmarks.neuron.models --sizes 1000 --summary
```

O benchmark inicial compara o mesmo laço `i32` com um baseline C compilado
com as mesmas flags. Ele confere o checksum antes de medir. Isso valida o
instrumento, não mede ainda uma vantagem neural. Há também um baseline LIF
time-driven em C, validado contra um oráculo Python em escala pequena e agora
também comparado ao LIF nativo nos testes. Metodologia e resultados
estão em [docs/PERFORMANCE.md](docs/PERFORMANCE.md).


## Modelos neurais nativos

Os modelos oficiais, parâmetros e solvers estão em [NEURON_MODELS.md](docs/NEURON_MODELS.md).

```sh
myrk run examples/if.myrk
myrk run examples/lif.myrk
myrk run examples/qif.myrk
myrk run examples/adex.myrk
myrk run examples/hh.myrk
```

O laboratório `benchmarks.neuron.models` cobre os cinco modelos novos, com
referências C independentes e oráculos Python. Atualmente esses kernels são
single-thread; o laboratório especializado Izhikevich preserva os modos
batch/multicore. São baselines corretos, sem promessa de precisão científica
para qualquer dt ou de desempenho igual entre modelos/solvers.

```sh
myrk run examples/vector.myrk
MYRK_THREADS=4 myrk run examples/izhikevich.myrk
python3 -m benchmarks.neuron.izhikevich --sizes 1000000 --dtype f32 --threads 4 --summary --output izh-4.json
```

Para comparar cache blocking no próprio dispositivo, mantendo os mesmos recursos:

```sh
for tile in 0 2048 16384; do
  python3 -m benchmarks.neuron.izhikevich --sizes 1000000 --dtype f32 \
    --threads 2 --tile "$tile" --summary --output "izh-tile-$tile.json"
done
```

O padrão é `MYRK_TILE=0`. Só use um tamanho positivo após medir; blocos pequenos
podem piorar desempenho. `MYRK_THREADS=2 MYRK_TILE=16384 myrk run examples/izhikevich.myrk`
ativa essa configuração para loops elegíveis sem observação intermediária.

Populações preservam estados SoA contíguos, parâmetros uniformes e solver
explícito; Izhikevich usa dois buffers e Euler simultâneo. `step`, `spikes`, `voltage` e `recovery` são operações da
linguagem. **São neurônios independentes: ainda não há conectividade ou sinapses.**
O laboratório confere todos os estados/spikes com C antes de reportar velocidade,
além do oráculo Python pequeno. Dtypes são comparados separadamente, sem
fast-math. Escalas até 10M têm orçamento de memória configurável; detalhes em
[benchmarks/neuron/README.md](benchmarks/neuron/README.md).

Para atualizar a instalação existente no Termux:

```sh
cd ~/Myrk
git pull --ff-only
./install.sh
python3 -m unittest discover -s tests -v
myrk run examples/izhikevich.myrk
```

## Arquitetura e próximos passos

O [ADR 0001](docs/decisions/0001-bootstrap-backend.md) explica a escolha
inicial do backend. O [roadmap](docs/ROADMAP.md) agora prioriza Izhikevich, escala, SIMD, spikes e
sinapses reais antes de tensores gerais e GPU. O [ADR 0002](docs/decisions/0002-snn-populations.md)
define populações na IR, uniformidade, buffers SoA e semântica do solver.
Veja o [plano de milhões de neurônios](docs/MILLION_NEURON_PLAN.md).

Licença: MIT. Consulte [CONTRIBUTING.md](CONTRIBUTING.md) antes de alterar a
linguagem ou otimizar kernels.
