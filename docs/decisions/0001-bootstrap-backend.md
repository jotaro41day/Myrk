# ADR 0001 — Backend inicial e fronteira da IR

Status: aceito para 0.1.0; revisitar após os baselines de LIF e tensor.

## Contexto

O brainstorm identifica uma oportunidade real em manter informações como
topologia, shape, estado, atividade e layout até a seleção do algoritmo. Ele
também propõe muitas IRs e MLIR. Implementar todas antes de medir elevaria o
custo do compilador, especialmente no Termux. AresY é referência de pesquisa
([repositório original](https://github.com/Jotaroofdioinbrando/AresY)); Myrk
não copia seu código nem é um fork.

## Opções

1. AST → LLVM diretamente: executável cedo, mas intenção de domínio perdida.
2. Dialeto MLIR e LLVM: infraestrutura poderosa, distribuição mais pesada e
   custo inicial alto no Termux.
3. IR tipada pequena → C11 → Clang/GCC: executável cedo, ferramentas disponíveis
   no Termux, testes simples; transformações sofisticadas ficam limitadas.
4. C++ gerado: ecossistema amplo, porém build e ABI mais complexos que C11.

## Decisão

Usar frontend Python sem dependências externas, uma IR tipada própria e C11
como backend temporário. A IR é separada da AST e o codegen recebe apenas a IR.
Não criar uma IR neural vazia. Quando houver LIF real, a IR deve preservar o
modelo e estado até uma escolha medida de estratégia; não baixar imediatamente
para laços. Clang ou GCC produz o executável nativo com modo numérico conservador.

## Consequências

- Instalação simples e compilação AOT em Linux e potencialmente Termux.
- Python é requerido para compilar, não para executar o binário gerado.
- C11 não é um backend definitivo para transforms vetoriais, tensor fusion e
  SNN em escala. Comparar código/tempo de engenharia com MLIR/LLVM após M5.
- Guardar testes semânticos independentes do backend para permitir substituição.
- Nenhuma otimização de domínio é alegada nesta etapa.

## Evidência e revisão

O brainstorm fornecido analisou AresY e literatura, mas não mediu AresY em
hardware comparável. Myrk 0.1.0 mede somente um baseline escalar equivalente
ao C. A decisão será revista com dados de compile time, correção e throughput
de LIF, SAXPY e tensor no AArch64 e x86-64. A busca pública inicial por
`myrk in:name` no GitHub encontrou usos genéricos, sem conflito óbvio com uma
linguagem consolidada; isso não é uma análise de marcas.
