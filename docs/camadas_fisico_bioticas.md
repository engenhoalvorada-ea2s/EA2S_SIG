# Camadas fisico-bioticas

Data de atualizacao: 2026-06-22

Nenhum SQL foi executado durante esta atualizacao. As informacoes abaixo registram campos confirmados para orientar a futura funcao de intersecoes fisico-bioticas.

## Geologia

- Tabela: `geologia.geologia_br_bdia_2025`
- Geometria: `geom`
- SRID: 4674
- Campo principal: `nm_unidade`
- Campos complementares: `letra_simb`, `nm_lito1`, `nm_lito2`, `nm_lito3`, `nm_lito4`, `nm_tempo_g`, `nm_provinc`, `nm_sub_pro`

## Geomorfologia

- Tabela: `geomorfologia.geomorfo_br_bdia_2025`
- Geometria: `geom`
- SRID: 4674
- Campo principal recomendado: `legenda`
- Campos complementares: `nm_dominio`, `nm_regiao`, `nm_unidade`, `categoria`, `natureza`, `forma`, `dens_dren`, `aprof_inci`, `niv_alt`, `compartime`

## Hidrogeologia

- Tabela: `hidrogeologia.hidrogeologico_sul_bdia_2025`
- Geometria: `geom`
- SRID: 4674
- Campo principal: `nome_unida`
- Campos complementares: `cd_legenda`, `litologia`, `provincia`, `dominio`, `vz_cl`, `vze_cl`, `vz_int_cl`, `vze_int_cl`, `"domínio_da"`

## Pedologia

- Tabela: `pedologia.pedo_ordem_ibge_br`
- Geometria: `geom`
- SRID: 4674
- Campo principal: `legenda`
- Campo complementar: `area_km`

## Vegetacao

- Tabela: `vegetacao.vegetacao_br_bdia_2025`
- Geometria: `geom`
- SRID: 4674
- Campo principal: `legenda`
- Campos complementares: `cd_fito`, `cd_leg_2`, `clas_domi`, `nm_uveg`, `nm_uantr`, `nm_contat`, `nm_pretet`, `legenda_1`, `legenda_2`

## Microbacias

- Tabela: `hidrografia.microbacias_sigeo_sirhesc_aguassc`
- Geometria: `geom`
- SRID: 29192
- Campo identificador: `cd_micro`
- Campo principal: `nm_micro`
- Campos complementares: `nm_rio_pri`, `cd_otto_1`, `cd_otto_2`, `cd_otto_3`, `cd_otto_4`, `cd_otto_5`, `cd_otto_6`, `cd_otto_7`, `cd_bacia`, `cd_ibge_mu`, `sg_tipo`, `vl_qmin7`, `nm_qmin7`, `vl_qrest`, `vl_qsubt`, `shape_area`, `shape_len`

## Regras metodologicas

- Transformar geometrias para EPSG:31982 antes de calcular areas.
- Reportar areas em m2 e hectares.
- Reportar percentual em relacao ao recorte usado: area direta, buffer de 1000 m ou microbacia, com arredondamento e limitacao final entre 0 e 100 para reduzir ruido de precisao numerica.
- Nao alterar dados oficiais dos schemas ambientais.
- A funcao/tabela de resultado das intersecoes fisico-bioticas foi proposta localmente em `sql/05_intersecoes_fisico_biotico.sql`, ainda sem execucao no banco.
## Tabela de resultado proposta

A tabela proposta para consolidar as intersecoes e `resultados.intersecao_fisico_biotica`, definida localmente em `sql/05_intersecoes_fisico_biotico.sql` para revisao antes de qualquer execucao.

Campos principais:

- `id bigserial primary key`
- `execucao_id bigint not null`
- `projeto_id bigint not null`
- `area_interesse_id bigint not null`
- `unidade_analise text not null`
- `unidade_analise_codigo text`
- `unidade_analise_nome text`
- `tema text not null`
- `camada_origem text not null`
- `feicao_origem_id text`
- `campo_principal text`
- `valor_principal text`
- `atributos_complementares jsonb`
- `area_intersecao_m2 numeric`
- `area_intersecao_ha numeric`
- `area_unidade_analise_m2 numeric`
- `percentual_unidade_analise numeric`
- `geom geometry(MultiPolygon, 31982)`
- `data_cadastro timestamp default now()`

