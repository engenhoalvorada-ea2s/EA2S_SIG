# Convencoes de banco e PostGIS

## Objetivo

Registrar convencoes para scripts, schemas, views, funcoes e operacoes espaciais do EA2S SIG.

## Schemas

### Operacionais

- `config`: parametros, catalogos e camadas de analise.
- `importacao`: inventario e controle de entrada de bases.
- `staging`: area avancada e temporaria, usada apenas quando necessario.
- `projetos`: projetos, areas de interesse, planos e matrizes.
- `resultados`: resultados processados, views tecnicas e produtos.
- `logs`: logs de processamento.
- `metadados`: dicionarios e documentacao estruturada.

### Oficiais ou referencia

- `urbano`
- `geologia`
- `geomorfologia`
- `hidrogeologia`
- `pedologia`
- `vegetacao`
- `hidrografia`
- `topografia`

Esses schemas nao devem ser alterados sem confirmacao explicita.

## Nomes

- Tabelas e views em minusculas, com `_`.
- Funcoes com prefixo descritivo e schema explicito.
- Views de saida tecnica podem usar prefixo `vw_`.
- Evitar nomes genericos como `teste`, `upload`, `camada` ou `area_interesse` para bases oficiais.

## SQL seguro

- Usar `CREATE SCHEMA IF NOT EXISTS`.
- Usar `CREATE TABLE IF NOT EXISTS` quando aplicavel.
- Usar `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` em evolucao incremental.
- Usar `CREATE INDEX IF NOT EXISTS`.
- Usar `DROP VIEW IF EXISTS` apenas para views de apresentacao quando a estrutura mudar.
- Nao usar `DROP TABLE`, `TRUNCATE`, `DELETE` ou `CASCADE` sem autorizacao clara.

## Views

- Evitar `SELECT *`.
- Explicitar colunas.
- Manter campos de identificacao em views de resultado:
  - `execucao_id`
  - `projeto_id`
  - `area_interesse_id`
- Para views existentes com mudanca de nomes ou ordem de colunas, usar `DROP VIEW IF EXISTS` seguido de `CREATE VIEW`, sem `CASCADE`, quando seguro.

## Funcoes

- Preservar assinatura quando validada no banco.
- Preservar ordem dos parametros.
- Usar `RETURNS TABLE` quando a funcao ja seguir esse padrao.
- Registrar inicio, fim e erro em `logs.processamento` quando o fluxo for processual.
- Em erro, registrar `SQLERRM` e `SQLSTATE` quando util.
- Relancar com `RAISE` quando a falha nao deve ser escondida.

## SRID

- Registrar SRID de origem das camadas quando conhecido.
- Usar EPSG:31982 para calculos de area e comprimento no MVP quando aplicavel.
- Nunca calcular area territorial em geometria geografica sem transformacao adequada.

## Geometria

- Padronizar geometrias de saida com:
  - `ST_MakeValid`
  - `ST_CollectionExtract(..., 3)` para poligonos
  - `ST_Multi`
- Descartar geometrias vazias com `ST_IsEmpty`.
- Usar bounding box para otimizar quando possivel.

## Areas e percentuais

- Area em metros quadrados: `area_m2` ou `area_intersecao_m2`.
- Area em hectares: `area_ha` ou `area_intersecao_ha`.
- Percentual da unidade: `percentual_unidade_analise`.
- Diferenciar area territorial liquida de soma operacional de areas registradas por tema.

## Valores nulos e zeros

- `NULL` significa ausente, nao informado ou nao aplicavel.
- `0` significa valor observado igual a zero.
- Nao substituir `NULL` por `0` em indicadores socioeconomicos sem regra tecnica explicita.

## Compatibilidade com estrutura real

Antes de usar colunas nao confirmadas, inspecionar estrutura ou criar camada de compatibilidade. Exemplo de consulta documentada:

```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'config'
  AND table_name = 'camadas_analise'
ORDER BY ordinal_position;
```

Essa consulta deve ser executada apenas quando o usuario autorizar conexao e SQL.