-- sql/18_importacao_direta_schema_oficial.sql
--
-- Primeira proposta local para o fluxo simplificado de importacao oficial.
-- Nao executar automaticamente. Aplicar manualmente apenas com autorizacao explicita.
--
-- Escopo:
-- - cria tabela de controle importacao.importacao_oficial;
-- - cria view tecnica importacao.vw_importacoes_oficiais;
-- - nao cria, apaga ou altera tabelas nos schemas oficiais;
-- - nao usa DROP TABLE, DELETE, TRUNCATE ou CASCADE;
-- - a criacao da camada oficial ocorre somente pela interface/funcoes Python,
--   mediante confirmacao explicita e sempre como nova tabela.

CREATE TABLE IF NOT EXISTS importacao.importacao_oficial (
    id bigserial PRIMARY KEY,
    inventario_arquivo_id bigint NOT NULL,
    lote_id bigint NOT NULL,
    schema_destino text NOT NULL,
    tabela_destino text NOT NULL,
    nome_camada text,
    grupo text,
    tema text,
    subtema text,
    fonte text,
    orgao_produtor text,
    ano_referencia integer,
    hash_arquivo text,
    srid integer DEFAULT 31982,
    tipo_geometria text,
    numero_feicoes bigint,
    geometrias_invalidas_antes integer,
    geometrias_invalidas_depois integer,
    corrigiu_geometrias boolean DEFAULT false,
    metodo_correcao_geometria text,
    status_qualidade text NOT NULL DEFAULT 'bloqueado',
    status_importacao text NOT NULL DEFAULT 'pendente',
    mensagem text,
    avisos jsonb DEFAULT '[]'::jsonb,
    pode_usar_diagnostico boolean DEFAULT false,
    cadastrada_em_config boolean DEFAULT false,
    camada_analise_id bigint,
    config_ativo boolean DEFAULT false,
    importado_por text,
    criado_em timestamp DEFAULT now(),
    atualizado_em timestamp DEFAULT now(),
    CONSTRAINT importacao_oficial_status_qualidade_check CHECK (
        status_qualidade IN ('valido', 'importado_com_pendencias', 'bloqueado')
    ),
    CONSTRAINT importacao_oficial_status_importacao_check CHECK (
        status_importacao IN ('pendente', 'importado', 'erro', 'cancelado')
    )
);

ALTER TABLE importacao.importacao_oficial
    ADD COLUMN IF NOT EXISTS inventario_arquivo_id bigint,
    ADD COLUMN IF NOT EXISTS lote_id bigint,
    ADD COLUMN IF NOT EXISTS schema_destino text,
    ADD COLUMN IF NOT EXISTS tabela_destino text,
    ADD COLUMN IF NOT EXISTS nome_camada text,
    ADD COLUMN IF NOT EXISTS grupo text,
    ADD COLUMN IF NOT EXISTS tema text,
    ADD COLUMN IF NOT EXISTS subtema text,
    ADD COLUMN IF NOT EXISTS fonte text,
    ADD COLUMN IF NOT EXISTS orgao_produtor text,
    ADD COLUMN IF NOT EXISTS ano_referencia integer,
    ADD COLUMN IF NOT EXISTS hash_arquivo text,
    ADD COLUMN IF NOT EXISTS srid integer DEFAULT 31982,
    ADD COLUMN IF NOT EXISTS tipo_geometria text,
    ADD COLUMN IF NOT EXISTS numero_feicoes bigint,
    ADD COLUMN IF NOT EXISTS geometrias_invalidas_antes integer,
    ADD COLUMN IF NOT EXISTS geometrias_invalidas_depois integer,
    ADD COLUMN IF NOT EXISTS corrigiu_geometrias boolean DEFAULT false,
    ADD COLUMN IF NOT EXISTS metodo_correcao_geometria text,
    ADD COLUMN IF NOT EXISTS status_qualidade text DEFAULT 'bloqueado',
    ADD COLUMN IF NOT EXISTS status_importacao text DEFAULT 'pendente',
    ADD COLUMN IF NOT EXISTS mensagem text,
    ADD COLUMN IF NOT EXISTS avisos jsonb DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS pode_usar_diagnostico boolean DEFAULT false,
    ADD COLUMN IF NOT EXISTS cadastrada_em_config boolean DEFAULT false,
    ADD COLUMN IF NOT EXISTS camada_analise_id bigint,
    ADD COLUMN IF NOT EXISTS config_ativo boolean DEFAULT false,
    ADD COLUMN IF NOT EXISTS importado_por text,
    ADD COLUMN IF NOT EXISTS criado_em timestamp DEFAULT now(),
    ADD COLUMN IF NOT EXISTS atualizado_em timestamp DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_importacao_oficial_inventario
    ON importacao.importacao_oficial(inventario_arquivo_id);

CREATE INDEX IF NOT EXISTS idx_importacao_oficial_lote
    ON importacao.importacao_oficial(lote_id);

CREATE INDEX IF NOT EXISTS idx_importacao_oficial_destino
    ON importacao.importacao_oficial(schema_destino, tabela_destino);

CREATE INDEX IF NOT EXISTS idx_importacao_oficial_status_qualidade
    ON importacao.importacao_oficial(status_qualidade);

CREATE INDEX IF NOT EXISTS idx_importacao_oficial_status_importacao
    ON importacao.importacao_oficial(status_importacao);

CREATE INDEX IF NOT EXISTS idx_importacao_oficial_criado_em
    ON importacao.importacao_oficial(criado_em);

-- A view e removida e recriada porque CREATE OR REPLACE VIEW nao permite
-- alterar ordem ou nomes de colunas quando a view ja existe.
DROP VIEW IF EXISTS importacao.vw_importacoes_oficiais;

CREATE VIEW importacao.vw_importacoes_oficiais AS
SELECT
    io.id AS importacao_oficial_id,
    io.inventario_arquivo_id,
    io.lote_id,
    li.nome_lote,
    ia.nome_arquivo,
    ia.nome_original_upload,
    io.hash_arquivo,
    left(io.hash_arquivo, 12) AS hash_abreviado,
    io.schema_destino,
    io.tabela_destino,
    io.nome_camada,
    io.grupo,
    io.tema,
    io.subtema,
    io.fonte,
    io.orgao_produtor,
    io.ano_referencia,
    io.srid,
    io.tipo_geometria,
    io.numero_feicoes,
    io.geometrias_invalidas_antes,
    io.geometrias_invalidas_depois,
    io.corrigiu_geometrias,
    io.metodo_correcao_geometria,
    io.status_qualidade,
    io.status_importacao,
    io.mensagem,
    io.avisos,
    io.pode_usar_diagnostico,
    io.cadastrada_em_config,
    io.camada_analise_id,
    io.config_ativo,
    io.importado_por,
    io.criado_em,
    io.atualizado_em
FROM importacao.importacao_oficial AS io
INNER JOIN importacao.inventario_arquivo AS ia
    ON ia.id = io.inventario_arquivo_id
INNER JOIN importacao.lote_importacao AS li
    ON li.id = io.lote_id;

-- Consultas de conferencia para execucao manual futura:
-- SELECT *
-- FROM importacao.vw_importacoes_oficiais
-- ORDER BY criado_em DESC
-- LIMIT 20;
--
-- SELECT status_qualidade, status_importacao, count(*)
-- FROM importacao.importacao_oficial
-- GROUP BY status_qualidade, status_importacao
-- ORDER BY status_qualidade, status_importacao;
