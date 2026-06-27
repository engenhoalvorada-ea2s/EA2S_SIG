# Pendencias de alinhamento com o banco real

Data: 2026-06-22

Nenhum SQL foi executado no banco durante esta revisao. As alteracoes foram feitas apenas em arquivos locais.

## Estrutura real confirmada

A estrutura real do banco `ea2s_sig` foi incorporada aos scripts revisados:

- `projetos.projeto` usa chave primaria `id`.
- `projetos.area_interesse` usa chave primaria `id`; nos scripts, `ai.id AS area_interesse_id`.
- `resultados.execucao` ja existe e nao foi recriada.
- `logs.processamento` usa `id`, `execucao_id`, `projeto_id`, `nivel`, `etapa`, `mensagem`, `detalhe` e `criado_em`.
- `resultados.setores_intersectados` usa `cd_setor`, `area_intersecao_m2`, `area_intersecao_ha`, `area_setor_total_m2`, `percentual_setor_intersectado`, `percentual_area_interesse` e `geom`.
- `resultados.indicador_socioeconomico_detalhe` e `resultados.indicador_socioeconomico_resumo` foram alinhadas aos campos reais confirmados.
- `config.indicadores_mvp` usa `id` e `nome_logico`.
- `metadados.dicionario_indicadores` usa o modelo real com `tabela_banco`, `campo`, `usar_no_mvp` e demais campos confirmados.

## Fontes reais incorporadas

- Malha censitaria: `urbano.setores_censo_2022_malha_br(cd_setor, geom)`, SRID 4674, MULTIPOLYGON, 468.099 setores, com calculos de area em EPSG:31982.
- Tabelas socioeconomicas principais no schema `urbano`, todas com 458.772 registros:
  - `agregados_por_setores_caracteristicas_domicilio1_br`, chave setorial `"CD_setor"`, 458.772 registros;
  - `agregados_por_setores_caracteristicas_domicilio2_br`, chave setorial `setor`, 458.772 registros;
  - `agregados_por_setores_caracteristicas_domicilio3_br`, chave setorial `setor`, 458.772 registros;
  - `agregados_por_setores_renda_responsavel_br`, chave setorial `"CD_SETOR"`, 458.772 registros.
- Camadas fisico-bioticas confirmadas:
  - `geologia.geologia_br_bdia_2025`, SRID 4674;
  - `geomorfologia.geomorfo_br_bdia_2025`, SRID 4674;
  - `hidrogeologia.hidrogeologico_sul_bdia_2025`, SRID 4674;
  - `pedologia.pedo_ordem_ibge_br`, SRID 4674;
  - `vegetacao.vegetacao_br_bdia_2025`, SRID 4674;
  - `hidrografia.microbacias_sigeo_sirhesc_aguassc`, SRID 29192.

## Validacao dos indicadores cadastrados

Resultado confirmado no DBeaver: todos os indicadores cadastrados em `config.indicadores_mvp` apontam para tabelas e colunas reais existentes. A consulta de validacao retornou `ok` para `campo_codigo_setor` e `campo_valor` em todos os indicadores listados.

Chaves setoriais confirmadas nos indicadores:

- `urbano.setores_censo_2022_malha_br`: `cd_setor`
- `urbano.agregados_por_setores_caracteristicas_domicilio1_br`: `CD_setor`
- `urbano.agregados_por_setores_caracteristicas_domicilio2_br`: `setor`
- `urbano.agregados_por_setores_renda_responsavel_br`: `CD_SETOR`

Indicadores inativos confirmados:

- `renda_variancia_moradores_dppo`
- `renda_variancia_rendimento_responsavel`

Esses indicadores devem permanecer inativos por enquanto, pois variancia nao deve ser tratada como soma ponderada simples no MVP.
## Scripts que ainda nao devem ser executados sem revisao

