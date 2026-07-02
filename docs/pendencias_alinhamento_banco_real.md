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
- Camadas de hidrografia ANA identificadas:
  - `hidrografia."bh6_curso_dagua_ANA_2022"`, tabela principal linear da ANA, SRID 4674, MULTILINESTRING, campo geometrico `geom`;
  - `hidrografia.microbacias_sigeo_sirhesc_aguassc`, tabela de microbacias, SRID 29192, MULTIPOLYGON, campo geometrico `geom`.

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
- `sql/10_hidrografia_ana.sql`: criado localmente como proposta do modulo de hidrografia ANA; usa a tabela real `hidrografia."bh6_curso_dagua_ANA_2022"` e os campos reais identificados, mas ainda deve ser revisado e testado em transacao controlada antes de execucao definitiva.

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

- testar novamente o exportador espacial `src/exportar_gpkg_mvp.py` apos reaplicar o SQL 05 atualizado, rodar nova execucao do MVP e gerar GPKG enriquecido com atributos originais;
- gerar projeto QGIS `.qgz` com grupos de camadas e simbologia;
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









## Exportacao GeoPackage do MVP

O script `src/exportar_gpkg_mvp.py` foi criado localmente para exportar camadas espaciais do MVP para um arquivo GeoPackage em:

```text
<projeto-sig-dir>\resultados_mvp\execucao_<execucao_id>\gpkg\ea2s_sig_execucao_<execucao_id>.gpkg
```

A primeira exportacao GeoPackage funcionou e gerou arquivo `.gpkg`. A pendencia foi resolvida parcialmente: o exportador existe e ja produziu saida, mas a organizacao das camadas foi revisada para melhorar a leitura no QGIS.

Melhoria implementada localmente em `src/exportar_gpkg_mvp.py`:

- a camada `area_interesse` deixou de ser exportada por padrao, pois a area de interesse e o poligono original de entrada do projeto;
- foram mantidas as camadas de referencia `buffer_1000m`, `microbacias_interceptadas` e `setores_censitarios_intersectados`;
- a camada socioeconomica `setores_censitarios_intersectados` passa a buscar o limite completo dos setores na malha oficial e atributos em `resultados.vw_relatorio_socio_contexto_setores`;
- as intersecoes fisico-bioticas passam a ser exportadas em camadas separadas por unidade de analise e tema;
- a camada unica `auditoria_fb_intersecoes_todas` fica disponivel apenas com o argumento opcional `--incluir-auditoria`.

Camadas previstas para nova conferencia:

- `buffer_1000m`;
- `microbacias_interceptadas`;
- `setores_censitarios_intersectados`;
- `setores_censitarios_area_intersectada`;
- camadas ambientais por tema para `area_interesse`, `buffer_1000m` e `microbacias`.

Pendencia futura: gerar projeto QGIS `.qgz` com grupos de camadas, ordem de desenho e simbologia padronizada.
## Atributos originais nas intersecoes fisico-bioticas

Melhoria planejada e implementada localmente nos arquivos:

- `sql/05_intersecoes_fisico_biotico.sql`;
- `src/exportar_gpkg_mvp.py`;
- `README.md`.

O script 05 passa a propor os campos `fonte_schema`, `fonte_tabela`, `fonte_camada` e `atributos_origem` em `resultados.intersecao_fisico_biotica`. A funcao de processamento passa a preencher `atributos_origem` com `to_jsonb(...) - 'geom' - 'geometry'`, preservando os atributos originais das feicoes oficiais de geologia, geomorfologia, hidrogeologia, pedologia e vegetacao sem alterar as bases oficiais.

O exportador GeoPackage passa a descobrir as chaves de `atributos_origem` por unidade de analise e tema, sanitizar nomes de colunas e exportar esses atributos junto com area, percentual, `valor_principal` e `atributos_origem_json`.

Pendencias operacionais:

1. Reaplicar o SQL atualizado de `sql/05_intersecoes_fisico_biotico.sql` no banco, somente com autorizacao explicita.
2. Rodar nova execucao do MVP para gravar os novos campos em `resultados.intersecao_fisico_biotica`.
3. Exportar novo GeoPackage a partir da nova execucao.
4. Conferir no QGIS se as camadas ambientais contem os atributos originais esperados e o campo `atributos_origem_json`.

