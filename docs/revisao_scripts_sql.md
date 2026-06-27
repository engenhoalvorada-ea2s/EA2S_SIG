# Revisao dos scripts SQL

Data da revisao inicial: 2026-06-22
Data da atualizacao estrutural: 2026-06-22

Escopo: arquivos em `sql/*.sql` do projeto `EA2S_SIG`.

Nenhum SQL foi executado no banco durante esta revisao. Nenhuma migration foi rodada e nenhuma conexao com o banco foi aberta nesta etapa. As alteracoes foram aplicadas apenas em arquivos locais do projeto.

## Situacao apos as alteracoes

Os roteiros/TODOs iniciais foram transformados em scripts organizados para revisao manual no DBeaver. A estrutura agora contempla verificacoes de leitura, DDL idempotente, cadastro idempotente de indicadores, funcoes de processamento, scripts conceituais para etapas futuras e consultas de conferencia sem `SELECT *`.

A ordem dos scripts foi reorganizada para que as intersecoes fisico-bioticas venham antes dos indicadores derivados:

1. `sql/00_verificacoes_banco.sql`
2. `sql/01_schema_mvp.sql`
3. `sql/02_cadastro_indicadores.sql`
4. `sql/03_processar_setores_intersectados.sql`
5. `sql/04_calcular_indicadores_socioeconomicos.sql`
6. `sql/05_intersecoes_fisico_biotico.sql`
7. `sql/06_indicadores_derivados.sql`
8. `sql/99_consultas_conferencia.sql`

## Arquivos alterados

- `sql/00_verificacoes_banco.sql`
- `sql/01_schema_mvp.sql`
- `sql/02_cadastro_indicadores.sql`
- `sql/03_processar_setores_intersectados.sql`
- `sql/04_calcular_indicadores_socioeconomicos.sql`
- `sql/05_intersecoes_fisico_biotico.sql`
- `sql/06_indicadores_derivados.sql`
- `sql/99_consultas_conferencia.sql`
- `README.md`
- `docs/metodologia.md`
- `src/executar_mvp.py`

## Arquivos renomeados

- `sql/05_indicadores_derivados.sql` -> `sql/06_indicadores_derivados.sql`
- `sql/06_intersecoes_fisico_biotico.sql` -> `sql/05_intersecoes_fisico_biotico.sql`

## Principais alteracoes

### `00_verificacoes_banco.sql`

- Mantido apenas com consultas de leitura.
- Inclui checagem da extensao PostGIS.
- Inclui checagem dos schemas esperados.
- Inclui checagem dos objetos operacionais esperados, incluindo `logs.processamento` e `resultados.produto_gerado`.
- Inclui checagem por assinatura exata das funcoes auxiliares e de processamento.

### `01_schema_mvp.sql`

- Convertido em DDL idempotente com `CREATE SCHEMA IF NOT EXISTS` e `CREATE TABLE IF NOT EXISTS`.
- Cria ou substitui as funcoes auxiliares `public.ea2s_normalizar_codigo_setor(text)` e `public.ea2s_safe_numeric(text)`.
- Define tabelas operacionais em `projetos`, `metadados`, `config`, `resultados` e `logs`.
- Inclui chaves primarias, constraints, indices e indices espaciais quando aplicavel.
- Nao inclui `DROP` destrutivo.

### `02_cadastro_indicadores.sql`

- Estruturado com `INSERT ... ON CONFLICT`.
- Mantem indicadores socioeconomicos como provisorios.
- Separa indicadores ativos provisorios, indicadores futuros e indicadores nao recomendados para soma direta.
- Inclui comentarios de revisao tecnica e consultas de conferencia comentadas.

### `03_processar_setores_intersectados.sql`

- Inclui a funcao `resultados.processar_setores_intersectados(bigint,bigint,bigint)`.
- Usa aliases explicitos e parametros nomeados como `p_projeto_id`, `p_area_interesse_id` e `p_execucao_id`.
- Garante transformacao para EPSG:31982 antes dos calculos de area.
- Usa `ON CONFLICT` para reprocessamento idempotente por `execucao_id` e `setor_codigo`.
- Inclui tratamento de erro com registro em `logs.processamento` e relancamento do erro.
- Inclui consultas de conferencia comentadas ao final.

### `04_calcular_indicadores_socioeconomicos.sql`

- Inclui a funcao `resultados.calcular_indicadores_socioeconomicos_mvp(bigint,bigint,bigint)`.
- Troca variaveis genericas por nomes claros, como `v_ind`.
- Usa aliases explicitos.
- Separa o tratamento de indicadores somaveis, medias ponderadas, medianas referenciais e valores referenciais.
- Inclui consultas de conferencia comentadas ao final.

### `05_intersecoes_fisico_biotico.sql`

- Mantido como estrutura conceitual, sem funcao complexa implementada.
- Organiza TODOs para area de interesse, buffer de 1000 m, microbacia, geologia, geomorfologia, hidrogeologia, pedologia e vegetacao.
- Define a saida esperada futura como area em m2, hectares e percentual por atributo.

### `06_indicadores_derivados.sql`

- Mantido como etapa futura, sem calculo implementado.
- Inclui matriz conceitual para densidade populacional, densidade domiciliar, percentuais de agua, lixo e esgotamento, solucoes sanitarias precarias e vulnerabilidade socioambiental.

### `99_consultas_conferencia.sql`

- Remove `SELECT *`.
- Inclui filtros por `execucao_id`, `projeto_id` e `area_interesse_id`.
- Inclui consultas para setores duplicados, percentuais fora de faixa, indicadores sem cadastro, divergencia entre detalhe e resumo e fechamento da area proximo de 100%.

## Pendencias

- Validar no DBeaver os nomes reais das tabelas e colunas de origem, especialmente `urbano.setores_censitarios`, `social.indicadores_setor` e `codigo_setor`.
- Confirmar se `projetos.area_interesse` sera a tabela definitiva para a geometria da area de interesse.
- Revisar tecnicamente a selecao dos indicadores socioeconomicos e os campos IBGE definitivos.
- Confirmar se `CREATE EXTENSION IF NOT EXISTS postgis` deve permanecer no script estrutural ou ser executado separadamente por perfil administrativo.
- Definir a estrutura final dos resultados fisico-bioticos antes de implementar a funcao da etapa 05.
- Definir formulas, pesos, classes e denominadores dos indicadores derivados antes de implementar a etapa 06.
- Revisar placeholders `:id_processamento`, `:id_projeto` e `:id_area_interesse` conforme a ferramenta de execucao usada.
- Validar manualmente no DBeaver as funcoes PL/pgSQL antes de qualquer execucao em banco.

## Proximos passos manuais

1. Abrir `sql/00_verificacoes_banco.sql` no DBeaver e executar apenas se houver autorizacao para consultas de leitura.
2. Conferir os nomes reais de tabelas, chaves e colunas de geometria dos schemas de origem.
3. Revisar `sql/01_schema_mvp.sql` com foco em permissao para `CREATE EXTENSION`, tipos geometry e constraints.
4. Revisar o cadastro provisorio em `sql/02_cadastro_indicadores.sql` contra os campos reais do IBGE.
5. Ajustar as premissas de `sql/03_processar_setores_intersectados.sql` e `sql/04_calcular_indicadores_socioeconomicos.sql` antes de qualquer execucao.
