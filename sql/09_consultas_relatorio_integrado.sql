-- ============================================================================
-- EA2S SIG - MVP Diagnostico Territorial
-- Script 09 - Consultas integradas para relatorio tecnico
-- ============================================================================
-- Objetivo:
-- Consolidar, em views finais de apresentacao, as saidas fisico-bioticas e
-- socioeconomicas organizadas pelos scripts 07 e 08.
--
-- Regras deste script:
-- - nao recalcula intersecoes, indicadores ou areas;
-- - nao cria tabelas fisicas;
-- - nao altera tabelas-base;
-- - nao altera schemas oficiais;
-- - mantem resultados separados por execucao_id, projeto_id e area_interesse_id.
-- ============================================================================

-- ============================================================================
-- 1. Contexto geral de execucao, projeto e area de interesse
-- ============================================================================

CREATE OR REPLACE VIEW resultados.vw_relatorio_contexto_projeto AS
SELECT
    e.id AS execucao_id,
    e.nome AS nome_execucao,
    e.tipo_execucao,
    e.status AS status_execucao,
    e.iniciado_em,
    e.finalizado_em,
    e.usuario,
    e.mensagem,
    p.id AS projeto_id,
    p.codigo AS codigo_projeto,
    p.nome AS nome_projeto,
    p.cliente,
    p.municipio,
    p.uf,
    p.atividade,
    p.tipo_estudo,
    p.responsavel,
    ai.id AS area_interesse_id,
    ai.nome AS nome_area_interesse,
    ai.tipo AS tipo_area_interesse,
    ai.area_m2 AS area_interesse_m2,
    ai.area_ha AS area_interesse_ha
FROM resultados.execucao AS e
INNER JOIN projetos.projeto AS p
    ON p.id = e.projeto_id
INNER JOIN projetos.area_interesse AS ai
    ON ai.projeto_id = p.id;

-- ============================================================================
-- 2. Fisico-biotico consolidado - area de interesse
-- ============================================================================

CREATE OR REPLACE VIEW resultados.vw_relatorio_fisico_biotico_area_interesse AS
SELECT
    fb.execucao_id,
    fb.projeto_id,
    ctx.codigo_projeto,
    ctx.nome_projeto,
    ctx.cliente,
    ctx.municipio,
    ctx.uf,
    fb.area_interesse_id,
    ctx.nome_area_interesse,
    fb.unidade_analise,
    fb.unidade_analise_nome,
    fb.tema,
    fb.campo_principal,
    fb.valor_principal,
    fb.area_m2,
    fb.area_ha,
    fb.percentual_unidade_analise
FROM resultados.vw_fisico_biotico_classes AS fb
LEFT JOIN resultados.vw_relatorio_contexto_projeto AS ctx
    ON ctx.execucao_id = fb.execucao_id
   AND ctx.projeto_id = fb.projeto_id
   AND ctx.area_interesse_id = fb.area_interesse_id
WHERE fb.unidade_analise = 'area_interesse';

-- ============================================================================
-- 3. Fisico-biotico consolidado - buffer de 1000 m
-- ============================================================================

CREATE OR REPLACE VIEW resultados.vw_relatorio_fisico_biotico_buffer_1000m AS
SELECT
    fb.execucao_id,
    fb.projeto_id,
    ctx.codigo_projeto,
    ctx.nome_projeto,
    ctx.cliente,
    ctx.municipio,
    ctx.uf,
    fb.area_interesse_id,
    ctx.nome_area_interesse,
    fb.unidade_analise,
    fb.unidade_analise_nome,
    fb.tema,
    fb.campo_principal,
    fb.valor_principal,
    fb.area_m2,
    fb.area_ha,
    fb.percentual_unidade_analise
FROM resultados.vw_fisico_biotico_classes AS fb
LEFT JOIN resultados.vw_relatorio_contexto_projeto AS ctx
    ON ctx.execucao_id = fb.execucao_id
   AND ctx.projeto_id = fb.projeto_id
   AND ctx.area_interesse_id = fb.area_interesse_id