## Modulo de hidrografia ANA

Foi criado localmente o primeiro modulo de hidrografia ANA do MVP EA2S SIG:

- `sql/10_hidrografia_ana.sql`;
- ajuste opcional em `src/executar_mvp.py` com `--incluir-hidrografia`;
- ajuste opcional em `src/exportar_gpkg_mvp.py` com `--incluir-hidrografia`;
- documentacao no `README.md`.

A hidrografia foi mantida separada de `resultados.intersecao_fisico_biotica`, pois a metrica principal e comprimento linear, nao area. A tabela proposta e `resultados.intersecao_hidrografia`, com geometria `MultiLineString` em EPSG:31982 e atributos originais preservados em `atributos_origem`.

Tabelas e campos reais identificados para o modulo:

- `hidrografia."bh6_curso_dagua_ANA_2022"`: tabela principal linear da ANA, SRID 4674, MULTILINESTRING, `geom`;
- campos ANA existentes: `id`, `geom`, `fid`, `wtc_pk`, `idcda`, `cocursodag`, `nudistbacc`, `nucompcda`, `nuareabacc`, `cocdadesag`, `nunivotcda`, `nuordemcda`, `dedominial`, `dsversao`;
- `hidrografia.microbacias_sigeo_sirhesc_aguassc`: tabela de microbacias, SRID 29192, MULTIPOLYGON, `geom`;
- campos de microbacias existentes: `id`, `geom`, `cd_micro`, `nm_micro`, `nm_rio_pri`, `cd_otto_1`, `cd_otto_2`, `cd_otto_3`, `cd_otto_4`, `cd_otto_5`, `cd_otto_6`, `cd_otto_7`, `cd_bacia`, `cd_ibge_mu`, `cd_trecho`, `sg_tipo`, `cd_qmin7`, `vl_qmin7`, `nm_qmin7`, `vl_qrest`, `vl_qsubt`, `shape_area`, `shape_len`.

A tabela ANA nao possui campo explicito de nome do rio ou curso d'agua. Portanto, `nome_curso` permanece nulo nesta versao. Os campos `codigo_trecho` e `codigo_curso` usam, respectivamente, `idcda` e `cocursodag`.

Pendencias operacionais:

1. Aplicar `sql/10_hidrografia_ana.sql` no banco somente com autorizacao explicita.
2. Rodar nova execucao com `--incluir-hidrografia`.
3. Validar as views `resultados.vw_hidrografia_area_interesse`, `resultados.vw_hidrografia_buffer_1000m`, `resultados.vw_hidrografia_microbacias` e `resultados.vw_hidrografia_resumo`.
4. Exportar novo GeoPackage com `--incluir-hidrografia`.
5. Validar no GPKG as camadas `hidrografia_area_interesse`, `hidrografia_buffer_1000m` e `hidrografia_microbacias`.

## Interface Streamlit inicial

Foi criada e ajustada localmente a primeira versão da interface Streamlit do MVP EA2S SIG em `src/app_streamlit.py`.

Melhorias de usabilidade aplicadas:

- seleção de projeto e área gravada em `st.session_state`;
- preenchimento automático de projeto e área na página de execução;
- usuário padrão `Paulo`;
- seleção amigável de execuções recentes por projeto/área;
- persistência local de `projeto_sig_dir` para comandos de exportação;
- parâmetros do diagnóstico consolidados em `st.session_state["parametros_diagnostico"]`;
- comandos PowerShell montados sem execução automática;
- avisos específicos para exportações e para ambiente QGIS/GDAL no GPKG.

Pendências futuras da interface:

1. Integrar execução segura via botão, com confirmação explícita, logs e tratamento de erros.
2. Persistir `pasta_sig` no cadastro do projeto, evitando digitação manual recorrente.
3. Implementar diagnóstico seletivo real por camada, além da montagem de parâmetros na interface.
4. Criar cadastro de projetos via formulário.
5. Criar cadastro de áreas e camadas de análise.
6. Implementar upload/importação de camadas, possivelmente com GeoPandas.
7. Implementar visualização cartográfica interativa.
8. Validar a interface em ambiente local com Streamlit após autorização para execução do app.