- `sql/03_processar_setores_intersectados.sql`: sincronizado localmente com a assinatura e comportamento real informados, mas nao deve ser executado contra o banco sem autorizacao explicita.
- `sql/04_calcular_indicadores_socioeconomicos.sql`: sincronizado localmente com a assinatura e comportamento real informados, mas nao deve ser executado contra o banco sem autorizacao explicita.
- `sql/05_intersecoes_fisico_biotico.sql`: aprovado em teste controlado com `ROLLBACK`; execucao definitiva depende de autorizacao explicita.
- `sql/07_tabelas_tecnicas_fisico_biotico.sql`: criado localmente como proposta de views tecnicas fisico-bioticas; ainda deve ser revisado e testado em transacao controlada antes de execucao definitiva.
- `sql/08_tabelas_tecnicas_socioeconomico.sql`: criado localmente como proposta de views tecnicas socioeconomicas; ainda deve ser revisado e testado em transacao controlada antes de execucao definitiva.
- `sql/09_consultas_relatorio_integrado.sql`: criado localmente como proposta de views integradas de relatorio; ainda deve ser revisado e testado em transacao controlada antes de execucao definitiva.

## Conferencia final das chaves setoriais

A consulta de conferencia dos 4 setores da execucao execucao_id = 4, projeto_id = 1, area_interesse_id = 1 retornou ok para todas as quatro tabelas socioeconomicas.

## Observacao sobre cobertura socioeconomica

A malha censitaria possui 468.099 setores, enquanto cada tabela socioeconomica confirmada possui 458.772 registros. A funcao socioeconomica real validada usa JOIN com as tabelas de origem e filtra valores nulos ou nao numericos com public.ea2s_safe_numeric(...) IS NOT NULL. Preservar setores sem registro socioeconomico por LEFT JOIN fica registrado apenas como melhoria futura possivel.
## Atributos fisico-bioticos confirmados

Atributos tematicos das camadas ambientais e estrutura da tabela de microbacias foram confirmados e documentados em `docs/camadas_fisico_bioticas.md` e `sql/05_intersecoes_fisico_biotico.sql`.
## Proposta de intersecoes fisico-bioticas

Foi criada proposta local revisada para a tabela resultados.intersecao_fisico_biotica e para a funcao resultados.processar_intersecoes_fisico_bioticas_mvp em sql/05_intersecoes_fisico_biotico.sql. A proposta inclui execucao_id obrigatorio, validacao de p_execucao_id contra resultados.execucao, unidade_analise_codigo, unidade_analise_nome, feicao_origem_id, todas as microbacias interceptadas, buffer_1000m como buffer completo incluindo a area de interesse, calculo em EPSG:31982, arredondamento de areas e percentual, ST_MakeValid, ST_CollectionExtract(..., 3), ST_Multi e DELETE controlado por execucao_id, projeto_id e area_interesse_id. A proposta ainda nao foi executada no banco. O retorno `area_total_registrada_m2` representa soma operacional das areas registradas por tema e unidade de analise, nao area territorial liquida unica.

## Pendencias que permanecem

