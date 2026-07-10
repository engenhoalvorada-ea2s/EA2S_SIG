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
- `sql/11_config_camadas_analise.sql`: criado localmente como proposta de cadastro configuravel de camadas e perfis de diagnostico; ainda deve ser aplicado e testado manualmente no banco com autorizacao explicita.
- `sql/15_perfil_atributos_inventario.sql`: recriado localmente como proposta de perfilamento de atributos no schema `importacao`; ainda deve ser aplicado e testado manualmente com autorizacao explicita.
- `sql/16_importacao_staging.sql`: criado localmente para o fluxo avancado Inventario -> Staging; ainda deve ser aplicado e testado manualmente com autorizacao explicita antes de usar a aba `Staging avancado`.
- `sql/18_importacao_direta_schema_oficial.sql`: criado localmente para o fluxo principal de importacao direta para schema oficial; ainda deve ser aplicado e testado manualmente com autorizacao explicita antes de usar a aba `Importar para base oficial`.

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


## Inventario e validacao de bases geograficas

Foi criado localmente o primeiro modulo funcional de inventario e validacao de bases geograficas do EA2S SIG:

- `sql/13_inventario_bases_geograficas.sql`;
- `sql/14_inventario_hash_deduplicacao.sql`;
- `sql/15_perfil_atributos_inventario.sql`;
- aba `Inventariar nova base` em `src/app_streamlit.py`;
- documentacao no `README.md`.

A proposta cria objetos apenas no schema operacional `importacao`:

- `importacao.lote_importacao`;
- `importacao.inventario_arquivo`;
- `importacao.vw_inventario_bases_geograficas`.

Objetos adicionados pelo SQL 15 de perfilamento de atributos:

- `importacao.perfil_atributo`;
- `importacao.regra_conversao_atributo`;
- `importacao.vw_perfil_atributos_inventario`.


O modulo permite entrada por upload, caminho local/rede ou URL pendente. Upload aceita GPKG, GeoJSON, JSON e shapefile zipado; caminho local/rede tambem permite `.shp` direto. O fluxo inclui leitura tecnica por GeoPandas/Fiona, validacao de CRS, geometria, bbox, feicoes, campos e tipos geometricos, resumo estatistico, perfilamento de atributos, Explorador Grafico com Plotly, hash SHA256 do arquivo original quando houver arquivo local, verificacao de duplicidade e registro de metadados de inventario. O fluxo nao importa dados para schemas oficiais e nao promove automaticamente camadas para `config.camadas_analise`.


Correcoes locais do modulo 15:

- Corrigido erro de assinatura no grafico exploratorio com `perfil_df`;
- Ajustada inferencia de data para nao converter numeros/codigos puros em datas de 1970;
- Ajustada inferencia de booleano para nao tratar campos `cd_*`, `cod*`, `id`, `mslink`, setor, quadra ou lote como booleanos apenas por terem valores 0/1;
- Campos `id`, `mslink`, `cd_*`, `cod*`, `fid`, `gid`, `objectid`, setor, quadra, lote, inscricao e matricula passam a priorizar `codigo`.
- Melhorada a selecao de eixos do Explorador Grafico, com modo recomendado e modo avancado;
- Incluidos campos opcionais de cor/agrupamento, rotulo, hover, tamanho e facet/coluna de separacao;
- Graficos de barra, pizza, treemap e sunburst passam a poder usar contagem automatica quando nao houver coluna numerica de valor.
- Corrigida regra que impedia registrar inventario com geometria invalida;
- Corrigida consulta de inventarios recentes para nao depender de coluna criado_em inexistente na view;
- Criado ajuste complementar local sql/16_ajuste_view_inventario_criado_em.sql para padronizar datas da view de inventario.
- Corrigida logica do botao Registrar inventario;
- Removido bloqueio causado por checkbox dentro de st.form;
- Validacao do registro passa a ocorrer apos o clique no botao;
- Geometria invalida continua permitindo inventario; no fluxo principal, deve gerar correcao opcional ou importacao com pendencias quando nao houver bloqueio critico.

Pendencias especificas:

