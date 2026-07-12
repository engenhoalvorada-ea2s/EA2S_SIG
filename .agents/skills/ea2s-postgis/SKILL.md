# Skill: ea2s-postgis

Use esta skill quando a tarefa envolver geometrias, PostGIS, SRID, area, comprimento, intersecoes ou exportacao espacial.

## Objetivo

Garantir processamento espacial coerente, reprodutivel e seguro para diagnostico socioambiental.

## Regras obrigatorias

- Nao execute SQL espacial sem autorizacao explicita.
- Nao altere camadas oficiais sem confirmacao explicita.
- Preserve atributos originais sempre que possivel.
- Documente SRID de origem e SRID de calculo.

## SRID e calculos

- Para area e comprimento no MVP, preferir EPSG:31982 quando aplicavel ao territorio analisado.
- Transformar geometrias antes de calcular area ou comprimento.
- Registrar SRID de origem quando conhecido.
- Nao misturar area em graus com area em metros.

## Geometrias validas

Quando gerar geometrias de saida, considerar:

- `ST_MakeValid`
- `ST_CollectionExtract(..., 3)` para poligonos
- `ST_Multi` para padronizar `MULTIPOLYGON`
- `ST_IsEmpty` para descartar geometrias vazias

## Intersecoes

- Usar filtro espacial por bounding box quando possivel: `a.geom && b.geom`.
- Calcular intersecoes em SRID projetado quando a medida for area.
- Arredondar areas e percentuais em views ou saidas tecnicas quando isso reduzir ruido numerico.
- Diferenciar soma operacional de area registrada de area territorial liquida.

## Atributos

- Guardar atributos complementares em `jsonb` quando a estrutura de cada camada variar.
- Nao descartar identificador da feicao original; usar campo como `feicao_origem_id` quando aplicavel.
- Nao preencher valores ausentes nas camadas oficiais; tratar apenas na apresentacao, por exemplo com `COALESCE(NULLIF(...), 'Sem classificacao informada')` em views.

## Saidas

- Tabelas de resultado devem ficar em `resultados`.
- Views tecnicas podem ficar em `resultados`.
- Schemas oficiais como `geologia`, `geomorfologia`, `hidrogeologia`, `pedologia`, `vegetacao`, `hidrografia`, `urbano` e `topografia` nao devem ser modificados sem autorizacao explicita.