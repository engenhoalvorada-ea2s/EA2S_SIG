/*
EA2S SIG - 08_tabelas_tecnicas_socioeconomico.sql

PROPOSTA LOCAL, AINDA NAO EXECUTADA.

Objetivo:
Criar views tecnicas de saida para o modulo socioeconomico do MVP a partir das
tabelas ja existentes no schema resultados.

Tabelas-base:
- resultados.setores_intersectados
- resultados.indicador_socioeconomico_detalhe
- resultados.indicador_socioeconomico_resumo

Tabelas de apoio:
- projetos.projeto
- projetos.area_interesse

Regras:
- nao recalcular dados;
- nao criar tabelas fisicas;
- nao criar objetos com nome de projeto;
- separar resultados por execucao_id, projeto_id e area_interesse_id;
- usar nome/codigo do projeto e nome da area apenas como campos nas views;
- nao alterar schemas oficiais.
*/

-- ============================================================================
-- 1. Setores censitarios intersectados - camada espacial para QGIS
-- ============================================================================

CREATE OR REPLACE VIEW resultados.vw_socio_setores_intersectados AS
SELECT
    si.execucao_id,
    si.projeto_id,
    p.codigo AS codigo_projeto,
    p.nome AS nome_projeto,
    p.cliente,
    p.municipio,
    p.uf,
    si.area_interesse_id,
    ai.nome AS nome_area_interesse,
    ai.tipo AS tipo_area_interesse,
    si.cd_setor,
    si.area_intersecao_m2,
    si.area_intersecao_ha,
    si.area_setor_total_m2,
    si.percentual_setor_intersectado,
    si.percentual_area_interesse,
    si.geom,
    si.data_cadastro
FROM resultados.setores_intersectados AS si
INNER JOIN projetos.projeto AS p
    ON p.id = si.projeto_id
INNER JOIN projetos.area_interesse AS ai
    ON ai.id = si.area_interesse_id
   AND ai.projeto_id = si.projeto_id;

-- ============================================================================
-- 2. Resumo tecnico dos indicadores socioeconomicos
-- ============================================================================

CREATE OR REPLACE VIEW resultados.vw_socio_indicadores_resumo AS
SELECT
    r.execucao_id,
    r.projeto_id,
    p.codigo AS codigo_projeto,
    p.nome AS nome_projeto,
    p.cliente,
    p.municipio,
    p.uf,
    r.area_interesse_id,
    ai.nome AS nome_area_interesse,
    ai.tipo AS tipo_area_interesse,
    r.indicador_id,
    r.nome_logico_indicador,
    r.tema,
    r.subtema,
    r.descricao,
    r.unidade,
    r.valor_estimado_total,
    r.valor_medio_ponderado,
    r.numero_setores,
    r.area_total_intersectada_m2,
    round((r.area_total_intersectada_m2 / 10000.0)::numeric, 6) AS area_total_intersectada_ha,
    r.metodo_estimativa,
    r.observacao,
    r.data_cadastro
FROM resultados.indicador_socioeconomico_resumo AS r
INNER JOIN projetos.projeto AS p
    ON p.id = r.projeto_id
INNER JOIN projetos.area_interesse AS ai
    ON ai.id = r.area_interesse_id
   AND ai.projeto_id = r.projeto_id;

-- ============================================================================
-- 3. Detalhe por setor censitario - auditoria dos indicadores
-- ============================================================================

CREATE OR REPLACE VIEW resultados.vw_socio_indicadores_detalhe_setor AS
SELECT
    d.execucao_id,
    d.projeto_id,
    p.codigo AS codigo_projeto,
    p.nome AS nome_projeto,
    p.cliente,
    p.municipio,
    p.uf,
    d.area_interesse_id,
    ai.nome AS nome_area_interesse,
    ai.tipo AS tipo_area_interesse,
    d.cd_setor,
    si.area_intersecao_m2,
    si.area_intersecao_ha,
    si.area_setor_total_m2,
    si.percentual_setor_intersectado,
    si.percentual_area_interesse,
    d.indicador_id,
    d.nome_logico_indicador,
    d.tema,
    d.subtema,
    d.tabela_origem,
    d.campo_origem,
    d.valor_original,
    d.valor_estimado,
    d.metodo_estimativa,
    d.observacao,
    d.data_cadastro
