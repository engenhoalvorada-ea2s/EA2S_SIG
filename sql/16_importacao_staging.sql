-- sql/16_importacao_staging.sql
--
-- Primeira versao do fluxo Inventario -> Staging do EA2S SIG.
-- Nao executar automaticamente. Aplicar manualmente apenas com autorizacao explicita.
--
-- Escopo:
-- - cria schema operacional staging;
-- - cria tabela de controle importacao.staging_importacao;
-- - cria view tecnica importacao.vw_staging_importacoes;
-- - remove e recria apenas a view tecnica, sem CASCADE, para permitir evolucao de colunas;
-- - nao altera schemas oficiais;
-- - nao promove camadas para schema oficial;
-- - nao cadastra automaticamente em config.camadas_analise.

CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS importacao.staging_importacao (
    id bigserial PRIMARY KEY,
    inventario_arquivo_id bigint NOT NULL,
    lote_id bigint NOT NULL,
    schema_staging text NOT NULL DEFAULT 'staging',
    tabela_staging text NOT NULL,
    nome_original text,
    layer_name text,
    hash_arquivo text,
    srid_origem integer,
    srid_destino integer DEFAULT 31982,
    tipo_geometria text,
    numero_feicoes_origem integer,
    numero_feicoes_staging integer,
    geometrias_invalidas_origem integer,
    geometrias_invalidas_staging integer,
    status_importacao text NOT NULL DEFAULT 'pendente',
    status_validacao text NOT NULL DEFAULT 'pendente',
    mensagem text,
    criado_em timestamp DEFAULT now(),
    atualizado_em timestamp DEFAULT now(),
    CONSTRAINT staging_importacao_status_importacao_check CHECK (
        status_importacao IN ('pendente', 'importado', 'erro', 'cancelado')
    ),
    CONSTRAINT staging_importacao_status_validacao_check CHECK (
        status_validacao IN ('pendente', 'valido', 'geometria_invalida', 'erro_leitura', 'revisar_crs', 'sem_geometria')
    )
);

CREATE INDEX IF NOT EXISTS idx_staging_importacao_inventario
    ON importacao.staging_importacao(inventario_arquivo_id);

CREATE INDEX IF NOT EXISTS idx_staging_importacao_lote
    ON importacao.staging_importacao(lote_id);

CREATE INDEX IF NOT EXISTS idx_staging_importacao_tabela
    ON importacao.staging_importacao(schema_staging, tabela_staging);

CREATE INDEX IF NOT EXISTS idx_staging_importacao_criado_em
    ON importacao.staging_importacao(criado_em);

-- A view e removida e recriada porque CREATE OR REPLACE VIEW nao permite
-- alterar ordem ou nomes de colunas quando a view ja existe.
DROP VIEW IF EXISTS importacao.vw_staging_importacoes;

CREATE VIEW importacao.vw_staging_importacoes AS
SELECT
    si.id AS staging_importacao_id,
    si.inventario_arquivo_id,
    si.lote_id,
    li.nome_lote,
    ia.nome_arquivo,
    ia.nome_original_upload,
    ia.caminho_temporario,
    si.nome_original,
    si.layer_name,
    si.hash_arquivo,
    left(si.hash_arquivo, 12) AS hash_abreviado,
    si.schema_staging,
    si.tabela_staging,
    si.srid_origem,
    si.srid_destino,
    si.tipo_geometria,
    si.numero_feicoes_origem,
    si.numero_feicoes_staging,
    si.geometrias_invalidas_origem,
    si.geometrias_invalidas_staging,
    si.status_importacao,
    si.status_validacao,
    si.mensagem,
    ia.status_validacao AS status_validacao_inventario,
    ia.schema_destino_sugerido,
    ia.tabela_destino_sugerida,
    ia.grupo_sugerido,
    ia.tema_sugerido,
    ia.subtema_sugerido,
    si.criado_em,
    si.atualizado_em
FROM importacao.staging_importacao AS si
INNER JOIN importacao.inventario_arquivo AS ia
    ON ia.id = si.inventario_arquivo_id
INNER JOIN importacao.lote_importacao AS li
    ON li.id = si.lote_id;

-- Consultas de conferencia para execucao manual futura:
-- SELECT *
-- FROM importacao.vw_staging_importacoes
-- ORDER BY criado_em DESC
-- LIMIT 20;
--
-- SELECT status_importacao, status_validacao, count(*)
-- FROM importacao.staging_importacao
-- GROUP BY status_importacao, status_validacao
-- ORDER BY status_importacao, status_validacao;