WHERE fb.unidade_analise = 'buffer_1000m';

-- ============================================================================
-- 4. Fisico-biotico consolidado - microbacias interceptadas
-- ============================================================================

CREATE OR REPLACE VIEW resultados.vw_relatorio_fisico_biotico_microbacias AS
SELECT
    fb.execucao_id,
    fb.projeto_id,
    ctx.codigo_projeto,
    ctx.nome_projeto,
    ctx.cliente,
    ctx.municipio,
    ctx.uf,
    fb.area_interesse_id,
    ctx.nome_area_interesse,
    fb.unidade_analise,
    fb.unidade_analise_codigo AS cd_micro,
    fb.unidade_analise_nome AS nm_micro,
    fb.tema,
    fb.campo_principal,
    fb.valor_principal,
    fb.area_m2,
    fb.area_ha,
    fb.percentual_unidade_analise
FROM resultados.vw_fisico_biotico_classes AS fb
LEFT JOIN resultados.vw_relatorio_contexto_projeto AS ctx
    ON ctx.execucao_id = fb.execucao_id
   AND ctx.projeto_id = fb.projeto_id
   AND ctx.area_interesse_id = fb.area_interesse_id
WHERE fb.unidade_analise = 'microbacia';

-- ============================================================================
-- 5. Identificacao das microbacias analisadas
-- ============================================================================

CREATE OR REPLACE VIEW resultados.vw_relatorio_microbacias_identificacao AS
SELECT
    mb.execucao_id,
    mb.projeto_id,
    ctx.codigo_projeto,
    ctx.nome_projeto,
    ctx.cliente,
    ctx.municipio,
    ctx.uf,
    mb.area_interesse_id,
    ctx.nome_area_interesse,
    mb.cd_micro,
    mb.nm_micro,
    mb.nm_rio_pri,
    mb.cd_bacia,
    mb.cd_ibge_mu,
    mb.sg_tipo,
    mb.vl_qmin7,
    mb.nm_qmin7,
    mb.vl_qrest,
    mb.vl_qsubt,
    mb.shape_area,
    mb.shape_len
FROM resultados.vw_tabela_microbacias_fisico_biotico AS mb
LEFT JOIN resultados.vw_relatorio_contexto_projeto AS ctx
    ON ctx.execucao_id = mb.execucao_id
   AND ctx.projeto_id = mb.projeto_id
   AND ctx.area_interesse_id = mb.area_interesse_id;

-- ============================================================================
-- 6. Socioeconomico por setor censitario interceptado
-- ============================================================================

CREATE OR REPLACE VIEW resultados.vw_relatorio_socio_contexto_setores AS
SELECT
    sc.execucao_id,
    sc.projeto_id,
    sc.codigo_projeto,
    sc.nome_projeto,
    sc.cliente,
    sc.municipio,
    sc.uf,
    sc.area_interesse_id,
    sc.nome_area_interesse,
    sc.cd_setor,
    sc.area_intersecao_ha,
    sc.percentual_area_interesse,
    sc.populacao_total_setor,
    sc.total_domicilios_setor,
    sc.domicilios_particulares_ocupados_setor,
    sc.domicilios_particulares_permanentes_ocupados_setor,
    sc.moradores_domicilios_particulares_permanentes_ocupados_setor,
    sc.media_moradores_por_domicilio_setor,
    sc.responsaveis_dppo_setor,
    sc.renda_media_responsavel_setor,
    sc.renda_mediana_responsavel_setor,
    sc.agua_rede_geral_setor,
    sc.lixo_coletado_domicilio_setor,
    sc.esgoto_fossa_septica_nao_ligada_rede_setor,
    sc.possui_dados_basicos,
    sc.possui_dados_dppo,
    sc.possui_dados_renda,
    sc.possui_dados_saneamento,
    sc.status_dados_setor
FROM resultados.vw_socio_contexto_setores AS sc;

