# Skill: ea2s-diagnostico

Use esta skill quando a tarefa envolver plano de diagnostico, limites, camadas selecionadas, matriz de cruzamentos ou diagnostico exploratorio/oficial.

## Objetivo

Organizar a selecao de camadas e cruzamentos territoriais de forma rastreavel, evitando suposicoes sobre estrutura do banco.

## Fluxo de diagnostico

1. Selecionar projeto e area de interesse.
2. Confirmar limite territorial.
3. Selecionar camadas de analise cadastradas.
4. Criar plano de diagnostico.
5. Gerar matriz de cruzamentos.
6. Executar diagnostico exploratorio quando autorizado.
7. Executar diagnostico oficial quando validado.
8. Exportar tabelas, mapas e relatorios.

## Camadas de analise

- Ler camadas a partir de `config.camadas_analise` ou view de compatibilidade.
- Nao assumir que existem colunas reais chamadas `schema_origem` e `tabela_origem`.
- Usar DataFrame normalizado com campos internos:
  - `camada_analise_id`
  - `grupo`
  - `tema`
  - `subtema`
  - `schema_origem`
  - `tabela_origem`
  - `coluna_geom`
  - `srid`
  - `ativo`

## Plano de diagnostico

- Guardar selecao do usuario em tabelas de projeto, nao em schemas oficiais.
- Diferenciar diagnostico exploratorio de diagnostico oficial.
- Preservar historico e status do plano.
- Evitar recriar ou apagar planos sem pedido.

## Matriz de cruzamentos

- A matriz deve indicar quais camadas entram em cada cruzamento.
- Usar identificadores de projeto, area de interesse e plano.
- Registrar limites, camadas e status.
- Nao executar cruzamentos espaciais sem autorizacao quando o pedido for apenas desenho ou edicao local.

## Saidas

- Resultados oficiais devem ser gravados em `resultados` ou schemas operacionais adequados.
- Relatorios e exportacoes devem ficar na pasta SIG especifica do projeto, quando o usuario informar.