FROM resultados.indicador_socioeconomico_detalhe AS d
INNER JOIN projetos.projeto AS p
    ON p.id = d.projeto_id
INNER JOIN projetos.area_interesse AS ai
    ON ai.id = d.area_interesse_id
   AND ai.projeto_id = d.projeto_id
INNER JOIN resultados.setores_intersectados AS si
    ON si.execucao_id = d.execucao_id
   AND si.projeto_id = d.projeto_id
   AND si.area_interesse_id = d.area_interesse_id
   AND si.cd_setor = d.cd_setor;

-- ============================================================================
-- 4. Contexto socioeconomico dos setores censitarios interceptados
-- ============================================================================

/*
Estas views representam o contexto socioeconomico dos setores censitarios
interceptados pela area de interesse. Os valores populacionais, domiciliares e
de infraestrutura correspondem aos setores censitarios inteiros, nao a area
exata do poligono. Essa abordagem e mais adequada para areas ambientais, APPs,
glebas vazias ou areas onde a ponderacao proporcional por area nao representa a
ocupacao real.
*/

-- As duas views abaixo mudam estrutura de colunas durante a evolucao do MVP.
-- A ordem evita dependencia da view total sobre a view por setor.
DROP VIEW IF EXISTS resultados.vw_socio_contexto_setores_total;
DROP VIEW IF EXISTS resultados.vw_socio_contexto_setores;

