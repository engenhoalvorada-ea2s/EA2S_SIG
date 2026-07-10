# EA2S SIG

MVP de diagnostico territorial ambiental da EA2S, organizado para automatizar analises em PostgreSQL/PostGIS com scripts SQL, Python e documentacao versionada.

## Estrutura de pastas

- `sql/`: scripts SQL numerados para verificacoes, criacao de estrutura, cadastro de indicadores e processamento.
- `src/`: scripts Python para conexao, testes e execucao controlada do MVP.
- `docs/`: documentacao tecnica, metodologia e descricao dos indicadores.
- `tests/`: testes automatizados futuros.
- `outputs/`: area tecnica local do sistema. Por padrao, resultados finais de projetos devem ser exportados para a pasta SIG especifica do projeto, nao para esta pasta geral.
- `data/`: dados locais de apoio, sem versionar arquivos geograficos pesados.

## Configuracao do ambiente

1. Copie `.env.example` para `.env`.
2. Preencha `DB_PASSWORD` manualmente no `.env`.
3. Confirme os demais parametros:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ea2s_sig
DB_USER=postgres
DB_PASSWORD=sua_senha
SRID_OPERACIONAL=31982
EA2S_PROJECTS_ROOT=C:\Users\Usuario\OneDrive\EA2S\Projetos
```

Nao versionar o arquivo `.env`.

## Instalar dependencias

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Testar conexao

Depois de preencher o `.env`, execute:

```powershell
python src/test_conexao.py
```

O teste executa apenas uma consulta de leitura:

```sql
SELECT current_database(), current_user, inet_server_port();
```

## Interface Streamlit

A primeira versão da interface Streamlit fica em `src/app_streamlit.py`. Ela funciona como camada amigável para leitura, seleção e montagem de comandos do MVP, sem substituir o banco PostGIS nem os scripts existentes.

O código da interface está comentado em português, com docstrings e notas curtas para facilitar manutenção, revisão técnica e entrada de novos colaboradores sem alterar a lógica operacional do MVP.

Para iniciar a interface manualmente:

```powershell
python -m streamlit run src\app_streamlit.py
```

Nesta versão, a interface:

- seleciona projeto e área de interesse existentes;
- mantém `projeto_id`, `area_interesse_id`, `projeto_sig_dir` e parâmetros do diagnóstico em `st.session_state`;
- configura temas ambientais, socioeconomia, unidades espaciais e buffer;
- lista execuções recentes do projeto/área para exportação e consulta de resultados;
- monta comandos PowerShell para processamento, exportação de planilhas, gráficos e GPKG;
- adiciona `--incluir-hidrografia` quando Hidrografia ANA estiver marcada;
- consulta resultados existentes com `SELECT` e mostra tabelas com `st.dataframe`;
- lê o cadastro de camadas em `config.vw_camadas_analise_ativas`, quando o script `sql/11_config_camadas_analise.sql` já tiver sido aplicado com autorização.

A interface inicial ainda não executa scripts SQL automaticamente. A importacao oficial de novas bases depende da aplicacao manual e autorizada dos scripts de suporte, especialmente `sql/18_importacao_direta_schema_oficial.sql`, e exige confirmacao explicita do usuario. A exportação GPKG depende do `ogr2ogr` e do ambiente QGIS/GDAL configurado no PowerShell. A interface nao substitui os scripts de processamento nem dispensa revisao tecnica antes de gravacoes definitivas no banco.



## Fluxo funcional de início de projeto

A página `Início` do WebGIS funciona como entrada visual limpa do sistema: título institucional, texto curto, mapa base Folium grande e botão `Iniciar projeto`. Ela não exibe últimas execuções, status do banco, tabelas técnicas, debug ou dataframes; esses elementos ficam em `Administração`.

O botão abre o fluxo em `st.dialog` quando disponível na versão instalada do Streamlit. Se `st.dialog` não estiver disponível, o mesmo fluxo aparece em um bloco expansível após o clique. O formulário interno usa `st.form` para evitar processamento parcial a cada interação do usuário.

O fluxo permite:

- selecionar projeto existente ou cadastrar novo projeto, com projetos existentes ordenados dos mais recentes para os mais antigos;
- carregar automaticamente, para projeto existente, os dados já cadastrados em `projetos.projeto`;
- manter código e nome do projeto existente protegidos contra edição acidental;
- editar apenas campos permitidos do projeto existente, mediante confirmação explícita;
- definir ou reaproveitar a pasta SIG vinculada ao projeto;
- sugerir a pasta SIG a partir de `EA2S_PROJECTS_ROOT` no `.env` quando o projeto ainda não tiver pasta cadastrada;
- criar a pasta SIG caso o usuário marque a confirmação correspondente;
- reutilizar áreas de interesse existentes vinculadas ao projeto, sem inserir novos registros;
- inserir nova área de interesse por upload em GPKG, GeoJSON ou SHP zipado;
- validar CRS, geometria, número de feições, colunas, bbox e área em hectares com GeoPandas;
- dissolver múltiplas feições em uma única geometria MultiPolygon;
- gravar novo projeto em `projetos.projeto` e nova área em `projetos.area_interesse`, sempre com confirmação explícita;
- seguir para `Compor diagnóstico` após selecionar ou salvar projeto e área.

O navegador não permite escolher livremente uma pasta local como um software desktop. Por isso, a pasta SIG é informada como texto ou sugerida por:

```env
EA2S_PROJECTS_ROOT=C:\Users\Usuario\OneDrive\EA2S\Projetos
```

Antes de usar o fluxo completo no banco, aplicar manualmente e com autorização explícita o script:

```text
sql/12_fluxo_projeto_area_interesse.sql
```

Esse script adiciona `pasta_sig` e `data_atualizacao` em `projetos.projeto` quando essas colunas ainda não existirem. O app detecta as colunas reais antes de inserir ou atualizar dados, para evitar depender de campos opcionais inexistentes.

## Estrutura WebGIS da interface

A interface Streamlit foi reorganizada como um WebGIS operacional interno da EA2S, com navegação orientada por fluxo:

1. `Início`: entrada visual do WebGIS, com título institucional, mapa base Folium grande e botão `Iniciar projeto`.
2. `Compor diagnóstico`: escolha de limites de análise, camadas dinâmicas, socioeconomia e prévia dos comandos.
3. `Dashboard`: mapa Folium, resumo estatístico, físico-biótico, socioeconômico, hidrografia e dados brutos em uma única área.
4. `Exportações`: montagem de comandos para processamento, planilhas, gráficos e GeoPackage, sem execução automática.
5. `Banco de dados geográficos`: cadastro e administração de camadas de análise em `config.camadas_analise`, com leitura de `config.vw_camadas_analise_ativas`.
6. `Administração`: status técnico, projetos cadastrados, execuções recentes, parâmetros de sessão e pendências operacionais.

A base `EA2S_SIG` concentra sistema, scripts e dados oficiais. Dados de projeto, como área de interesse e pasta SIG, pertencem ao contexto de cada projeto. Resultados finais exportados devem continuar sendo gravados dentro da pasta SIG específica do projeto, em `resultados_mvp\execucao_<id>`.

O mapa operacional usa Folium/Leaflet para visualização rápida em EPSG:4326. O processamento oficial e os cálculos continuam no PostGIS, com SRID operacional adequado. Mapas finais técnicos, simbologia e conferência cartográfica detalhada ainda devem ser revisados no QGIS.

O Plotly passa a ser a biblioteca principal para gráficos interativos no dashboard, usando barras, barras horizontais, comparações por limite de análise e estruturas preparadas para histogramas, box plots, dispersão e pirâmide etária quando houver dados validados. Gráficos de pizza não são usados como padrão.

As informações técnicas, como status do banco, projetos cadastrados, últimas execuções e parâmetros de sessão, ficam em `Administração`, não na página inicial. A aplicação possui a variável `MODO_APP = "interno"`. Autenticação, perfil público somente leitura, controle de acesso e camada pública serão etapas futuras. Nesta versão não há login simulado: o modo interno apenas organiza a evolução esperada da interface.

## Dashboard e Explorador Analítico

O `Dashboard` reúne em uma única área operacional o mapa Folium, cards de resumo, análises físico-bióticas, socioeconômicas, hidrografia, Explorador Analítico e dados brutos. Os filtros de projeto, área de interesse, execução e limite de análise ficam no topo da página.

A aba `Explorador analítico` permite escolher a fonte de dados, o tipo de gráfico e as variáveis dos eixos. As fontes previstas são físico-biótico, socioeconômico, hidrografia e síntese executiva. Os gráficos são interativos com Plotly e usam chaves únicas geradas por `make_key(...)` para evitar `StreamlitDuplicateElementKey`.

O mapa usa Folium/Leaflet, `fit_bounds` quando a área de interesse está disponível e controle de camadas para área de interesse, buffer, microbacias, setores censitários e hidrografia. O processamento oficial e os cálculos continuam no PostGIS; a interface apenas consulta resultados já processados e organiza a visualização.
## Mapa na interface Streamlit

A interface possui uma página `Mapa` para visualização cartográfica rápida das camadas principais do projeto e da execução com Folium/Leaflet.

Dependências específicas:

```powershell
python -m pip install folium streamlit-folium
```

Como rodar a interface:

```powershell
python -m streamlit run src\app_streamlit.py
```

O mapa é uma visualização operacional inicial. As geometrias são transformadas para EPSG:4326 apenas para exibição no Folium; o processamento oficial continua no PostGIS, com cálculos em SRID operacional. Mapas finais técnicos, simbologia e conferência cartográfica detalhada ainda devem ser feitos no QGIS.

Camadas previstas na página `Mapa`:

- área de interesse;
- buffer configurável, por padrão 1000 m;
- microbacias interceptadas;
- setores censitários da execução;
- hidrografia ANA da execução, quando processada.
## Resumo estatístico no Streamlit

A interface possui uma página `Resumo estatístico` para consultar estatísticas consolidadas da execução selecionada.

A página permite:

- selecionar execução, projeto e área de interesse;
- escolher o limite de análise: área de interesse, buffer de 1000 m, microbacias interceptadas ou setores censitários intersectados;
- consultar estatísticas físico-bióticas por tema, classe dominante, área e percentual;
- consultar indicadores socioeconômicos dos setores censitários intersectados;
- consultar estatísticas de hidrografia, quando a execução tiver esse módulo processado;
- visualizar gráficos interativos simples com Plotly.

A pirâmide etária e a estrutura por sexo dependem de dados específicos disponíveis e validados no banco. Quando essas fontes não estiverem mapeadas com segurança, a interface mostra aviso e não inventa valores.

## Cadastro de camadas de analise

O script `sql/11_config_camadas_analise.sql` cria a primeira versao do cadastro configuravel de camadas do EA2S SIG. A tabela principal e `config.camadas_analise`, complementada por `config.perfis_diagnostico`, `config.perfil_camadas_analise` e pelas views `config.vw_camadas_analise_ativas` e `config.vw_perfis_diagnostico_camadas`.

A interface Streamlit possui a pagina `Camadas de analise`, que le esse cadastro para listar, filtrar e cadastrar/editar metadados das camadas. O formulario grava apenas em `config.camadas_analise`; ele nao importa arquivos espaciais, nao cria tabelas oficiais e nao altera schemas de origem.

Novas bases, como PRODES, CAR, unidades de conservacao, zoneamento ou risco geologico, podem seguir pelo fluxo de inventario e importacao oficial controlada antes do registro em `config.camadas_analise`. O processamento seletivo real por camada ainda e etapa futura; nesta versao, a selecao dinamica orienta a interface e os parametros de sessao.

Fluxo recomendado:

1. Aplicar `sql/11_config_camadas_analise.sql` no banco somente com autorizacao explicita.
2. Abrir a interface Streamlit.
3. Acessar `Camadas de analise`.
4. Conferir as camadas ativas e seus metadados.
5. Configurar o diagnostico usando a selecao dinamica de camadas.

## Inventario de bases geograficas

O modulo de inventario de bases geograficas avalia tecnicamente novas bases antes de qualquer importacao oficial. A proposta usa a aba `Inventariar nova base` em `Banco de dados geograficos`, o script base `sql/13_inventario_bases_geograficas.sql`, o complemento `sql/14_inventario_hash_deduplicacao.sql` e o perfilamento de atributos em `sql/15_perfil_atributos_inventario.sql`.

Fluxo previsto do inventario:

1. Entrada da base por upload, caminho local/rede ou URL registrada como pendente. Upload aceita GPKG, GeoJSON, JSON e shapefile zipado; caminho local/rede tambem permite `.shp` direto.
2. Leitura tecnica com GeoPandas/Fiona, sem alterar schemas oficiais.
3. Validacao de formato, CRS, geometria, bbox, quantidade de feicoes, campos e tipos geometricos.
4. Resumo estatistico inicial dos atributos numericos e textuais.
5. Perfilamento de atributos com inferencia de tipo, revisao manual em tabela editavel e conversoes apenas para visualizacao.
6. Explorador Grafico com Plotly, permitindo barras, barras horizontais, linhas, dispersao, histograma, box plot, violino, area, heatmap 2D, treemap, sunburst e pizza apenas quando escolhida explicitamente e aplicavel.
7. Complementacao manual de metadados: grupo, tema, subtema, fonte, orgao produtor, ano e destino sugerido.
8. Verificacao de duplicidade por hash SHA256 do arquivo original enviado.
9. Registro do inventario em `importacao.lote_importacao`, `importacao.inventario_arquivo` e, quando houver leitura tabular, `importacao.perfil_atributo`.

Inventariar e importar sao etapas diferentes. Inventariar registra metadados, qualidade, hash, sugestao de grupo/tema/schema/tabela, leitura exploratoria e perfilamento de atributos. O inventario tambem registra pendencias tecnicas, como geometrias invalidas, CRS ausente, ausencia de geometria ou erro de leitura identificado.

O hash SHA256 e calculado sobre o arquivo original enviado pelo usuario: ZIP, GPKG, GeoJSON ou JSON. Se o mesmo hash ja existir, a interface avisa que o arquivo ja foi inventariado, bloqueia o registro normal e exige confirmacao explicita para registrar duplicado. Registros duplicados de teste nao sao apagados automaticamente; futuramente poderao ser marcados como `arquivado`.

Para nomear bases oficiais, evitar nomes genericos como `area_interesse`, `camada` ou `upload`. Preferir nomes estaveis com tema, fonte e ano, por exemplo `parcelamento_solo_pmf_2023`, `zona_azul_pmf_2026` ou `pgv_pmf_2023`.

O inventario nao altera schemas oficiais como `urbano`, `geologia`, `geomorfologia`, `hidrogeologia`, `pedologia`, `vegetacao`, `hidrografia` ou `topografia`. O registro fica restrito ao schema operacional `importacao`.

## Fluxo simplificado de importacao oficial

O fluxo principal de importacao de novas bases foi simplificado. Em vez de exigir a passagem obrigatoria por staging, a interface passa a operar assim:

```text
Inventario -> Validacao tecnica -> Correcao opcional de geometria -> Importacao direta para schema oficial -> Cadastro opcional em config.camadas_analise
```

A aba principal em `Banco de dados geograficos` e `Importar para base oficial`. Ela seleciona um inventario ja registrado, diagnostica o arquivo persistido, verifica schema/tabela destino, conta feicoes e geometrias invalidas, permite testar correcao automatica em memoria e so entao oferece a importacao.

Situacoes previstas:

- `valido`: arquivo abre, possui SRID, geometrias validas, schema existe, tabela destino nao existe e a camada pode ser usada em diagnostico.
- `importado_com_pendencias`: arquivo abre e pode ser gravado, mas restam pendencias tecnicas. A camada pode ser importada para correcao posterior no QGIS, sem uso automatico em diagnostico.
- `bloqueado`: erro critico, como arquivo inexistente, falha de leitura, ausencia de geometria, SRID ausente sem correcao, schema inexistente ou tabela destino ja existente.

O arquivo original inventariado nunca e substituido. Ele permanece em:

```text
data/importacao/originais/lote_<lote_id>/inventario_<inventario_arquivo_id>/
```

Quando houver copia corrigida ou material auxiliar de correcao, a pasta prevista e:

```text
data/importacao/corrigidos/lote_<lote_id>/inventario_<inventario_arquivo_id>/
```

A implementacao local usa:

- `sql/18_importacao_direta_schema_oficial.sql`: cria a tabela de controle `importacao.importacao_oficial` e a view `importacao.vw_importacoes_oficiais`;
- `src/importacao_oficial.py`: centraliza diagnostico do inventario, teste de correcao de geometrias, nome seguro de tabela oficial e importacao direta;
- aba `Importar para base oficial` em `Banco de dados geograficos` na interface Streamlit.

A importacao direta so pode criar nova tabela no schema oficial indicado. Ela nao apaga, substitui, trunca ou sobrescreve tabelas existentes. O cadastro em `config.camadas_analise` e opcional; camadas com pendencias devem ficar inativas ou exigir confirmacao explicita.

Para habilitar o controle de importacoes oficiais no banco, aplicar manualmente e com autorizacao explicita:

```text
sql/18_importacao_direta_schema_oficial.sql
```

Testes manuais previstos depois da aplicacao autorizada do SQL 18:

1. Testar `inventario_arquivo_id = 4` (`zona_azul.zip`), esperando importacao como `valido`, `pode_usar_diagnostico = true` e opcao de cadastro ativo em `config.camadas_analise`.
2. Testar `Zoneamento.zip`, esperando deteccao de geometrias invalidas, tentativa de correcao automatica e, se restarem problemas, possibilidade de importar como `importado_com_pendencias`.
3. Tentar importar novamente para a mesma tabela oficial, esperando bloqueio de sobrescrita e sugestao de nome com sufixo `_v2`.

## Staging avancado

O fluxo `Inventario -> Staging` continua preservado como recurso avancado, mas nao e mais etapa obrigatoria do fluxo principal. Ele pode ser usado para auditoria, investigacao tecnica ou cargas intermediarias quando isso fizer sentido.

A implementacao local usa:

- `sql/16_importacao_staging.sql`: cria o schema `staging`, a tabela de controle `importacao.staging_importacao` e a view `importacao.vw_staging_importacoes`;
- `src/importacao_staging.py`: centraliza persistencia do arquivo original, nome seguro de tabela staging, leitura com GeoPandas, aplicacao do perfil confirmado e gravacao com `to_postgis`;
- aba `Staging avancado` em `Banco de dados geograficos` na interface Streamlit.

As tabelas staging sao sempre criadas no schema `staging`. O fluxo avancado nao altera schemas oficiais, nao promove a camada para base oficial e nao cadastra automaticamente em `config.camadas_analise`.

Para habilitar o controle de staging no banco, aplicar manualmente e com autorizacao explicita:

```text
sql/16_importacao_staging.sql
```
## Perfilamento e conversao de atributos

Muitas bases publicas trazem numeros como texto, valores monetarios com `R$`, percentuais com `%`, datas em formatos variados e codigos que parecem numeros mas nao devem ser somados. O modulo de perfilamento detecta tipos sugeridos para cada campo e permite que o usuario confirme o tipo correto antes de qualquer etapa de staging.

O perfil confirmado fica em `importacao.perfil_atributo`. Ele guarda tipo original, tipo sugerido, tipo confirmado, categoria de uso, nulos, valores unicos, exemplos e flags de uso em dashboard, graficos, popup de mapa e exportacao.

As conversoes sao temporarias e usadas apenas em copias de visualizacao para graficos, estatisticas e futuras exportacoes. A base original, os schemas oficiais e as tabelas de resultados permanecem preservados.

O perfilamento de atributos foi ajustado para evitar conversoes indevidas, especialmente numeros e codigos convertidos para data e codigos convertidos para booleano. Campos como `id`, `mslink`, `cd_*`, `cod*`, `setor`, `quadra` e `lote` sao priorizados como codigos.

O Explorador Grafico possui modo recomendado e modo avancado. O modo recomendado filtra colunas compativeis com cada tipo de grafico; o modo avancado permite testar combinacoes mais livres, com validacao antes de plotar. Campos de nome, classe, zona, uso e descricao podem ser usados como rotulo, cor/agrupamento ou hover, mesmo quando nao sao adequados como eixos numericos.
## Fluxo geral do MVP

1. Cadastrar projeto.
2. Inserir area de interesse.
3. Processar setores censitarios.
4. Calcular indicadores socioeconomicos.
5. Processar intersecoes fisico-bioticas.
6. Calcular indicadores derivados.
7. Exportar resultados.

## Cuidados operacionais

Neste projeto, comandos destrutivos no banco dependem de autorizacao explicita. Os schemas oficiais de dados importados devem ser preservados, especialmente `urbano`, `geologia`, `geomorfologia`, `pedologia`, `vegetacao`, `hidrografia` e `topografia`.

## Ordem dos scripts SQL

1. `sql/00_verificacoes_banco.sql`: conferencias iniciais de leitura.
2. `sql/01_schema_mvp.sql`: estrutura operacional idempotente.
3. `sql/02_cadastro_indicadores.sql`: cadastro provisorio de indicadores.
4. `sql/03_processar_setores_intersectados.sql`: funcao de intersecao dos setores.
5. `sql/04_calcular_indicadores_socioeconomicos.sql`: funcao de indicadores socioeconomicos.
6. `sql/05_intersecoes_fisico_biotico.sql`: etapa conceitual das intersecoes fisico-bioticas.
7. `sql/06_indicadores_derivados.sql`: matriz futura de indicadores derivados.
8. `sql/07_tabelas_tecnicas_fisico_biotico.sql`: views tecnicas fisico-bioticas.
9. `sql/08_tabelas_tecnicas_socioeconomico.sql`: views tecnicas socioeconomicas.
10. `sql/09_consultas_relatorio_integrado.sql`: views integradas para relatorio tecnico.
11. `sql/10_hidrografia_ana.sql`: modulo opcional de hidrografia ANA linear.
12. `sql/11_config_camadas_analise.sql`: cadastro configuravel de camadas de analise e perfis de diagnostico.
13. `sql/12_fluxo_projeto_area_interesse.sql`: suporte ao fluxo funcional de projeto, pasta SIG e area de interesse.
14. `sql/13_inventario_bases_geograficas.sql`: estrutura operacional para inventario e validacao de novas bases geograficas.
15. `sql/14_inventario_hash_deduplicacao.sql`: complemento de hash, deduplicacao e view ampliada do inventario.
16. `sql/15_perfil_atributos_inventario.sql`: perfilamento de atributos de bases inventariadas.
17. `sql/16_ajuste_view_inventario_criado_em.sql`: ajuste complementar local da view de inventario para expor `lote_criado_em`, `arquivo_criado_em` e `criado_em`.
18. `sql/16_importacao_staging.sql`: estrutura operacional avancada para importacao Inventario -> Staging, com schema `staging`, tabela de controle e view tecnica.
19. `sql/18_importacao_direta_schema_oficial.sql`: controle operacional da importacao direta para schema oficial, com tabela `importacao.importacao_oficial` e view tecnica.
20. `sql/99_consultas_conferencia.sql`: consultas finais de leitura.
## Como executar o MVP

Depois de preencher o `.env` e confirmar que os scripts e funcoes necessarios ja foram aplicados no banco com autorizacao, o orquestrador principal pode ser chamado assim:

```powershell
python src/executar_mvp.py --projeto-id 1 --area-interesse-id 1 --usuario Paulo
```

Para validar a existencia do projeto e da area e revisar a sequencia prevista sem criar execucao nem chamar funcoes de processamento:

```powershell
python src/executar_mvp.py --projeto-id 1 --area-interesse-id 1 --dry-run
```

O orquestrador cria uma linha em `resultados.execucao`, executa as etapas validadas do MVP em sequencia controlada e informa o `execucao_id` gerado para consulta das views finais de relatorio.
## Como exportar resultados do MVP

Os resultados finais devem ser gravados na pasta SIG especifica de cada projeto. A base `EA2S_SIG` contem o sistema, scripts e dados oficiais; produtos finais de projetos ficam fora dessa base comum.

Exemplo:

```powershell
python src\exportar_resultados_mvp.py --execucao-id 6 --projeto-id 1 --area-interesse-id 1 --projeto-sig-dir "C:\Users\Usuario\OneDrive\EA2S\Projetos\Ataide\SIG"
```

O exportador cria automaticamente a subpasta:

```text
<projeto-sig-dir>\resultados_mvp\execucao_<execucao_id>\
```

Os arquivos Excel gerados ficam dentro dessa pasta de execucao.

## Como gerar graficos do MVP

Os graficos do MVP tambem devem ser gravados na pasta SIG especifica do projeto, dentro de `resultados_mvp\execucao_<execucao_id>\graficos`.

Exemplo:

```powershell
python src\gerar_graficos_mvp.py --execucao-id 6 --projeto-id 1 --area-interesse-id 1 --projeto-sig-dir "C:\CAMINHO\DO\PROJETO\SIG"
```

O gerador usa apenas consultas `SELECT` nas views integradas do relatorio, cria imagens `.png` em `dpi=300` e organiza as saidas em subpastas para fisico-biotico, socioeconomico e sintese.
## Primeira versao funcional do MVP

A primeira versao funcional do MVP EA2S SIG foi validada com:

- `projeto_id = 1`
- `area_interesse_id = 1`
- `execucao_id = 6`
- pasta SIG do projeto de teste: `C:\Users\Usuario\OneDrive\EA2S\Projetos\2025\Ataide_Ingleses\SIG`

O processamento validado gerou 4 setores censitarios intersectados, 150 registros fisico-bioticos e 39 indicadores socioeconomicos de resumo. As views integradas de relatorio, a exportacao de planilhas e a geracao automatica de graficos tambem foram validadas.

### Rodar o processamento

```powershell
python src\executar_mvp.py --projeto-id 1 --area-interesse-id 1 --usuario Paulo
```

### Exportar resultados

```powershell
python src\exportar_resultados_mvp.py --execucao-id 6 --projeto-id 1 --area-interesse-id 1 --projeto-sig-dir "C:\Users\Usuario\OneDrive\EA2S\Projetos\2025\Ataide_Ingleses\SIG"
```

### Gerar graficos

```powershell
python src\gerar_graficos_mvp.py --execucao-id 6 --projeto-id 1 --area-interesse-id 1 --projeto-sig-dir "C:\Users\Usuario\OneDrive\EA2S\Projetos\2025\Ataide_Ingleses\SIG"
```

A pasta `EA2S_SIG` contem o sistema, scripts e base comum. Os produtos finais de cada projeto sao gerados dentro da pasta SIG especifica do projeto. Cada execucao cria uma subpasta propria em:

```text
<projeto-sig-dir>\resultados_mvp\execucao_<execucao_id>\
```

## Como exportar GeoPackage do MVP

O MVP possui um exportador espacial para gerar um unico GeoPackage com camadas organizadas para leitura no QGIS. A saida deve ficar dentro da pasta SIG especifica do projeto, nao dentro da base comum `EA2S_SIG`.

Exemplo:

```powershell
python src\exportar_gpkg_mvp.py --execucao-id 6 --projeto-id 1 --area-interesse-id 1 --projeto-sig-dir "C:\Users\Usuario\OneDrive\EA2S\Projetos\2025\Ataide_Ingleses\SIG" --overwrite
```

A saida sera criada em:

```text
<projeto-sig-dir>\resultados_mvp\execucao_<execucao_id>\gpkg\ea2s_sig_execucao_<execucao_id>.gpkg
```

A area de interesse nao e duplicada por padrao, pois e o poligono original de entrada do projeto. As camadas de referencia espacial exportadas sao:

- `buffer_1000m`
- `microbacias_interceptadas`
- `setores_censitarios_intersectados`
- `setores_censitarios_area_intersectada`

A camada `setores_censitarios_intersectados` usa o limite completo dos setores censitarios a partir de `urbano.setores_censo_2022_malha_br` e agrega atributos socioeconomicos de `resultados.vw_relatorio_socio_contexto_setores`. A camada `setores_censitarios_area_intersectada` mantem a geometria da intersecao com a area de interesse para auditoria espacial.

As camadas ambientais sao separadas por unidade de analise e tema:

- area de interesse: `area_interesse_geologia`, `area_interesse_geomorfologia`, `area_interesse_hidrogeologia`, `area_interesse_pedologia`, `area_interesse_vegetacao`
- buffer de 1000 m: `buffer_1000m_geologia`, `buffer_1000m_geomorfologia`, `buffer_1000m_hidrogeologia`, `buffer_1000m_pedologia`, `buffer_1000m_vegetacao`
- microbacias: `microbacias_geologia`, `microbacias_geomorfologia`, `microbacias_hidrogeologia`, `microbacias_pedologia`, `microbacias_vegetacao`

Cada camada ambiental contem area, percentual e atributos originais da camada oficial usados na intersecao. O campo `valor_principal` continua sendo a referencia principal para agrupamento e calculo de area. Os demais atributos originais servem para diagnostico tecnico, auditoria e geracao automatica de texto.

O exportador expande as chaves de `atributos_origem` em colunas do GeoPackage com nomes sanitizados, sem acentos, espacos ou caracteres especiais. A coluna `atributos_origem_json` tambem e exportada para preservar o JSON completo da feicao oficial.

Para que esses atributos estejam disponiveis, o SQL atualizado de `sql/05_intersecoes_fisico_biotico.sql` precisa ser reaplicado no banco com autorizacao explicita e uma nova execucao do MVP precisa gravar os campos `fonte_schema`, `fonte_tabela`, `fonte_camada` e `atributos_origem` em `resultados.intersecao_fisico_biotica`.

Para auditoria, e possivel incluir uma camada unica com todas as intersecoes fisico-bioticas:

```powershell
python src\exportar_gpkg_mvp.py --execucao-id 6 --projeto-id 1 --area-interesse-id 1 --projeto-sig-dir "C:\Users\Usuario\OneDrive\EA2S\Projetos\2025\Ataide_Ingleses\SIG" --overwrite --incluir-auditoria
```

Nesse caso, tambem sera exportada a camada `auditoria_fb_intersecoes_todas`.

Quando `--incluir-hidrografia` for informado, tambem sao exportadas as camadas lineares `hidrografia_area_interesse`, `hidrografia_buffer_1000m` e `hidrografia_microbacias`.

O exportador usa `ogr2ogr`/GDAL para exportar consultas `SELECT` do PostGIS para GeoPackage. Se `ogr2ogr` nao estiver disponivel no `PATH`, execute pelo ambiente do QGIS/OSGeo4W ou configure o GDAL/OGR no Windows.

Arquivos `.lyr` nao sao convertidos automaticamente nesta versao. Eles podem ser guardados como referencia de simbologia do ArcGIS, mas a aplicacao de estilos no QGIS deve ser feita posteriormente, preferencialmente com arquivos `.qml` ou `.sld`.

## Processamento de hidrografia ANA

A hidrografia ANA e tratada no MVP como camada linear, separada das intersecoes fisico-bioticas poligonais. A metrica principal e comprimento, em metros e quilometros, nao area.

A base ANA principal identificada para esta versao e `hidrografia."bh6_curso_dagua_ANA_2022"`; por conter letras maiusculas no nome, ela deve ser escrita com aspas duplas quando referenciada diretamente em SQL. A tabela de microbacias usada como unidade de analise continua sendo `hidrografia.microbacias_sigeo_sirhesc_aguassc`.

A hidrografia ANA esta em SRID 4674 e possui geometria `MULTILINESTRING` no campo `geom`. As microbacias estao em SRID 29192 e possuem geometria `MULTIPOLYGON` no campo `geom`. O processamento transforma todas as geometrias para EPSG:31982 antes de recortar e calcular comprimento.

A tabela ANA nao possui campo explicito de nome do rio ou curso d'agua. Por isso, `nome_curso` permanece nulo nesta versao e nao deve ser preenchido com codigo. Os principais identificadores usados sao `idcda`, `cocursodag`, `nuordemcda` e `nunivotcda`; os campos `fid`, `wtc_pk`, `cocdadesag`, `dedominial`, `dsversao` e `nucompcda` tambem sao preservados nas saidas tecnicas.

Os atributos originais da ANA sao preservados em `atributos_origem` com `to_jsonb(h) - 'geom' - 'geometry'`. As camadas exportadas ficam em SRID 31982 e usam geometria linear recortada.

O processamento e opcional nesta fase. Exemplo:

```powershell
python src\executar_mvp.py --projeto-id 1 --area-interesse-id 1 --usuario Paulo --incluir-hidrografia
```

Para exportar a hidrografia no GeoPackage:

```powershell
python src\exportar_gpkg_mvp.py --execucao-id 7 --projeto-id 1 --area-interesse-id 1 --projeto-sig-dir "C:\Users\Usuario\OneDrive\EA2S\Projetos\2025\Ataide_Ingleses\SIG" --overwrite --incluir-hidrografia
```

Camadas lineares previstas:

- `hidrografia_area_interesse`
- `hidrografia_buffer_1000m`
- `hidrografia_microbacias`