-- ============================================================================
-- 7. Socioeconomico consolidado dos setores censitarios interceptados
-- ============================================================================

-- Pendencias de colunas ainda nao presentes em resultados.vw_socio_contexto_setores_total:
-- - percentual_domicilios_agua_rede_geral
-- - percentual_domicilios_lixo_coletado
-- - percentual_domicilios_esgoto_fossa_septica_nao_ligada_rede
-- - media_moradores_por_domicilio_contexto
-- Para evitar erro de coluna inexistente, estes campos nao sao forcados nesta view.

CREATE OR REPLACE VIEW resultados.vw_relatorio_socio_total_setores AS
SELECT
    st.execucao_id,
    st.projeto_id,
    st.codigo_projeto,
    st.nome_projeto,
    st.cliente,
    st.municipio,
    st.uf,
    st.area_interesse_id,
    st.nome_area_interesse,
    st.numero_setores_intersectados,
    st.setores_com_dados_basicos,
    st.setores_com_dados_dppo,
    st.setores_com_dados_renda,
    st.setores_com_dados_saneamento,
    st.setores_com_dados_completos,
    st.setores_com_dados_parciais,
    st.area_interesse_intersectada_ha,
    st.populacao_total_setores,
    st.total_domicilios_setores,
    st.domicilios_particulares_ocupados_setores,
    st.domicilios_particulares_permanentes_ocupados_setores,
    st.moradores_domicilios_particulares_permanentes_ocupados_setores,
    st.responsaveis_dppo_setores,
    st.agua_rede_geral_setores,
    st.lixo_coletado_domicilio_setores,
    st.esgoto_fossa_septica_nao_ligada_rede_setores,
    st.renda_media_responsavel_media_setores,
    st.renda_media_responsavel_ponderada_responsaveis,
    st.renda_mediana_responsavel_media_setores
FROM resultados.vw_socio_contexto_setores_total AS st;

-- ============================================================================
-- 8. Sintese executiva integrada
-- ============================================================================

CREATE OR REPLACE VIEW resultados.vw_relatorio_sintese_executiva AS
WITH fisico_area AS (
    SELECT
        fb.execucao_id,
        fb.projeto_id,
        fb.area_interesse_id,
        fb.tema,
        fb.valor_principal,
        fb.area_ha,
        row_number() OVER (
            PARTITION BY fb.execucao_id, fb.projeto_id, fb.area_interesse_id, fb.tema
            ORDER BY fb.area_ha DESC NULLS LAST, fb.valor_principal
        ) AS rn
    FROM resultados.vw_fisico_biotico_classes AS fb
    WHERE fb.unidade_analise = 'area_interesse'
),
classes_predominantes AS (
    SELECT
        fa.execucao_id,
        fa.projeto_id,
        fa.area_interesse_id,
        max(fa.valor_principal) FILTER (WHERE fa.tema = 'geologia' AND fa.rn = 1) AS geologia_predominante,
        max(fa.valor_principal) FILTER (WHERE fa.tema = 'geomorfologia' AND fa.rn = 1) AS geomorfologia_predominante,
        max(fa.valor_principal) FILTER (WHERE fa.tema = 'hidrogeologia' AND fa.rn = 1) AS hidrogeologia_predominante,
        max(fa.valor_principal) FILTER (WHERE fa.tema = 'pedologia' AND fa.rn = 1) AS pedologia_predominante,
        max(fa.valor_principal) FILTER (WHERE fa.tema = 'vegetacao' AND fa.rn = 1) AS vegetacao_predominante
    FROM fisico_area AS fa
    WHERE fa.rn = 1
    GROUP BY
        fa.execucao_id,
        fa.projeto_id,
        fa.area_interesse_id
),
microbacias AS (
    SELECT
        mb.execucao_id,
        mb.projeto_id,
        mb.area_interesse_id,
        count(DISTINCT mb.cd_micro) AS numero_microbacias_interceptadas,
        string_agg(DISTINCT mb.nm_micro, '; ' ORDER BY mb.nm_micro) AS microbacias_interceptadas
    FROM resultados.vw_tabela_microbacias_fisico_biotico AS mb
    GROUP BY
        mb.execucao_id,
        mb.projeto_id,
        mb.area_interesse_id
)
SELECT
    ctx.execucao_id,
    ctx.projeto_id,
    ctx.codigo_projeto,
    ctx.nome_projeto,
    ctx.cliente,
    ctx.municipio,
    ctx.uf,
    ctx.area_interesse_id,
    ctx.nome_area_interesse,
    ctx.area_interesse_ha,
    st.numero_setores_intersectados,
    st.populacao_total_setores,
    st.total_domicilios_setores,
    st.domicilios_particulares_permanentes_ocupados_setores,
    st.renda_media_responsavel_ponderada_responsaveis,
    st.setores_com_dados_completos,
    st.setores_com_dados_parciais,
    mb.numero_microbacias_interceptadas,
    mb.microbacias_interceptadas,
    cp.geologia_predominante,
    cp.geomorfologia_predominante,
    cp.hidrogeologia_predominante,
    cp.pedologia_predominante,
    cp.vegetacao_predominante