1. Aplicar `sql/13_inventario_bases_geograficas.sql` no banco somente com autorizacao explicita.
2. Aplicar `sql/14_inventario_hash_deduplicacao.sql` no banco somente com autorizacao explicita.
3. Testar deduplicacao por hash, confirmando bloqueio do registro normal e liberacao apenas com `Registrar mesmo assim como novo inventário`.
4. Testar o inventario com arquivo GPKG.
5. Testar o inventario com shapefile zipado, incluindo casos com e sem `.prj`.
6. Testar o inventario com GeoJSON.
7. Testar o Explorador Grafico com barras, linhas, dispersao, histograma, box plot, violino, area, heatmap, treemap, sunburst e pizza opcional.
8. Aplicar `sql/18_importacao_direta_schema_oficial.sql` no banco somente com autorizacao explicita e testar a importacao direta para schema oficial.
9. Aplicar `sql/16_importacao_staging.sql` apenas se o recurso avancado de staging for necessario.
10. Testar cadastro opcional em `config.camadas_analise` somente para bases validas ou explicitamente aprovadas.
11. Avaliar se registros duplicados de teste devem ser marcados como `arquivado`, sem apagar dados.
12. Implementar controle de usuarios, login e trilha de auditoria para fluxos de importacao e promocao.
13. Aplicar `sql/15_perfil_atributos_inventario.sql` no banco somente com autorizacao explicita.
14. Testar com base de zoneamento PMF, conferindo campos categóricos, textos e codigos.
15. Testar campos monetarios, percentuais e datas, incluindo valores em texto como `R$`, `%`, `DD/MM/YYYY`, `MM/YYYY` e `YYYY`.
16. Testar salvamento do perfil confirmado em `importacao.perfil_atributo` junto com o inventario.
17. Testar o Explorador Grafico usando o dataframe convertido pelo perfil confirmado.
18. Usar o perfil confirmado na importacao direta para schema oficial e, quando necessario, no staging avancado.
19. Usar o perfil confirmado futuramente nas exportacoes.
20. Testar novamente com altimetria PMF (`alt_cn.shp`), conferindo `id`, `mslink`, `cd_*`, `nm_elevaca`, `cd_classe` e `dt_cadastr`.
21. Testar com PGV para campos monetarios, codigos numericos longos e graficos com cor/hover/rotulo.
22. Testar o Explorador Grafico com bases de zoneamento, validando campos de zona, uso, classe e descricao como rotulo/hover.
23. Testar novamente com altimetria PMF (`alt_cn.shp`) em modo recomendado e avancado, especialmente graficos de dispersao com X/Y diferentes.
24. Usar o perfil confirmado na importacao direta para schema oficial, sem inferir novamente tipos sensiveis.
25. Testar correcao opcional de geometrias invalidas antes da importacao oficial ou registro como pendencia tecnica.

## Fluxo simplificado de importacao oficial

Foi criada localmente a primeira versao do fluxo principal Inventario -> Importacao direta para schema oficial do EA2S SIG:

- `sql/18_importacao_direta_schema_oficial.sql`;
- `src/importacao_oficial.py`;
- aba `Importar para base oficial` em `src/app_streamlit.py`;
- atualizacao do `README.md`;
- regra em `.gitignore` para `data/importacao/corrigidos/`.

O fluxo principal usa o inventario como etapa obrigatoria de identificacao da base, diagnostico tecnico, perfilamento de atributos, validacao de geometria, tentativa opcional de correcao e definicao de schema/tabela destino. A importacao oficial pode registrar tres situacoes: `valido`, `importado_com_pendencias` e `bloqueado`.

A importacao direta proposta so cria nova tabela no schema oficial indicado. Ela nao apaga, substitui, trunca ou sobrescreve tabelas existentes. O arquivo original permanece preservado em `data/importacao/originais/lote_<lote_id>/inventario_<inventario_arquivo_id>/`. Correcoes opcionais de geometria devem usar memoria ou a pasta `data/importacao/corrigidos/lote_<lote_id>/inventario_<inventario_arquivo_id>/`, sem substituir o arquivo original.

Pendencias especificas da importacao oficial direta:

