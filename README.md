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
11. `sql/99_consultas_conferencia.sql`: consultas finais de leitura.

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
