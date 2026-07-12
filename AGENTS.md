# AGENTS.md — EA2S SIG

## Contexto do projeto

A EA2S é uma empresa de consultoria socioambiental que atua com estudos, pesquisas, projetos ambientais, diagnósticos territoriais, análises socioeconômicas e produtos técnicos voltados ao planejamento, licenciamento e gestão ambiental.

O projeto **EA2S SIG** está sendo desenvolvido como uma ferramenta interna de geoprocessamento, análise territorial e WebGIS socioambiental. Seu objetivo inicial é aumentar a qualidade, padronização e produtividade dos produtos técnicos da EA2S. Em uma etapa futura, o sistema poderá servir como base para soluções customizáveis voltadas a outras empresas e organizações.

O sistema busca consolidar um repositório socioambiental com dados tabulares, vetoriais e, futuramente, matriciais, permitindo analisar áreas de interesse, limites territoriais e camadas temáticas, com geração de estatísticas, gráficos, mapas, tabelas, exportações e textos técnicos automatizados.

## Objetivo do sistema

O EA2S SIG deve permitir:

1. Cadastrar projetos e áreas de interesse.
2. Inventariar bases geográficas oficiais ou locais.
3. Validar e corrigir dados quando possível.
4. Importar bases para schemas oficiais de forma controlada.
5. Cadastrar camadas em `config.camadas_analise`.
6. Compor planos de diagnóstico.
7. Montar matrizes de cruzamento entre limites e camadas.
8. Gerar diagnósticos exploratórios e oficiais.
9. Produzir tabelas, estatísticas, gráficos, mapas e exportações.
10. Apoiar a elaboração de relatórios técnicos ambientais, socioeconômicos e territoriais.

## Stack técnica

O projeto utiliza principalmente:

- Python
- Streamlit
- PostgreSQL/PostGIS
- GeoPandas
- Pandas
- Shapely
- Plotly
- Folium
- SQL versionado em `sql/`
- Documentação em `docs/`

## Fluxo principal do sistema

O fluxo principal do EA2S SIG é:

```text
Projeto e área de interesse
→ Inventário de bases
→ Validação e correção técnica
→ Importação oficial controlada
→ Cadastro em config.camadas_analise
→ Plano de diagnóstico
→ Matriz de cruzamentos
→ Diagnóstico exploratório/oficial
→ WebGIS
→ Exportações