FROM resultados.vw_relatorio_contexto_projeto AS ctx
LEFT JOIN resultados.vw_socio_contexto_setores_total AS st
    ON st.execucao_id = ctx.execucao_id
   AND st.projeto_id = ctx.projeto_id
   AND st.area_interesse_id = ctx.area_interesse_id
LEFT JOIN microbacias AS mb
    ON mb.execucao_id = ctx.execucao_id
   AND mb.projeto_id = ctx.projeto_id
   AND mb.area_interesse_id = ctx.area_interesse_id
LEFT JOIN classes_predominantes AS cp
    ON cp.execucao_id = ctx.execucao_id
   AND cp.projeto_id = ctx.projeto_id
   AND cp.area_interesse_id = ctx.area_interesse_id;

-- ============================================================================
-- 9. Consultas de conferencia para uso manual apos execucao autorizada
-- ============================================================================

/*
-- Conferir contexto do projeto, execucao e area de interesse
SELECT *
FROM resultados.vw_relatorio_contexto_projeto
WHERE execucao_id = 4
  AND projeto_id = 1
  AND area_interesse_id = 1;

-- Conferir classes fisico-bioticas da area de interesse
SELECT *
FROM resultados.vw_relatorio_fisico_biotico_area_interesse
WHERE execucao_id = 4
  AND projeto_id = 1
  AND area_interesse_id = 1
ORDER BY tema, area_ha DESC;

-- Conferir classes fisico-bioticas do buffer de 1000 m
SELECT *
FROM resultados.vw_relatorio_fisico_biotico_buffer_1000m
WHERE execucao_id = 4
  AND projeto_id = 1
  AND area_interesse_id = 1
ORDER BY tema, area_ha DESC;

-- Conferir classes fisico-bioticas das microbacias
SELECT *
FROM resultados.vw_relatorio_fisico_biotico_microbacias
WHERE execucao_id = 4
  AND projeto_id = 1
  AND area_interesse_id = 1
ORDER BY nm_micro, tema, area_ha DESC;

-- Conferir contexto socioeconomico por setor censitario interceptado
SELECT *
FROM resultados.vw_relatorio_socio_contexto_setores
WHERE execucao_id = 4
  AND projeto_id = 1
  AND area_interesse_id = 1
ORDER BY percentual_area_interesse DESC;

-- Conferir total socioeconomico dos setores censitarios interceptados
SELECT *
FROM resultados.vw_relatorio_socio_total_setores
WHERE execucao_id = 4
  AND projeto_id = 1
  AND area_interesse_id = 1;

-- Conferir sintese executiva integrada
SELECT *
FROM resultados.vw_relatorio_sintese_executiva
WHERE execucao_id = 4
  AND projeto_id = 1
  AND area_interesse_id = 1;
*/