CREATE OR REPLACE VIEW resultados.vw_socio_contexto_setores AS
WITH setor_contexto AS (
    SELECT
        si.execucao_id,
        si.projeto_id,
        p.codigo AS codigo_projeto,
        p.nome AS nome_projeto,
        p.cliente,
        p.municipio,
        p.uf,
        si.area_interesse_id,
        ai.nome AS nome_area_interesse,
        si.cd_setor,
        si.area_intersecao_m2,
        si.area_intersecao_ha,
        si.area_setor_total_m2,
        si.percentual_setor_intersectado,
        si.percentual_area_interesse,
        max(d.valor_original) FILTER (
            WHERE d.nome_logico_indicador = 'censo_total_pessoas'
        ) AS populacao_total_setor,
        max(d.valor_original) FILTER (
            WHERE d.nome_logico_indicador = 'censo_total_domicilios'
        ) AS total_domicilios_setor,
        max(d.valor_original) FILTER (
            WHERE d.nome_logico_indicador = 'censo_total_domicilios_particulares_ocupados'
        ) AS domicilios_particulares_ocupados_setor,
        max(d.valor_original) FILTER (
            WHERE d.nome_logico_indicador = 'dom_dppo_total'
        ) AS domicilios_particulares_permanentes_ocupados_setor,
        max(d.valor_original) FILTER (
            WHERE d.nome_logico_indicador = 'dom_dppo_moradores'
        ) AS moradores_domicilios_particulares_permanentes_ocupados_setor,
        max(d.valor_original) FILTER (
            WHERE d.nome_logico_indicador = 'censo_media_moradores_dpo'
        ) AS media_moradores_por_domicilio_setor,
        max(d.valor_original) FILTER (
            WHERE d.nome_logico_indicador = 'renda_media_responsavel'
        ) AS renda_media_responsavel_setor,
        max(d.valor_original) FILTER (
            WHERE d.nome_logico_indicador = 'renda_mediana_responsavel'
        ) AS renda_mediana_responsavel_setor,
        max(d.valor_original) FILTER (
            WHERE d.nome_logico_indicador = 'renda_responsaveis_dppo'
        ) AS responsaveis_dppo_setor,
        max(d.valor_original) FILTER (
            WHERE d.nome_logico_indicador = 'agua_rede_geral'
        ) AS agua_rede_geral_setor,
        max(d.valor_original) FILTER (
            WHERE d.nome_logico_indicador = 'lixo_coletado_domicilio_servico_limpeza'
        ) AS lixo_coletado_domicilio_setor,
        max(d.valor_original) FILTER (
            WHERE d.nome_logico_indicador = 'esgoto_fossa_septica_nao_ligada_rede'
        ) AS esgoto_fossa_septica_nao_ligada_rede_setor
    FROM resultados.setores_intersectados AS si
    INNER JOIN projetos.projeto AS p
        ON p.id = si.projeto_id
    INNER JOIN projetos.area_interesse AS ai
        ON ai.id = si.area_interesse_id
       AND ai.projeto_id = si.projeto_id
    LEFT JOIN resultados.indicador_socioeconomico_detalhe AS d
        ON d.execucao_id = si.execucao_id
       AND d.projeto_id = si.projeto_id
       AND d.area_interesse_id = si.area_interesse_id
       AND d.cd_setor = si.cd_setor
    GROUP BY
        si.execucao_id,
        si.projeto_id,
        p.codigo,
        p.nome,
        p.cliente,
        p.municipio,
        p.uf,
        si.area_interesse_id,
        ai.nome,
        si.cd_setor,
        si.area_intersecao_m2,
        si.area_intersecao_ha,
        si.area_setor_total_m2,
        si.percentual_setor_intersectado,
        si.percentual_area_interesse
),
disponibilidade AS (
    SELECT
        sc.*,
        CASE
            WHEN sc.populacao_total_setor IS NOT NULL
              OR sc.total_domicilios_setor IS NOT NULL
              OR sc.domicilios_particulares_ocupados_setor IS NOT NULL
            THEN true ELSE false
        END AS possui_dados_basicos,
        CASE
            WHEN sc.domicilios_particulares_permanentes_ocupados_setor IS NOT NULL
              OR sc.moradores_domicilios_particulares_permanentes_ocupados_setor IS NOT NULL
            THEN true ELSE false
        END AS possui_dados_dppo,
        CASE
            WHEN sc.renda_media_responsavel_setor IS NOT NULL
              OR sc.renda_mediana_responsavel_setor IS NOT NULL
              OR sc.responsaveis_dppo_setor IS NOT NULL
            THEN true ELSE false
        END AS possui_dados_renda,
        CASE
            WHEN sc.agua_rede_geral_setor IS NOT NULL
              OR sc.lixo_coletado_domicilio_setor IS NOT NULL
              OR sc.esgoto_fossa_septica_nao_ligada_rede_setor IS NOT NULL
            THEN true ELSE false
        END AS possui_dados_saneamento
    FROM setor_contexto AS sc
)
SELECT
    d.*,
    CASE
        WHEN d.possui_dados_basicos
         AND d.possui_dados_dppo
         AND d.possui_dados_renda
         AND d.possui_dados_saneamento
        THEN 'completo'
        ELSE 'parcial'
    END AS status_dados_setor
FROM disponibilidade AS d;
-- ============================================================================
-- 5. Total do contexto socioeconomico dos setores interceptados
-- ============================================================================

/*
Renda media e renda mediana nao devem ser somadas. Nesta view:

- renda_media_responsavel_media_setores representa media simples entre setores;
- renda_media_responsavel_ponderada_responsaveis pondera cada setor pelo numero
  de responsaveis em domicilios particulares permanentes ocupados, sendo a
  referencia preferencial para sintese territorial;
- renda_mediana_responsavel_media_setores representa media simples das medianas
  setoriais, apenas como referencia descritiva. Mediana nao e somavel nem
  ponderavel diretamente sem microdados.

Valores nulos representam ausencia de dado ou dado nao informado na base; nao
devem ser substituidos por zero. Os somatorios consideram apenas os setores com
dados disponiveis para cada indicador. Zeros devem ser interpretados como
valores efetivamente iguais a zero quando vierem da base original.
*/

