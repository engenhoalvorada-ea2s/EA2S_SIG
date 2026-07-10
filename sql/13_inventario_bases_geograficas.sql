-- EA2S SIG - Inventario de bases geograficas
--
-- Proposta inicial segura para registrar metadados de bases espaciais
-- antes de qualquer importacao para staging ou promocao para schemas oficiais.
--
-- Este script NAO importa geometrias e NAO altera schemas oficiais como
-- geologia, geomorfologia, pedologia, vegetacao, hidrografia, urbano etc.

CREATE SCHEMA IF NOT EXISTS importacao;

CREATE TABLE IF NOT EXISTS importacao.lote_importacao (
    id bigserial PRIMARY KEY,
    nome_lote text NOT NULL,
    tipo_lote text DEFAULT 'base_geografica',
    origem text,
    responsavel text,
    status text DEFAULT 'inventariado',
    observacao text,
    criado_em timestamp DEFAULT now(),
    atualizado_em timestamp DEFAULT now(),
    CONSTRAINT lote_importacao_status_check CHECK (
        status IN (
            'inventariado',
            'validado',
            'reprovado',
            'importado_staging',
            'promovido_oficial',
            'arquivado'
        )
    )
);

CREATE TABLE IF NOT EXISTS importacao.inventario_arquivo (
    id bigserial PRIMARY KEY,
    lote_id bigint NOT NULL REFERENCES importacao.lote_importacao(id),
    nome_arquivo text NOT NULL,
    formato text,
    caminho_temporario text,
    tamanho_bytes bigint,
    crs_original text,
    srid_detectado integer,
    tipo_geometria text,
    numero_feicoes bigint,
    numero_campos integer,
    campos jsonb,
    bbox jsonb,
    area_total_ha numeric,
    comprimento_total_km numeric,
    tem_geometria boolean,
    geometria_valida boolean,
    tem_crs boolean,
    mensagem_validacao text,
    status_validacao text DEFAULT 'pendente',
    grupo_sugerido text,
    tema_sugerido text,
    subtema_sugerido text,
    schema_destino_sugerido text,
    tabela_destino_sugerida text,
    fonte text,
    orgao_produtor text,
    ano_referencia integer,
    observacao text,
    criado_em timestamp DEFAULT now(),
    atualizado_em timestamp DEFAULT now(),
    CONSTRAINT inventario_arquivo_status_validacao_check CHECK (
        status_validacao IN (
            'pendente',
            'valido',
            'revisar_crs',
            'geometria_invalida',
            'formato_invalido',
            'sem_geometria',
            'erro_leitura'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_inventario_arquivo_lote_id
    ON importacao.inventario_arquivo(lote_id);

CREATE INDEX IF NOT EXISTS idx_inventario_arquivo_status_validacao
    ON importacao.inventario_arquivo(status_validacao);

CREATE INDEX IF NOT EXISTS idx_inventario_arquivo_grupo_sugerido
    ON importacao.inventario_arquivo(grupo_sugerido);

CREATE INDEX IF NOT EXISTS idx_inventario_arquivo_tema_sugerido
    ON importacao.inventario_arquivo(tema_sugerido);

CREATE INDEX IF NOT EXISTS idx_inventario_arquivo_schema_destino_sugerido
    ON importacao.inventario_arquivo(schema_destino_sugerido);

CREATE INDEX IF NOT EXISTS idx_inventario_arquivo_criado_em
    ON importacao.inventario_arquivo(criado_em);

CREATE OR REPLACE VIEW importacao.vw_inventario_bases_geograficas AS
SELECT
    l.id AS lote_id,
    l.nome_lote,
    l.tipo_lote,
    l.origem,
    l.responsavel,
    l.status AS status_lote,
    l.observacao AS observacao_lote,
    l.criado_em AS lote_criado_em,
    a.id AS inventario_arquivo_id,
    a.nome_arquivo,
    a.formato,
    a.tamanho_bytes,
    a.crs_original,
    a.srid_detectado,
    a.tipo_geometria,
    a.numero_feicoes,
    a.numero_campos,
    a.bbox,
    a.area_total_ha,
    a.comprimento_total_km,
    a.tem_geometria,
    a.geometria_valida,
    a.tem_crs,
    a.status_validacao,
    a.mensagem_validacao,
    a.grupo_sugerido,
    a.tema_sugerido,
    a.subtema_sugerido,
    a.schema_destino_sugerido,
    a.tabela_destino_sugerida,
    a.fonte,
    a.orgao_produtor,
    a.ano_referencia,
    a.observacao AS observacao_arquivo,
    a.criado_em
FROM importacao.lote_importacao AS l
INNER JOIN importacao.inventario_arquivo AS a
    ON a.lote_id = l.id;

-- Consultas de conferencia para execucao manual futura:
-- SELECT
--     lote_id,
--     nome_lote,
--     inventario_arquivo_id,
--     nome_arquivo,
--     formato,
--     srid_detectado,
--     tipo_geometria,
--     numero_feicoes,
--     status_validacao,
--     grupo_sugerido,
--     tema_sugerido,
--     schema_destino_sugerido,
--     tabela_destino_sugerida,
--     criado_em
-- FROM importacao.vw_inventario_bases_geograficas
-- ORDER BY criado_em DESC
-- LIMIT 20;
-- SELECT status_validacao, count(*) FROM importacao.inventario_arquivo GROUP BY status_validacao;