# Skill: ea2s-streamlit

Use esta skill quando a tarefa envolver a interface Streamlit do EA2S SIG.

## Objetivo

Construir uma interface operacional, clara e segura para WebGIS interno, sem misturar acao destrutiva, consulta e configuracao.

## Regras obrigatorias

- Nao execute o app sem autorizacao explicita.
- Nao conecte no banco sem autorizacao explicita.
- Nao rode scripts auxiliares por conta propria.
- Preserve o fluxo existente e comentarios didaticos.
- O usuario esta aprendendo programacao; explique trechos importantes com comentarios curtos em portugues.

## Estrutura de interface

Priorize paginas e blocos funcionais:

- Inicio
- Iniciar projeto
- Compor diagnostico
- Dashboard
- Exportacoes
- Banco de dados geograficos
- Administracao

Evite telas de marketing. A primeira tela deve ajudar a operar o sistema.

## Forms e botoes

- Use `st.form` para acoes de registro, importacao ou processamento composto.
- Evite botoes soltos que disparam operacoes sensiveis sem contexto.
- Depois de uma acao, atualize `st.session_state` com o resultado relevante.
- Mensagens devem ser claras: o que aconteceu, onde foi gravado e qual o proximo passo.

## Estado da interface

- Use `st.session_state` para manter projeto, area de interesse, arquivos carregados, resultados de validacao e filtros.
- Nao dependa de variaveis globais mutaveis para fluxo do usuario.
- Use chaves estaveis em widgets.

## Plotly e graficos

- Use `plotly.express` quando possivel.
- Exiba graficos com helper que passe `key`, por exemplo `exibir_plotly(fig, key=make_key(...))`.
- Nao use `st.plotly_chart` diretamente sem chave estavel.
- Valide colunas numericas, categoricas e temporais antes de plotar.
- Mostre aviso amigavel quando o grafico nao for compativel com os dados.

## Folium e mapas

- Use chaves estaveis para mapas.
- Carregue apenas dados necessarios para manter a interface leve.
- Deixe claro quando a visualizacao e exploratoria e nao substitui processamento oficial no PostGIS.

## Erros

- Nao deixar traceback bruto como unica resposta ao usuario.
- Mostrar mensagem amigavel e sugestao de diagnostico.
- Registrar detalhes tecnicos apenas quando ajudarem a corrigir.

## Banco de dados

Quando a interface ler metadados de tabelas como `config.camadas_analise`, use camada de compatibilidade e nao assuma nomes reais de colunas como `schema_origem` ou `tabela_origem`.