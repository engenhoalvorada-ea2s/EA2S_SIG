-- sql/16_ajuste_view_inventario_criado_em.sql
--
-- Ajuste complementar local para padronizar a view de inventario.
-- Nao executar automaticamente. Aplicar manualmente apenas com autorizacao explicita.
--
-- Motivo:
-- Algumas versoes da view importacao.vw_inventario_bases_geograficas expuseram
-- apenas datas especificas, como lote_criado_em e arquivo_criado_em, enquanto o
-- app antigo consultava uma coluna generica criado_em. Como CREATE OR REPLACE
-- VIEW nao permite alterar ordem/nome de colunas de uma view existente em todos
-- os cenarios, a view e removida e recriada sem CASCADE.
--
-- Seguranca:
-- - Nao usa CASCADE.
-- - Nao usa DROP TABLE.
-- - Nao apaga dados.
-- - Nao altera schemas oficiais.
-- - Recria apenas view de apresentacao no schema importacao.

DROP VIEW IF EXISTS importacao.vw_inventario_bases_geograficas;

CREATE VIEW importacao.vw_inventario_bases_geograficas AS
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
    left(a.hash_arquivo, 12) AS hash_abreviado,
    a.layer_name,
    a.nome_original_upload,
    a.registrado_por,
    a.permitir_duplicado,
    a.observacao AS observacao_arquivo,
    a.criado_em AS arquivo_criado_em,
    COALESCE(a.criado_em, l.criado_em) AS criado_em
FROM importacao.lote_importacao AS l
INNER JOIN importacao.inventario_arquivo AS a
    ON a.lote_id = l.id;

-- Consultas de conferencia para execucao manual futura:
-- SELECT
--     lote_id,
--     inventario_arquivo_id,
--     nome_lote,
--     nome_arquivo,
--     nome_original_upload,
--     hash_abreviado,
--     layer_name,
--     grupo_sugerido,
--     tema_sugerido,
--     schema_destino_sugerido,
--     tabela_destino_sugerida,
--     status_validacao,
--     arquivo_criado_em,
--     criado_em
-- FROM importacao.vw_inventario_bases_geograficas
-- ORDER BY arquivo_criado_em DESC
-- LIMIT 20;
