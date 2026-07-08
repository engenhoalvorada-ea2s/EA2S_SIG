-- EA2S SIG - Perfilamento de atributos de bases inventariadas
--
-- Proposta segura para registrar tipos sugeridos/confirmados de campos
-- antes de importacao para staging, exportacao ou promocao oficial.
--
-- Este script cria objetos apenas no schema operacional importacao.
-- Nao importa dados, nao altera schemas oficiais e nao apaga registros.

CREATE SCHEMA IF NOT EXISTS importacao;

CREATE TABLE IF NOT EXISTS importacao.perfil_atributo (
    id bigserial PRIMARY KEY,
    inventario_arquivo_id bigint NOT NULL REFERENCES importacao.inventario_arquivo(id),
    nome_campo text NOT NULL,
    tipo_original text,
    tipo_sugerido text,
    tipo_confirmado text,
    categoria_uso text,
    total_registros bigint,
    nulos bigint,
    nao_nulos bigint,
    valores_unicos bigint,
    exemplos_valores jsonb,
    percentual_conversao numeric,
    min_num numeric,
    max_num numeric,
    media_num numeric,
    min_data timestamp,
    max_data timestamp,
    usar_dashboard boolean DEFAULT false,
    usar_grafico boolean DEFAULT true,
    usar_mapa_popup boolean DEFAULT false,
    usar_exportacao boolean DEFAULT true,
    observacao text,
    criado_em timestamp DEFAULT now(),
    atualizado_em timestamp DEFAULT now(),
    CONSTRAINT perfil_atributo_tipo_sugerido_check CHECK (
        tipo_sugerido IS NULL OR tipo_sugerido IN (
            'texto', 'categoria', 'inteiro', 'decimal', 'monetario',
            'percentual', 'data', 'booleano', 'codigo', 'ignorar'
        )
    ),
    CONSTRAINT perfil_atributo_tipo_confirmado_check CHECK (
        tipo_confirmado IS NULL OR tipo_confirmado IN (
            'texto', 'categoria', 'inteiro', 'decimal', 'monetario',
            'percentual', 'data', 'booleano', 'codigo', 'ignorar'
        )
    ),
    CONSTRAINT perfil_atributo_categoria_uso_check CHECK (
        categoria_uso IS NULL OR categoria_uso IN (
            'identificador', 'classificacao', 'medida', 'temporal',
            'descricao', 'ignorar', 'outro'
        )
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_perfil_atributo_inventario_campo_unico
    ON importacao.perfil_atributo(inventario_arquivo_id, nome_campo);

CREATE INDEX IF NOT EXISTS idx_perfil_atributo_inventario_id
    ON importacao.perfil_atributo(inventario_arquivo_id);

CREATE INDEX IF NOT EXISTS idx_perfil_atributo_tipo_confirmado
    ON importacao.perfil_atributo(tipo_confirmado);

CREATE INDEX IF NOT EXISTS idx_perfil_atributo_categoria_uso
    ON importacao.perfil_atributo(categoria_uso);

CREATE TABLE IF NOT EXISTS importacao.regra_conversao_atributo (
    id bigserial PRIMARY KEY,
    inventario_arquivo_id bigint REFERENCES importacao.inventario_arquivo(id),
    nome_campo text NOT NULL,
    tipo_destino text NOT NULL,
    expressao_conversao text,
    separador_decimal text,
    separador_milhar text,
    remover_prefixos jsonb,
    remover_sufixos jsonb,
    tratar_vazio_como_null boolean DEFAULT true,
    ativo boolean DEFAULT true,
    criado_em timestamp DEFAULT now(),
    atualizado_em timestamp DEFAULT now(),
    CONSTRAINT regra_conversao_tipo_destino_check CHECK (
        tipo_destino IN (
            'texto', 'categoria', 'inteiro', 'decimal', 'monetario',
            'percentual', 'data', 'booleano', 'codigo', 'ignorar'
        )
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_regra_conversao_inventario_campo_unico
    ON importacao.regra_conversao_atributo(inventario_arquivo_id, nome_campo);

CREATE INDEX IF NOT EXISTS idx_regra_conversao_inventario_id
    ON importacao.regra_conversao_atributo(inventario_arquivo_id);

CREATE INDEX IF NOT EXISTS idx_regra_conversao_ativo
    ON importacao.regra_conversao_atributo(ativo);

-- A view e removida e recriada para permitir ajuste futuro de ordem
-- ou nomes de colunas sem tocar em dados das tabelas base.
DROP VIEW IF EXISTS importacao.vw_perfil_atributos_inventario;

CREATE VIEW importacao.vw_perfil_atributos_inventario AS
SELECT
    li.id AS lote_id,
    li.nome_lote,
    li.status AS status_lote,
    ia.id AS inventario_arquivo_id,
    ia.nome_arquivo,
    ia.hash_arquivo,
    left(ia.hash_arquivo, 12) AS hash_abreviado,
    ia.layer_name,
    ia.grupo_sugerido,
    ia.tema_sugerido,
    ia.schema_destino_sugerido,
    ia.tabela_destino_sugerida,
    pa.id AS perfil_atributo_id,
    pa.nome_campo,
    pa.tipo_original,
    pa.tipo_sugerido,
    pa.tipo_confirmado,
    pa.categoria_uso,
    pa.percentual_conversao,
    pa.valores_unicos,
    pa.nulos,
    pa.usar_dashboard,
    pa.usar_grafico,
    pa.usar_mapa_popup,
    pa.usar_exportacao,
    pa.criado_em
FROM importacao.perfil_atributo AS pa
INNER JOIN importacao.inventario_arquivo AS ia
    ON ia.id = pa.inventario_arquivo_id
INNER JOIN importacao.lote_importacao AS li
    ON li.id = ia.lote_id;

-- Consultas de conferencia para execucao manual futura:
-- SELECT
--     inventario_arquivo_id,
--     nome_arquivo,
--     nome_campo,
--     tipo_original,
--     tipo_sugerido,
--     tipo_confirmado,
--     categoria_uso,
--     percentual_conversao
-- FROM importacao.vw_perfil_atributos_inventario
-- ORDER BY inventario_arquivo_id DESC, nome_campo;
--
-- SELECT
--     inventario_arquivo_id,
--     tipo_confirmado,
--     count(*) AS total_campos
-- FROM importacao.perfil_atributo
-- GROUP BY inventario_arquivo_id, tipo_confirmado
-- ORDER BY inventario_arquivo_id DESC, tipo_confirmado;