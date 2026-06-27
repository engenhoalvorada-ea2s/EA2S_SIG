# Metodologia

## Visao geral

O MVP EA2S SIG organiza uma rotina de diagnostico territorial ambiental baseada em uma area de interesse, setores censitarios e camadas fisico-bioticas. O SRID operacional adotado e EPSG:31982, SIRGAS 2000 / UTM 22S.

## Area de interesse

A area de interesse deve ser armazenada e processada em EPSG:31982. Esse sistema projetado permite trabalhar com medidas de area em metros quadrados com maior consistencia para o territorio analisado.

## Setores censitarios

Os setores censitarios devem usar a malha IBGE 2022 como base espacial. Antes do processamento, os codigos de setor precisam estar padronizados para evitar divergencias entre geometria e tabelas de atributos.

## Intersecao espacial

O procedimento central consiste em intersectar a area de interesse com os setores censitarios. Para cada setor interceptado, devem ser calculadas:

- area total do setor;
- area interceptada pela area de interesse;
- proporcao interceptada.

## Ponderacao areal

Indicadores socioeconomicos podem ser estimados por ponderacao areal quando a informacao original esta agregada por setor censitario. Nesse caso, os valores sao multiplicados pela proporcao da area do setor que intersecta a area de interesse.

## Limitacoes

A ponderacao areal assume distribuicao homogenea dos atributos dentro de cada setor censitario. Essa hipotese pode gerar distorcoes em areas com ocupacao irregular, grandes vazios, corpos d'agua, usos nao residenciais ou concentracao espacial de populacao e infraestrutura.

## Revisao tecnica

Os indicadores selecionados para o MVP devem ser revisados tecnicamente antes de uso analitico definitivo. A documentacao dos campos, formulas e criterios de ponderacao deve ser mantida em `docs/indicadores.md`.
## Ordem operacional atualizada

A ordem revisada do MVP posiciona as intersecoes fisico-bioticas antes dos indicadores derivados, pois parte dos derivados futuros pode depender de exposicao ambiental e cruzamentos territoriais.

1. Conferir o banco com `sql/00_verificacoes_banco.sql`.
2. Preparar a estrutura operacional com `sql/01_schema_mvp.sql`.
3. Cadastrar indicadores provisorios com `sql/02_cadastro_indicadores.sql`.
4. Processar setores censitarios com `sql/03_processar_setores_intersectados.sql`.
5. Calcular indicadores socioeconomicos com `sql/04_calcular_indicadores_socioeconomicos.sql`.
6. Estruturar intersecoes fisico-bioticas com `sql/05_intersecoes_fisico_biotico.sql`.
7. Consolidar indicadores derivados futuros com `sql/06_indicadores_derivados.sql`.
8. Gerar tabelas tecnicas fisico-bioticas com `sql/07_tabelas_tecnicas_fisico_biotico.sql`.
9. Gerar tabelas tecnicas socioeconomicas com `sql/08_tabelas_tecnicas_socioeconomico.sql`.
10. Gerar views integradas de relatorio com `sql/09_consultas_relatorio_integrado.sql`.
11. Conferir resultados com `sql/99_consultas_conferencia.sql`.
## Camadas fisico-bioticas confirmadas

As camadas ambientais e de microbacias possuem tabelas, geometrias, SRIDs e atributos principais confirmados em `docs/camadas_fisico_bioticas.md`. A etapa futura de intersecoes deve transformar as geometrias para EPSG:31982 antes de calcular areas e deve reportar area em m2, hectares e percentual por atributo principal.

A tabela `resultados.intersecao_fisico_biotica` e a funcao `resultados.processar_intersecoes_fisico_bioticas_mvp` foram propostas em `sql/05_intersecoes_fisico_biotico.sql`, ainda sem execucao no banco. A proposta deve ser revisada antes de aplicacao.
## Regras do MVP fisico-biotico

Nesta versao MVP, `buffer_1000m` representa o buffer completo de 1000 m ao redor da area de interesse, incluindo a propria area. Uma unidade futura `entorno_1000m`, excluindo a area de interesse, pode ser avaliada depois.

Para microbacias, a proposta considera todas as microbacias interceptadas pela area de interesse. A microbacia dominante podera ser indicada posteriormente em tabela de resumo ou texto tecnico.

A funcao proposta deve calcular areas sempre em EPSG:31982 e usar `ST_MakeValid`, `ST_CollectionExtract(..., 3)` e `ST_Multi` para garantir saidas `MultiPolygon`. As areas e percentuais registrados devem ser arredondados para reduzir ruido de precisao numerica, e o percentual deve ser limitado entre 0 e 100. O retorno `area_total_registrada_m2` e uma soma operacional das areas gravadas por tema e unidade de analise, nao uma area territorial liquida unica.
## Views tecnicas fisico-bioticas

O script `sql/07_tabelas_tecnicas_fisico_biotico.sql` organiza views de sintese, classes tematicas e tabelas por tema a partir da tabela-base `resultados.intersecao_fisico_biotica`. As views tematicas preservam os campos de unidade de analise para permitir tabelas especificas de `area_interesse`, `buffer_1000m` e `microbacia`.

Hidrogeologia e mantida como tema fisico-biotico ja calculado no script 05. Hidrologia superficial, cursos d'agua e drenagem devem ser tratados em modulo posterior com camadas de hidrografia.

A proxima etapa e revisar e testar o `sql/07_tabelas_tecnicas_fisico_biotico.sql` em transacao controlada antes de execucao definitiva.
## Views tecnicas socioeconomicas

O modulo socioeconomico usa os setores censitarios interceptados pela area de interesse como base espacial e metodologica. A camada `resultados.setores_intersectados` representa o recorte censitario para abertura no QGIS e para auditoria das ponderacoes areais.