1. Decidir se melhorias futuras, como `LEFT JOIN` na funcao socioeconomica, serao implementadas em versao posterior.
2. Revisar e testar `sql/07_tabelas_tecnicas_fisico_biotico.sql` em transacao controlada antes de execucao definitiva.
3. Revisar e testar `sql/08_tabelas_tecnicas_socioeconomico.sql` em transacao controlada antes de execucao definitiva.
4. Revisar e testar `sql/09_consultas_relatorio_integrado.sql` em transacao controlada antes de execucao definitiva, conferindo contexto do projeto, tabelas fisico-bioticas por unidade de analise, tabelas socioeconomicas consolidadas, sintese executiva, classes predominantes da area de interesse, numero e nomes das microbacias interceptadas.
5. Testar o orquestrador local com `python src/executar_mvp.py --projeto-id 1 --area-interesse-id 1 --dry-run` e, depois, com execucao real controlada e autorizada.
6. Testar o exportador `src/exportar_resultados_mvp.py` com `--projeto-sig-dir`, conferindo criacao de `resultados_mvp\execucao_<id>` dentro da pasta SIG do projeto e geracao dos arquivos Excel esperados.
7. Testar o gerador `src/gerar_graficos_mvp.py` com `--projeto-sig-dir`, conferindo graficos de area de interesse, buffer de 1000 m, microbacias e setores censitarios.
8. Testar `resultados.vw_socio_contexto_setores` para confirmar uma linha por setor censitario interceptado, usando `valor_original`.
9. Testar `resultados.vw_socio_contexto_setores_total` para confirmar somatorio dos setores, medias simples de renda, renda media ponderada por responsaveis e contadores de setores com dados disponiveis.
10. Testar os campos `possui_dados_basicos`, `possui_dados_dppo`, `possui_dados_renda`, `possui_dados_saneamento` e `status_dados_setor` na view `resultados.vw_socio_contexto_setores`.
11. Testar os campos `responsaveis_dppo_setor`, `responsaveis_dppo_setores` e `renda_media_responsavel_ponderada_responsaveis`.
12. Testar os contadores de setores com dados disponiveis na view `resultados.vw_socio_contexto_setores_total`.
13. Conferir se os filtros das views de populacao, renda e saneamento capturam corretamente os indicadores cadastrados.
14. Conferir se a view `resultados.vw_socio_sintese_geral_area` encontra corretamente os nomes logicos reais dos indicadores e manter seu uso restrito a casos em que a estimativa proporcional por area seja adequada.
15. Decidir futuramente se sera criada uma unidade `entorno_1000m`, excluindo a area de interesse.
16. Definir se a microbacia dominante sera registrada em tabela de resumo ou apenas em texto tecnico.


## Primeira versao funcional validada

A primeira versao funcional do MVP EA2S SIG foi validada com a execucao `6`, para `projeto_id = 1` e `area_interesse_id = 1`. A rodada concluiu o processamento de setores censitarios, indicadores socioeconomicos, intersecoes fisico-bioticas, views integradas de relatorio, exportacao de planilhas e geracao automatica de graficos.

Resultados confirmados:

- setores censitarios intersectados: 4;
- registros fisico-bioticos: 150;
- indicadores socioeconomicos de resumo: 39.

## Pendencias futuras pos-v0.1

- exportacao espacial para GeoPackage;
- geracao automatica de mapas;
- geracao automatica de relatorio DOCX;
- melhoria estetica dos graficos;
- automacao integrada em comando unico para processar, exportar e gerar graficos.
## Seguranca da proposta fisico-biotica

- Nenhuma tabela dos schemas oficiais `geologia`, `geomorfologia`, `hidrogeologia`, `pedologia`, `vegetacao`, `hidrografia` ou `urbano` deve ser alterada.
- O script proposto cria/altera apenas objetos no schema `resultados`.
- O schema `logs` e usado somente para gravacao em `logs.processamento`, tabela ja existente.

## Recomendacoes

- Manter `sql/01_schema_mvp.sql` como documentacao executavel minima, sem recriar tabelas ja existentes.
- Preservar os schemas oficiais `urbano`, `geologia`, `geomorfologia`, `pedologia`, `vegetacao`, `hidrografia`, `hidrogeologia` e `topografia`.
- Executar qualquer validacao futura primeiro no DBeaver, de forma manual e autorizada.
## Views tecnicas fisico-bioticas

O script `sql/07_tabelas_tecnicas_fisico_biotico.sql` foi criado localmente para propor views tecnicas de saida a partir de `resultados.intersecao_fisico_biotica`. As views tematicas mantem `unidade_analise`, `unidade_analise_codigo` e `unidade_analise_nome`, permitindo consultas para `area_interesse`, `buffer_1000m` e `microbacia`.

Hidrogeologia nao deve ser confundida com hidrologia superficial. Cursos d'agua e drenagem serao tratados em modulo posterior com camadas de hidrografia.