1. Aplicar `sql/18_importacao_direta_schema_oficial.sql` no banco somente com autorizacao explicita.
2. Testar a aba `Importar para base oficial` apos aplicar o SQL 18.
3. Testar `inventario_arquivo_id = 4` (`zona_azul.zip`), esperando importacao como `valido`, `pode_usar_diagnostico = true` e opcao de cadastro ativo em `config.camadas_analise`.
4. Testar `Zoneamento.zip`, esperando deteccao de geometrias invalidas, oferta de correcao automatica e possibilidade de `importado_com_pendencias` se restarem problemas.
5. Testar tentativa de importacao para tabela oficial ja existente, esperando bloqueio de sobrescrita e sugestao de nome com sufixo `_v2`.
6. Verificar o cadastro opcional em `config.camadas_analise`, sem duplicar camada por mesmo schema/tabela/tema.
7. Verificar se camadas importadas como validas e cadastradas como ativas aparecem em `Compor diagnostico`.
8. Validar que camadas importadas com pendencias nao sejam usadas automaticamente em diagnosticos.

## Fluxo Inventario -> Staging avancado

O fluxo Inventario -> Staging continua preservado como recurso avancado, mas deixou de ser etapa obrigatoria do fluxo principal:

- `sql/16_importacao_staging.sql`;
- `src/importacao_staging.py`;
- aba `Staging avancado` em `src/app_streamlit.py`;
- regras explicitas em `.gitignore` para `data/importacao/originais/` e `data/importacao/staging_temp/`.

O staging pode ser usado para auditoria, investigacao tecnica ou cargas intermediarias. Ele preserva o arquivo original inventariado, cria nome seguro de tabela no schema `staging`, aplica o perfil de atributos confirmado quando existir, reprojeta para EPSG:31982 quando necessario e registra a importacao em `importacao.staging_importacao`.

Pendencias especificas do staging avancado:

1. Aplicar `sql/16_importacao_staging.sql` no banco somente com autorizacao explicita, se o recurso avancado for usado.
2. Testar a aba `Staging avancado` apos aplicar o SQL 16.
3. Conferir a tabela criada em `staging` e o registro em `importacao.staging_importacao`.
4. Manter staging fora do fluxo principal de importacao oficial, salvo decisao tecnica posterior.

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
- avisos específicos para exportações e para ambiente QGIS/GDAL no GPKG;
- comentários didáticos em português no arquivo `src/app_streamlit.py`, sem alteração intencional de lógica, SQL ou comportamento.

Pendências futuras da interface:

1. Integrar execução segura via botão, com confirmação explícita, logs e tratamento de erros.
2. Persistir `pasta_sig` no cadastro do projeto, evitando digitação manual recorrente.
3. Implementar diagnóstico seletivo real por camada, além da montagem de parâmetros na interface.
4. Criar cadastro de projetos via formulário.
5. Criar cadastro de áreas e camadas de análise.
6. Implementar upload/importação de camadas, possivelmente com GeoPandas.
7. Visualização cartográfica inicial com Folium adicionada em src/app_streamlit.py.
8. Validar a interface em ambiente local com Streamlit após autorização para execução do app.
9. Melhorar simbologia cartográfica das camadas no mapa Folium.
10. Permitir seleção de camadas ambientais específicas para visualização.
11. Criar mapa por tema ambiental.
12. Implementar exportação de mapa estático para relatório.
## Mapa Folium na interface

Foi adicionada localmente a visualização cartográfica inicial com Folium/Leaflet na página `Mapa` da interface Streamlit. A página usa apenas consultas `SELECT`, transforma geometrias para EPSG:4326 somente para exibição e preserva o processamento oficial no banco/PostGIS.

Pendências específicas:

1. Testar a página `Mapa` em ambiente local após autorização para executar o app.
2. Melhorar simbologia das camadas.
3. Permitir seleção de camadas ambientais específicas.
4. Criar visualização por tema ambiental.
5. Implementar exportação de mapa estático para relatório.
## Resumo estatístico na interface