CREATE OR REPLACE VIEW resultados.vw_socio_contexto_setores_total AS
SELECT
    c.execucao_id,
    c.projeto_id,
    c.codigo_projeto,
    c.nome_projeto,
    c.cliente,
    c.municipio,
    c.uf,
    c.area_interesse_id,
    c.nome_area_interesse,
    count(*) AS numero_setores_intersectados,
    count(*) FILTER (WHERE c.possui_dados_basicos) AS setores_com_dados_basicos,
    count(*) FILTER (WHERE c.possui_dados_dppo) AS setores_com_dados_dppo,
    count(*) FILTER (WHERE c.possui_dados_renda) AS setores_com_dados_renda,
    count(*) FILTER (WHERE c.possui_dados_saneamento) AS setores_com_dados_saneamento,
    count(*) FILTER (WHERE c.status_dados_setor = 'completo') AS setores_com_dados_completos,
    count(*) FILTER (WHERE c.status_dados_setor = 'parcial') AS setores_com_dados_parciais,
    round(sum(c.area_intersecao_ha)::numeric, 6) AS area_interesse_intersectada_ha,
    sum(c.populacao_total_setor) AS populacao_total_setores,
    sum(c.total_domicilios_setor) AS total_domicilios_setores,
    sum(c.domicilios_particulares_ocupados_setor) AS domicilios_particulares_ocupados_setores,
    sum(c.domicilios_particulares_permanentes_ocupados_setor) AS domicilios_particulares_permanentes_ocupados_setores,
    sum(c.moradores_domicilios_particulares_permanentes_ocupados_setor) AS moradores_domicilios_particulares_permanentes_ocupados_setores,
    sum(c.responsaveis_dppo_setor) AS responsaveis_dppo_setores,
    sum(c.agua_rede_geral_setor) AS agua_rede_geral_setores,
    sum(c.lixo_coletado_domicilio_setor) AS lixo_coletado_domicilio_setores,
    sum(c.esgoto_fossa_septica_nao_ligada_rede_setor) AS esgoto_fossa_septica_nao_ligada_rede_setores,
    avg(c.renda_media_responsavel_setor) AS renda_media_responsavel_media_setores,
    sum(c.renda_media_responsavel_setor * c.responsaveis_dppo_setor)
    / nullif(sum(c.responsaveis_dppo_setor), 0) AS renda_media_responsavel_ponderada_responsaveis,
    avg(c.renda_mediana_responsavel_setor) AS renda_mediana_responsavel_media_setores
FROM resultados.vw_socio_contexto_setores AS c
GROUP BY
    c.execucao_id,
    c.projeto_id,
    c.codigo_projeto,
    c.nome_projeto,
    c.cliente,
    c.municipio,
    c.uf,
    c.area_interesse_id,
    c.nome_area_interesse;
-- ============================================================================
-- 6. Sintese de populacao, moradores e domicilios
-- ============================================================================

CREATE OR REPLACE VIEW resultados.vw_socio_sintese_populacao_domicilios AS
SELECT
    r.execucao_id,
    r.projeto_id,
    r.codigo_projeto,
    r.nome_projeto,
    r.cliente,
    r.municipio,
    r.uf,
    r.area_interesse_id,
    r.nome_area_interesse,
    r.tema,
    r.subtema,
    r.nome_logico_indicador,
    r.descricao,
    r.unidade,
    r.valor_estimado_total,
    r.valor_medio_ponderado,
    r.numero_setores,
    r.metodo_estimativa,
    r.observacao
FROM resultados.vw_socio_indicadores_resumo AS r
WHERE concat_ws(' ', r.tema, r.subtema, r.nome_logico_indicador, r.descricao) ILIKE ANY (ARRAY[
    '%população%',
    '%populacao%',
    '%morador%',
    '%moradores%',
    '%domicílio%',
    '%domicilio%',
    '%domicílios%',
    '%domicilios%'
]);

-- ============================================================================
-- 7. Sintese de renda
-- ============================================================================

