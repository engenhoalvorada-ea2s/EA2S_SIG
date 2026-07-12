# Arquitetura EA2S SIG

## Visao geral

O EA2S SIG e um WebGIS socioambiental para diagnostico territorial. A arquitetura combina interface Streamlit, banco PostgreSQL/PostGIS, scripts SQL versionados e rotinas Python para importacao, analise, exportacao e visualizacao.

## Componentes principais

### Interface

A interface Streamlit concentra os fluxos operacionais:

- inicio e status do sistema;
- cadastro/inicio de projeto;
- upload e validacao de area de interesse;
- banco de dados geograficos;
- composicao de diagnostico;
- dashboards e mapas;
- exportacoes.

### Banco PostGIS

O banco organiza dados em schemas operacionais e schemas oficiais. Os schemas operacionais guardam configuracoes, logs, projetos, importacoes e resultados. Os schemas oficiais guardam bases tecnicas de referencia.

### SQL versionado

Scripts SQL ficam em `sql/` e devem ser revisaveis, idempotentes quando possivel e documentados. Funcoes ja validadas no banco devem preservar assinatura, ordem de parametros e logica confirmada.

### Python

Rotinas Python fazem orquestracao, exportacao, leitura de arquivos geograficos, graficos, interface e funcoes auxiliares. Codigo novo deve ser pequeno, comentado em portugues e facil de testar.

## Fluxo principal de dados

1. O usuario envia ou identifica uma base geografica.
2. O sistema inventaria metadados, hash, atributos, CRS e geometria.
3. A base passa por validacao e correcao, quando necessario.
4. A importacao oficial e feita de forma controlada.
5. A camada e cadastrada em `config.camadas_analise`.
6. O usuario monta um plano de diagnostico.
7. O sistema gera matriz de cruzamentos.
8. Diagnosticos exploratorios ou oficiais sao executados mediante autorizacao.
9. Resultados sao disponibilizados em views, mapas, planilhas, GeoPackage e relatorios.

## Staging

O staging existe como recurso avancado para cenarios especificos. O fluxo principal atual privilegia inventario, validacao/correcao e importacao oficial controlada.

## Camadas oficiais

Schemas oficiais nao devem ser alterados sem confirmacao explicita:

- `urbano`
- `geologia`
- `geomorfologia`
- `hidrogeologia`
- `pedologia`
- `vegetacao`
- `hidrografia`
- `topografia`

## Camadas operacionais

Schemas operacionais concentram objetos do sistema:

- `config`
- `importacao`
- `staging`
- `projetos`
- `resultados`
- `logs`
- `metadados`

## Principio de compatibilidade

Quando uma tabela real pode ter nomes de colunas diferentes dos esperados pela aplicacao, criar uma camada de compatibilidade. A interface e os modulos internos devem trabalhar com nomes padronizados, sem obrigar alteracao destrutiva da tabela real.