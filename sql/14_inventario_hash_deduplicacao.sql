    -- EA2S SIG - Inventario: hash e deduplicacao
    --
    -- Complemento seguro ao sql/13_inventario_bases_geograficas.sql.
    -- Nao importa dados, nao apaga registros e nao altera schemas oficiais.
    -- O controle principal de duplicidade permanece no Streamlit; os indices abaixo
    -- apoiam consulta por hash e auditoria de inventarios ja registrados.

    ALTER TABLE importacao.inventario_arquivo
        ADD COLUMN IF NOT EXISTS hash_arquivo text;

    ALTER TABLE importacao.inventario_arquivo
        ADD COLUMN IF NOT EXISTS layer_name text;

    ALTER TABLE importacao.inventario_arquivo
        ADD COLUMN IF NOT EXISTS nome_original_upload text;

    ALTER TABLE importacao.inventario_arquivo
        ADD COLUMN IF NOT EXISTS registrado_por text;

    ALTER TABLE importacao.inventario_arquivo
        ADD COLUMN IF NOT EXISTS permitir_duplicado boolean DEFAULT false;

    CREATE INDEX IF NOT EXISTS idx_inventario_arquivo_hash_arquivo
        ON importacao.inventario_arquivo(hash_arquivo);

    CREATE INDEX IF NOT EXISTS idx_inventario_arquivo_nome_arquivo
        ON importacao.inventario_arquivo(nome_arquivo);

    CREATE INDEX IF NOT EXISTS idx_inventario_arquivo_layer_name
        ON importacao.inventario_arquivo(layer_name);

    CREATE INDEX IF NOT EXISTS idx_inventario_arquivo_hash_nome_layer
        ON importacao.inventario_arquivo(hash_arquivo, nome_arquivo, layer_name);

    -- Nao foi criado indice unico parcial nesta primeira versao para preservar a
    -- possibilidade de registrar duplicados autorizados. A prevencao de duplicidade
    -- acidental fica no Streamlit, usando hash SHA256 e confirmacao explicita.

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
        a.caminho_temporario,
        a.tamanho_bytes,
        a.crs_original,
        a.srid_detectado,
        a.tipo_geometria,
        a.numero_feicoes,
        a.numero_campos,
        a.campos,
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
        a.hash_arquivo,
        a.layer_name,
        a.nome_original_upload,
        a.registrado_por,
        a.permitir_duplicado,
        a.observacao AS observacao_arquivo,
        a.criado_em
    FROM importacao.lote_importacao AS l
    INNER JOIN importacao.inventario_arquivo AS a
        ON a.lote_id = l.id;

    -- Consultas de conferencia para execucao manual futura:
    -- SELECT
    --     inventario_arquivo_id,
    --     lote_id,
    --     nome_lote,
    --     nome_arquivo,
    --     left(hash_arquivo, 12) AS hash_abreviado,
    --     layer_name,
    --     grupo_sugerido,
    --     tema_sugerido,
    --     schema_destino_sugerido,
    --     tabela_destino_sugerida,
    --     status_validacao,
    --     criado_em
    -- FROM importacao.vw_inventario_bases_geograficas
    -- ORDER BY criado_em DESC
    -- LIMIT 20;
    --
    -- SELECT
    --     hash_arquivo,
    --     layer_name,
    --     nome_arquivo,
    --     count(*) AS total_registros
    -- FROM importacao.inventario_arquivo
    -- WHERE hash_arquivo IS NOT NULL
    -- GROUP BY hash_arquivo, layer_name, nome_arquivo
    -- HAVING count(*) > 1
    -- ORDER BY total_registros DESC;