Foi adicionada localmente a página `Resumo estatístico` na interface Streamlit. A página usa consultas `SELECT`, pandas para agregações e Plotly para gráficos simples, sem alterar dados ou tabelas.

Pendências específicas:

1. Testar a página em ambiente local após autorização para executar o app.
2. Integrar base etária e sexo do Censo para pirâmide etária e estrutura por sexo.
3. Avaliar cálculo físico-biótico por setor censitário, se necessário.
4. Avaliar hidrografia por setor censitário, se necessário.
5. Permitir comparação entre múltiplos limites no mesmo gráfico.

## Cadastro configuravel de camadas de analise

Foi criado localmente o script `sql/11_config_camadas_analise.sql` com a primeira versao do cadastro configuravel de camadas do EA2S SIG. A proposta cria objetos apenas no schema `config`:

- `config.camadas_analise`;
- `config.perfis_diagnostico`;
- `config.perfil_camadas_analise`;
- `config.vw_camadas_analise_ativas`;
- `config.vw_perfis_diagnostico_camadas`.

O cadastro inicial registra as camadas ja usadas no MVP: geologia, geomorfologia, hidrogeologia, pedologia, vegetacao e hidrografia ANA. A tabela ANA foi registrada como `hidrografia.bh6_curso_dagua_ANA_2022`; quando referenciada diretamente em SQL, o nome real deve usar aspas duplas: `hidrografia."bh6_curso_dagua_ANA_2022"`.

A interface Streamlit foi preparada para ler `config.vw_camadas_analise_ativas`, exibir a pagina `Camadas de analise`, permitir cadastro/edicao apenas em `config.camadas_analise` e usar a selecao dinamica na pagina `Configurar diagnostico`. O processamento seletivo real por camada ainda nao foi implementado no backend.

Pendencias especificas:

1. Aplicar `sql/11_config_camadas_analise.sql` no banco somente com autorizacao explicita.
2. Validar os registros automaticos de camadas apos a aplicacao do script.
3. Testar a pagina `Camadas de analise` no Streamlit.
4. Criar futuramente importador seguro de novas camadas espaciais para PostGIS.
5. Implementar processamento seletivo real por camada no backend.
6. Persistir parametros de execucao e camadas selecionadas em estrutura propria, quando o fluxo de execucao via interface for ativado.

## Reorganizacao WebGIS da interface Streamlit

A interface `src/app_streamlit.py` foi reorganizada localmente para uma estrutura de WebGIS operacional interno, com as areas `Início`, `Compor diagnóstico`, `Dashboard`, `Exportações`, `Banco de dados geográficos` e `Administração`.

Melhorias aplicadas localmente:

- `MODO_APP = "interno"` criado como marcador inicial para futura separação entre camada pública e camada restrita;
- página inicial reorganizada como tela de entrada WebGIS limpa, com título institucional, mapa base Folium grande e botão `Iniciar projeto`;
- página inicial limpa implementada, mantendo apenas título, texto curto, mapa base Folium e botão `Iniciar projeto`;
- fluxo `Iniciar projeto` consolidado com `st.form` para selecionar ou cadastrar projeto, definir pasta SIG e validar upload de área de interesse;
- cadastro de camadas concentrado em `Banco de dados geográficos`, com filtros, métricas, formulário técnico em expander e gráficos Plotly de administração;
- `Compor diagnóstico` foi reorganizada em três passos: projeto/área, limites de análise e camadas/atributos, com `st.form` e agrupamento visual por grupo de camada;
- `Dashboard` passa a agrupar mapa, resumo, físico-biótico, socioeconômico, hidrografia, Explorador Analítico e dados brutos em abas;
- `Exportações` concentra montagem de comandos, sem executar automaticamente;
- `Administração` concentra status técnico, projetos cadastrados, execuções recentes, parâmetros de sessão e pendências.

Plotly foi incorporado como biblioteca principal de gráficos interativos do dashboard e da administração. As chaves dos gráficos foram centralizadas com `make_key(...)` e `exibir_plotly(...)` para corrigir colisões como `StreamlitDuplicateElementKey`. Folium permanece como base cartográfica operacional; mapas finais técnicos continuam dependendo de conferência no QGIS.

