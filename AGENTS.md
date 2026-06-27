# Instrucoes permanentes do projeto

Este projeto e o MVP EA2S SIG.

- Usar PostgreSQL/PostGIS.
- Usar SRID operacional EPSG:31982.
- Nao alterar tabelas oficiais.
- Nao executar comandos destrutivos sem autorizacao explicita.
- Nunca executar sem autorizacao: `DROP DATABASE`, `DROP SCHEMA`, `DROP TABLE`, `TRUNCATE`, `DELETE` sem `WHERE`, `UPDATE` sem `WHERE` ou `ALTER TABLE` em tabelas oficiais.
- Nao alterar dados oficiais importados nos schemas `urbano`, `geologia`, `geomorfologia`, `pedologia`, `vegetacao`, `hidrografia` e `topografia`.
- Preferir scripts SQL numerados.
- Usar aliases explicitos em PL/pgSQL.
- Evitar ambiguidade entre variaveis e colunas.
- Registrar logs em `logs.processamento`.
- Usar `.env` para conexao.
- Nao colocar senha em codigo.
- Gerar outputs em `outputs/`.