Os resultados socioeconomicos sao sempre separados por `execucao_id`, `projeto_id` e `area_interesse_id`. O banco nao cria tabelas por projeto e nao incorpora o nome do projeto aos nomes de tabelas ou views. Produtos finais, arquivos exportados e mapas podem receber nome do projeto, mas as estruturas internas permanecem genericas e reutilizaveis.

As views do script `sql/08_tabelas_tecnicas_socioeconomico.sql` organizam os resultados para relatorio, auditoria e exportacao. Elas incluem dados de projeto e area de interesse por meio de joins com `projetos.projeto` e `projetos.area_interesse`, mantendo as tabelas-base em `resultados` como fonte dos calculos ja processados.
## Contexto socioeconomico dos setores interceptados

Ha duas formas distintas de apresentar os resultados socioeconomicos:

- Estimativa proporcional por area de setor: usa a proporcao da area do setor censitario intersectada pela area de interesse para estimar valores dentro do poligono. Essa abordagem pode ser adequada quando a premissa de distribuicao homogenea e aceitavel.
- Contexto socioeconomico dos setores censitarios interceptados: usa os valores originais dos setores censitarios que tocam a area de interesse, sem ponderar populacao, domicilios ou infraestrutura pela area do poligono.

Para areas ambientais, APPs, glebas vazias ou areas nao ocupadas, a abordagem principal do relatorio deve ser o contexto dos setores censitarios interceptados. Nessa leitura, populacao, domicilios e infraestrutura correspondem aos setores censitarios inteiros, servindo como contexto territorial do entorno censitario da area analisada.

No script `sql/08_tabelas_tecnicas_socioeconomico.sql`, essa abordagem e organizada pelas views `resultados.vw_socio_contexto_setores` e `resultados.vw_socio_contexto_setores_total`. A primeira apresenta uma linha por setor censitario interceptado usando `valor_original`; a segunda soma indicadores de quantidade dos setores, calcula a media simples de renda entre setores e tambem apresenta a renda media ponderada pelo numero de responsaveis em domicilios particulares permanentes ocupados. Para interpretacao tecnica da sintese territorial, `renda_media_responsavel_ponderada_responsaveis` e preferivel a media simples entre setores, pois considera o peso demografico de cada setor. A coluna `renda_mediana_responsavel_media_setores` permanece apenas como referencia descritiva, ja que mediana setorial nao e somavel nem ponderavel diretamente sem microdados.

Valores nulos devem ser preservados como nulos: eles indicam ausencia de dado ou dado nao informado na base de origem. Nao devem ser convertidos para zero, pois zero representa valor observado igual a zero quando vem da base. Na view total, os somatorios consideram os setores com dados disponiveis para cada indicador, e os campos de controle `possui_dados_basicos`, `possui_dados_dppo`, `possui_dados_renda`, `possui_dados_saneamento` e `status_dados_setor` ajudam a avaliar a completude de cada setor.
## Consultas integradas para relatorio tecnico

O script `sql/09_consultas_relatorio_integrado.sql` consolida as saidas fisico-bioticas e socioeconomicas ja organizadas pelos scripts `07` e `08`. Ele nao recalcula intersecoes, indicadores, areas ou percentuais; apenas cria views finais de apresentacao para relatorio tecnico, mapas, graficos e exportacoes.

A sintese executiva integrada combina identificacao da execucao, projeto e area de interesse, contexto socioeconomico dos setores censitarios interceptados, microbacias interceptadas e classes fisico-bioticas predominantes na area de interesse. As classes predominantes sao selecionadas pela maior area em hectares dentro de cada tema para a unidade `area_interesse`.

Para o componente socioeconomico, a saida principal do relatorio integrado usa o contexto dos setores censitarios interceptados, com valores originais dos setores, e nao a estimativa proporcional pela area do poligono. Essa escolha evita interpretar populacao, domicilios e infraestrutura como se estivessem homogeneamente distribuidos dentro de areas ambientais, APPs, glebas vazias ou areas nao ocupadas.
## Orquestrador do MVP

O arquivo `src/executar_mvp.py` e o orquestrador principal da rodada do MVP. Ele cria uma execucao unica em `resultados.execucao` e chama, em sequencia controlada, os modulos ja validados para setores censitarios, indicadores socioeconomicos e intersecoes fisico-bioticas.

Todos os resultados gerados por uma rodada devem permanecer relacionados pelas chaves `execucao_id`, `projeto_id` e `area_interesse_id`. Essa regra permite consultar as views finais de relatorio sem criar tabelas por projeto e sem misturar resultados de rodadas diferentes.

O modo `--dry-run` deve ser usado antes da execucao real para validar projeto e area de interesse e revisar a sequencia prevista sem inserir registro de execucao nem chamar funcoes de processamento.
## Exportacao dos resultados do MVP

A pasta `EA2S_SIG` e a base comum do sistema, scripts e dados oficiais. Os resultados exportados do MVP pertencem a pasta SIG especifica de cada projeto, informada no momento da exportacao por `--projeto-sig-dir`.

Cada execucao exportada cria uma subpasta propria em `resultados_mvp\execucao_<id>` dentro da pasta SIG do projeto. Essa organizacao evita misturar dados oficiais, scripts do sistema e produtos finais de projetos diferentes.

O exportador `src/exportar_resultados_mvp.py` deve consultar apenas as views finais por `SELECT` e gerar arquivos Excel de apresentacao. Ele nao deve alterar dados, criar tabelas no banco ou gravar resultados dentro da base comum `EA2S_SIG/outputs` por padrao.