Pendências específicas da interface WebGIS:

1. Testar a interface reorganizada em ambiente local com Streamlit após autorização explícita.
2. Implementar login e controle de acesso real.
3. Criar camada pública somente leitura e definir separação pública/restrita.
4. Testar o upload real de área de interesse em GPKG, GeoJSON e SHP zipado após autorização explícita.
5. Implementar importação real de bases oficiais/reutilizáveis para PostGIS.
6. Implementar processamento seletivo real das camadas escolhidas no backend.
7. Persistir parâmetros de diagnóstico e camadas selecionadas em estrutura própria.
8. Gerar relatório DOCX automatizado.
9. Melhorar identidade visual da tela inicial e do dashboard após testes com usuários.
10. Ampliar gráficos Plotly para histogramas, box plots, dispersão e séries temporais quando houver dados validados.

## Fluxo funcional de projeto e área de interesse

Foi implementado localmente em `src/app_streamlit.py` o fluxo funcional inicial para projeto e área de interesse:

- botão `Iniciar projeto` na página `Início`;
- modal com `st.dialog` quando disponível, com fallback em expander;
- seleção de projeto existente ou cadastro de novo projeto;
- carregamento automático dos dados reais do projeto selecionado, incluindo código, nome, cliente, município, UF, atividade, tipo de estudo, responsável, pasta SIG, status, descrição e datas quando as colunas existirem;
- correção do comportamento que mostrava sugestão de código novo para projeto existente;
- proteção contra edição acidental de projeto existente, com edição apenas mediante marcação de `Editar dados do projeto existente` e confirmação explícita;
- seleção de área de interesse existente vinculada ao projeto, sem nova gravação;
- inserção de nova área de interesse em projeto existente, com confirmação explícita;
- definição de pasta SIG do projeto, com sugestão a partir de `EA2S_PROJECTS_ROOT` quando o projeto não tiver pasta cadastrada;
- upload de área de interesse em GPKG, GeoJSON ou SHP zipado;
- upload de área de interesse com GeoPandas, incluindo validação de CRS, geometria, número de feições, colunas, bbox e área;
- transformação para EPSG:31982 antes de cálculo e gravação;
- dissolução de múltiplas feições em uma única geometria MultiPolygon;
- gravação transacional restrita a `projetos.projeto` e `projetos.area_interesse`, apenas mediante confirmação explícita;
- atualização de `st.session_state` com `projeto_id`, `projeto_nome`, `area_interesse_id` e `projeto_sig_dir`.

Foi criado localmente o script `sql/12_fluxo_projeto_area_interesse.sql`, que adiciona `pasta_sig` e `data_atualizacao` em `projetos.projeto` com `ADD COLUMN IF NOT EXISTS` e sem `DROP`.

Também foi corrigida a geração de gráficos Plotly com a função auxiliar `exibir_plotly(fig, key)`, para evitar IDs duplicados no Streamlit.

Pendências específicas:

1. Aplicar `sql/12_fluxo_projeto_area_interesse.sql` no banco somente com autorização explícita.
2. Testar o fluxo de upload com GPKG.
3. Testar o fluxo de upload com GeoJSON.
4. Testar o fluxo de upload com shapefile zipado contendo `.shp`, `.dbf`, `.shx` e preferencialmente `.prj`.
5. Testar seleção de projeto existente e confirmar carregamento automático dos dados reais no modal.
6. Testar seleção de área de interesse existente sem inserir registros novos.
7. Confirmar inserção/atualização em `projetos.projeto` usando apenas as colunas reais disponíveis e apenas após confirmação explícita.
8. Confirmar inserção em `projetos.area_interesse` com geometria MultiPolygon em EPSG:31982.
9. Implementar importação de bases oficiais ou locais para o banco corporativo em módulo separado.
10. Implementar login, camada pública e camada interna com controle de acesso real.
11. Modularizar `src/app_streamlit.py` em componentes menores quando o fluxo estiver estabilizado.
12. Melhorar futuramente a edição de projetos com perfis de usuário, trilha de auditoria e permissões por papel.
