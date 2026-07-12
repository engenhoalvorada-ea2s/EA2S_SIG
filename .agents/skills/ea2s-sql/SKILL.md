# Skill: ea2s-sql

Use esta skill quando a tarefa envolver criar, revisar ou reorganizar scripts SQL do EA2S SIG.

## Objetivo

Produzir SQL seguro, versionado, revisavel e coerente com o fluxo real do projeto, sem presumir estrutura de banco nao confirmada.

## Regras obrigatorias

- Nao execute SQL por conta propria.
- Nao conecte no banco sem autorizacao explicita.
- Nao rode migrations sem autorizacao explicita.
- Nao use `DROP TABLE`, `TRUNCATE` ou `DELETE` sem pedido explicito.
- Nao altere schemas oficiais sem confirmacao explicita.
- Prefira scripts locais em `sql/`.
- Registre pendencias quando a estrutura real ainda nao estiver confirmada.

## Padrao de script

Cada script deve ter:

- Cabecalho com finalidade, status e cuidados.
- Objetos criados ou alterados.
- Dependencias esperadas.
- Comentarios de validacao manual.
- Consultas de conferencia comentadas no final, quando util.

## DDL seguro

Use quando aplicavel:

- `CREATE SCHEMA IF NOT EXISTS`
- `CREATE TABLE IF NOT EXISTS`
- `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
- `CREATE INDEX IF NOT EXISTS`
- `CREATE OR REPLACE FUNCTION`
- `DROP VIEW IF EXISTS` seguido de `CREATE VIEW`, apenas para views de apresentacao quando nomes ou ordem de colunas mudarem.

Evite `CREATE OR REPLACE VIEW` quando a view existente pode ter nomes ou ordem de colunas diferentes.

## Consultas e views

- Evite `SELECT *`.
- Nomeie colunas explicitamente.
- Preserve campos de identificacao: `execucao_id`, `projeto_id`, `area_interesse_id`.
- Use aliases claros.
- Evite ambiguidade com nomes como `id`, `execucao_id`, `geom` e `status`.

## Funcoes

- Preservar assinatura quando a funcao ja foi validada no DBeaver.
- Preservar ordem dos parametros.
- Preservar `RETURNS TABLE` quando existir.
- Incluir logs em `logs.processamento` quando o fluxo ja usar log.
- Incluir bloco `EXCEPTION WHEN OTHERS THEN` quando a funcao executa processamento composto.
- Relancar erro com `RAISE` quando necessario para nao ocultar falhas.

## Antes de assumir colunas

Se houver duvida sobre estrutura real, documente consulta de inspecao, por exemplo:

```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'config'
  AND table_name = 'camadas_analise'
ORDER BY ordinal_position;
```

Nao execute essa consulta sem autorizacao.