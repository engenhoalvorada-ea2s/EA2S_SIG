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
- consulta resultados existentes com `SELECT` e mostra tabelas com `st.dataframe`.

A interface inicial ainda não executa scripts automaticamente. A execução direta por botão será uma etapa futura, com controles adicionais de segurança. A exportação GPKG depende do `ogr2ogr` e do ambiente QGIS/GDAL configurado no PowerShell. A interface também ainda não cadastra projetos, não importa novas bases espaciais e não substitui os scripts de processamento.

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
12. `sql/99_consultas_conferencia.sql`: consultas finais de leitura.

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