CREATE OR REPLACE VIEW resultados.vw_socio_sintese_renda AS
SELECT
    r.execucao_id,
    r.projeto_id,
    r.codigo_projeto,
    r.nome_projeto,
    r.cliente,
    r.municipio,
    r.uf,
    r.area_interesse_id,
    r.nome_area_interesse,
    r.tema,
    r.subtema,
    r.nome_logico_indicador,
    r.descricao,
    r.unidade,
    r.valor_estimado_total,
    r.valor_medio_ponderado,
    r.numero_setores,
    r.metodo_estimativa,
    r.observacao
FROM resultados.vw_socio_indicadores_resumo AS r
WHERE concat_ws(' ', r.tema, r.subtema, r.nome_logico_indicador, r.descricao) ILIKE ANY (ARRAY[
    '%renda%',
    '%rendimento%',
    '%responsável%',
    '%responsavel%',
    '%salário%',
    '%salario%'
]);

-- ============================================================================
-- 8. Sintese de saneamento
-- ============================================================================

CREATE OR REPLACE VIEW resultados.vw_socio_sintese_saneamento AS
SELECT
    r.execucao_id,
    r.projeto_id,
    r.codigo_projeto,
    r.nome_projeto,
    r.cliente,
    r.municipio,
    r.uf,
    r.area_interesse_id,
    r.nome_area_interesse,
    r.tema,
    r.subtema,
    r.nome_logico_indicador,
    r.descricao,
    r.unidade,
    r.valor_estimado_total,
    r.valor_medio_ponderado,
    r.numero_setores,
    r.metodo_estimativa,
    r.observacao
FROM resultados.vw_socio_indicadores_resumo AS r
WHERE concat_ws(' ', r.tema, r.subtema, r.nome_logico_indicador, r.descricao) ILIKE ANY (ARRAY[
    '%saneamento%',
    '%água%',
    '%agua%',
    '%abastecimento%',
    '%esgoto%',
    '%esgotamento%',
    '%fossa%',
    '%lixo%',
    '%resíduo%',
    '%residuo%',
    '%resíduos%',
    '%residuos%',
    '%coleta%',
    '%banheiro%',
    '%sanitário%',
    '%sanitario%'
]);

-- ============================================================================
-- 9. Sintese geral por area
-- ============================================================================

-- A view de sintese geral usa estimativas proporcionais por area de intersecao
-- dos setores censitarios. Use apenas quando essa premissa for metodologicamente
-- adequada. Para relatorios ambientais em APPs, glebas vazias ou areas nao
-- ocupadas, use preferencialmente resultados.vw_socio_contexto_setores e
-- resultados.vw_socio_contexto_setores_total.
-- A view de sintese geral e apenas uma camada de apresentacao.
-- O DROP VIEW evita erro de renomeacao de colunas em CREATE OR REPLACE VIEW
-- quando uma versao anterior ja existe. Nao apaga dados das tabelas-base.
DROP VIEW IF EXISTS resultados.vw_socio_sintese_geral_area;

CREATE OR REPLACE VIEW resultados.vw_socio_sintese_geral_area AS
SELECT
    r.execucao_id,
    r.projeto_id,
    r.codigo_projeto,
    r.nome_projeto,
    r.cliente,
    r.municipio,
    r.uf,
    r.area_interesse_id,
    r.nome_area_interesse,
    max(r.valor_estimado_total) FILTER (
        WHERE r.nome_logico_indicador = 'censo_total_pessoas'
    ) AS populacao_estimada,
    max(r.valor_estimado_total) FILTER (
        WHERE r.nome_logico_indicador = 'censo_total_domicilios'
    ) AS total_domicilios,
    max(r.valor_estimado_total) FILTER (
        WHERE r.nome_logico_indicador = 'censo_total_domicilios_particulares_ocupados'
    ) AS domicilios_particulares_ocupados,
    max(r.valor_estimado_total) FILTER (
        WHERE r.nome_logico_indicador = 'dom_dppo_total'
    ) AS domicilios_particulares_permanentes_ocupados,
    max(r.valor_estimado_total) FILTER (
        WHERE r.nome_logico_indicador = 'dom_dppo_moradores'
    ) AS moradores_domicilios_particulares_permanentes_ocupados,
    max(r.valor_medio_ponderado) FILTER (
        WHERE r.nome_logico_indicador = 'censo_media_moradores_dpo'
    ) AS media_moradores_por_domicilio,
    max(r.valor_medio_ponderado) FILTER (
        WHERE r.nome_logico_indicador = 'renda_media_responsavel'
    ) AS renda_media_responsavel,
    max(r.valor_medio_ponderado) FILTER (
        WHERE r.nome_logico_indicador = 'renda_mediana_responsavel'
    ) AS renda_mediana_responsavel,
    max(r.valor_estimado_total) FILTER (
        WHERE r.nome_logico_indicador = 'agua_rede_geral'
    ) AS domicilios_agua_rede_geral,
    max(r.valor_estimado_total) FILTER (
        WHERE r.nome_logico_indicador = 'lixo_coletado_domicilio_servico_limpeza'
    ) AS domicilios_lixo_coletado_domicilio,
    max(r.valor_estimado_total) FILTER (
        WHERE r.nome_logico_indicador = 'esgoto_fossa_septica_nao_ligada_rede'
    ) AS domicilios_esgoto_fossa_septica_nao_ligada_rede,
    max(r.numero_setores) AS numero_setores