Valores previstos para `unidade_analise`: `area_interesse`, `buffer_1000m`, `microbacia`.

Nesta versao MVP, `buffer_1000m` representa o buffer completo de 1000 m ao redor da area de interesse, incluindo a propria area. A criacao de uma unidade futura `entorno_1000m`, excluindo a area de interesse, fica registrada como melhoria possivel.

Para microbacias, a funcao deve considerar todas as microbacias interceptadas pela area de interesse. A microbacia dominante podera ser indicada posteriormente em tabela de resumo ou texto tecnico.

Valores previstos para `tema`: `geologia`, `geomorfologia`, `hidrogeologia`, `pedologia`, `vegetacao`.

## Funcao proposta

A funcao proposta e `resultados.processar_intersecoes_fisico_bioticas_mvp(p_execucao_id bigint, p_projeto_id bigint, p_area_interesse_id bigint)`.

Ela devera:

1. Buscar a area de interesse em `projetos.area_interesse`.
2. Criar as unidades de analise `area_interesse`, `buffer_1000m` e `microbacia`.
3. Transformar geometrias para EPSG:31982.
4. Intersectar cada unidade de analise com as camadas ambientais confirmadas.
5. Gravar area em m2, hectares e percentual da unidade de analise.
6. Guardar atributos complementares em `jsonb`.

O retorno `area_total_registrada_m2` soma as areas registradas de todos os temas e unidades de analise. Esse valor e uma soma operacional de registros, nao uma area territorial liquida unica.

Status: proposta local, ainda nao executada no banco.
## Seguranca da proposta

- A proposta nao altera tabelas dos schemas oficiais `geologia`, `geomorfologia`, `hidrogeologia`, `pedologia`, `vegetacao`, `hidrografia` ou `urbano`.
- O script cria/altera apenas objetos no schema `resultados`.
- O schema `logs` e usado somente para gravacao em `logs.processamento`, tabela ja existente.
- A funcao proposta usa EPSG:31982 para calculo de area.
- A funcao proposta usa `ST_MakeValid`, `ST_CollectionExtract(..., 3)` e `ST_Multi` para garantir saida `MultiPolygon`.
- O `DELETE` e controlado por `execucao_id`, `projeto_id` e `area_interesse_id`.
## Tabelas tecnicas propostas

O arquivo `sql/07_tabelas_tecnicas_fisico_biotico.sql` foi criado localmente como proposta inicial de views tecnicas a partir de `resultados.intersecao_fisico_biotica`.

Views propostas:

- `resultados.vw_fisico_biotico_sintese_unidade_tema`: sintese por unidade de analise e tema.
- `resultados.vw_fisico_biotico_classes`: classes tematicas consolidadas.
- `resultados.vw_tabela_geologia`: tabela tecnica de geologia.
- `resultados.vw_tabela_geomorfologia`: tabela tecnica de geomorfologia.
- `resultados.vw_tabela_hidrogeologia`: tabela tecnica de hidrogeologia.
- `resultados.vw_tabela_pedologia`: tabela tecnica de pedologia.
- `resultados.vw_tabela_vegetacao`: tabela tecnica de vegetacao.
- `resultados.vw_tabela_microbacias_fisico_biotico`: resumo das microbacias analisadas.

Todas as views tematicas mantem `unidade_analise`, `unidade_analise_codigo` e `unidade_analise_nome`, permitindo consulta separada para `area_interesse`, `buffer_1000m` e `microbacia`.

A view de hidrogeologia trata unidades hidrogeologicas. Hidrologia superficial, cursos d'agua e drenagem devem ser tratados em modulo posterior com camadas de hidrografia.

Proxima etapa: revisar e testar `sql/07_tabelas_tecnicas_fisico_biotico.sql` em transacao controlada antes de qualquer execucao definitiva.