FROM resultados.vw_socio_indicadores_resumo AS r
GROUP BY
    r.execucao_id,
    r.projeto_id,
    r.codigo_projeto,
    r.nome_projeto,
    r.cliente,
    r.municipio,
    r.uf,
    r.area_interesse_id,
    r.nome_area_interesse;
-- ============================================================================
-- 10. Consultas de conferencia para uso manual apos execucao autorizada
-- ============================================================================

/*
-- Conferir setores intersectados
SELECT *
FROM resultados.vw_socio_setores_intersectados
WHERE execucao_id = 4
  AND projeto_id = 1
  AND area_interesse_id = 1
ORDER BY percentual_area_interesse DESC;

-- Conferir resumo
SELECT *
FROM resultados.vw_socio_indicadores_resumo
WHERE execucao_id = 4
  AND projeto_id = 1
  AND area_interesse_id = 1
ORDER BY tema, subtema, nome_logico_indicador;

-- Conferir detalhe por setor
SELECT *
FROM resultados.vw_socio_indicadores_detalhe_setor
WHERE execucao_id = 4
  AND projeto_id = 1
  AND area_interesse_id = 1
ORDER BY cd_setor, tema, subtema, nome_logico_indicador;

-- Conferir sintese geral
SELECT *
FROM resultados.vw_socio_sintese_geral_area
WHERE execucao_id = 4
  AND projeto_id = 1
  AND area_interesse_id = 1;

-- Conferir registros sem indicador
SELECT *
FROM resultados.vw_socio_indicadores_resumo
WHERE nome_logico_indicador IS NULL
   OR btrim(nome_logico_indicador) = '';

-- Conferir valores estimados nulos
SELECT *
FROM resultados.vw_socio_indicadores_resumo
WHERE valor_estimado_total IS NULL
  AND valor_medio_ponderado IS NULL;

-- Conferir contexto socioeconomico por setor inteiro
SELECT *
FROM resultados.vw_socio_contexto_setores
WHERE execucao_id = 4
  AND projeto_id = 1
  AND area_interesse_id = 1
ORDER BY percentual_area_interesse DESC;

-- Conferir total do contexto socioeconomico dos setores inteiros
SELECT *
FROM resultados.vw_socio_contexto_setores_total
WHERE execucao_id = 4
  AND projeto_id = 1
  AND area_interesse_id = 1;

-- Conferir renda media simples, renda media ponderada por responsaveis e media
-- simples das medianas setoriais no contexto dos setores interceptados
SELECT
    responsaveis_dppo_setores,
    renda_media_responsavel_media_setores,
    renda_media_responsavel_ponderada_responsaveis,
    renda_mediana_responsavel_media_setores
FROM resultados.vw_socio_contexto_setores_total
WHERE execucao_id = 4
  AND projeto_id = 1
  AND area_interesse_id = 1;
*/

