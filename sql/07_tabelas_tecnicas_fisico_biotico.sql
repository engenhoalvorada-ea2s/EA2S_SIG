/*
EA2S SIG - 07_tabelas_tecnicas_fisico_biotico.sql

PROPOSTA LOCAL, AINDA NAO EXECUTADA.

Objetivo:
Criar views tecnicas de saida para diagnostico fisico-biotico do MVP a partir
da tabela-base resultados.intersecao_fisico_biotica.

Nao executar sem revisao e autorizacao explicita.
Nao conectar ao banco a partir deste arquivo.
Nao confundir hidrogeologia com hidrologia superficial. O tema hidrogeologia
representa unidades hidrogeologicas ja processadas no script 05. Hidrologia
superficial, cursos d'agua e drenagem devem ser tratados em modulo posterior
com camadas de hidrografia.

Observacao metodologica:
area_total_registrada_m2, quando utilizada em conferencias, representa soma
operacional das areas registradas por tema e unidade de analise, nao area
territorial liquida unica.
*/

-- ============================================================================
-- 1. Sintese por unidade de analise e tema
-- ============================================================================

CREATE OR REPLACE VIEW resultados.vw_fisico_biotico_sintese_unidade_tema AS
SELECT
    ifb.execucao_id,
    ifb.projeto_id,
    ifb.area_interesse_id,
    ifb.unidade_analise,
    ifb.unidade_analise_codigo,
    ifb.unidade_analise_nome,
    ifb.tema,
    count(DISTINCT ifb.valor_principal) AS total_classes,
    round(sum(ifb.area_intersecao_m2)::numeric, 4) AS area_total_m2,
    round(sum(ifb.area_intersecao_ha)::numeric, 6) AS area_total_ha,
    round(sum(ifb.percentual_unidade_analise)::numeric, 8) AS percentual_total
FROM resultados.intersecao_fisico_biotica AS ifb
GROUP BY
    ifb.execucao_id,
    ifb.projeto_id,
    ifb.area_interesse_id,
    ifb.unidade_analise,
    ifb.unidade_analise_codigo,
    ifb.unidade_analise_nome,
    ifb.tema;

-- ============================================================================
-- 2. Classes tematicas consolidadas
-- ============================================================================

CREATE OR REPLACE VIEW resultados.vw_fisico_biotico_classes AS
SELECT
    ifb.execucao_id,
    ifb.projeto_id,
    ifb.area_interesse_id,
    ifb.unidade_analise,
    ifb.unidade_analise_codigo,
    ifb.unidade_analise_nome,
    ifb.tema,
    ifb.camada_origem,
    ifb.campo_principal,
    COALESCE(NULLIF(btrim(ifb.valor_principal), ''), 'Sem classificação informada') AS valor_principal,
    round(sum(ifb.area_intersecao_m2)::numeric, 4) AS area_m2,
    round(sum(ifb.area_intersecao_ha)::numeric, 6) AS area_ha,
    round(sum(ifb.percentual_unidade_analise)::numeric, 8) AS percentual_unidade_analise
FROM resultados.intersecao_fisico_biotica AS ifb
GROUP BY
    ifb.execucao_id,
    ifb.projeto_id,
    ifb.area_interesse_id,
    ifb.unidade_analise,
    ifb.unidade_analise_codigo,
    ifb.unidade_analise_nome,
    ifb.tema,
    ifb.camada_origem,
    ifb.campo_principal,
    ifb.valor_principal;

-- ============================================================================
-- 3. Tabela tecnica de geologia
-- ============================================================================

CREATE OR REPLACE VIEW resultados.vw_tabela_geologia AS
SELECT
    ifb.execucao_id,
    ifb.projeto_id,
    ifb.area_interesse_id,
    ifb.unidade_analise,
    ifb.unidade_analise_codigo,
    ifb.unidade_analise_nome,
    ifb.valor_principal AS unidade_geologica,
    ifb.atributos_complementares ->> 'letra_simb' AS letra_simb,
    ifb.atributos_complementares ->> 'nm_lito1' AS nm_lito1,
    ifb.atributos_complementares ->> 'nm_lito2' AS nm_lito2,
    ifb.atributos_complementares ->> 'nm_lito3' AS nm_lito3,
    ifb.atributos_complementares ->> 'nm_lito4' AS nm_lito4,
    ifb.atributos_complementares ->> 'nm_tempo_g' AS nm_tempo_g,
    ifb.atributos_complementares ->> 'nm_provinc' AS nm_provinc,
    ifb.atributos_complementares ->> 'nm_sub_pro' AS nm_sub_pro,
    round(sum(ifb.area_intersecao_m2)::numeric, 4) AS area_m2,
    round(sum(ifb.area_intersecao_ha)::numeric, 6) AS area_ha,
    round(sum(ifb.percentual_unidade_analise)::numeric, 8) AS percentual_unidade_analise
FROM resultados.intersecao_fisico_biotica AS ifb
WHERE ifb.tema = 'geologia'
GROUP BY
    ifb.execucao_id,
    ifb.projeto_id,
    ifb.area_interesse_id,
    ifb.unidade_analise,
    ifb.unidade_analise_codigo,
    ifb.unidade_analise_nome,
    ifb.valor_principal,
    ifb.atributos_complementares ->> 'letra_simb',
    ifb.atributos_complementares ->> 'nm_lito1',
    ifb.atributos_complementares ->> 'nm_lito2',
    ifb.atributos_complementares ->> 'nm_lito3',
    ifb.atributos_complementares ->> 'nm_lito4',
    ifb.atributos_complementares ->> 'nm_tempo_g',
    ifb.atributos_complementares ->> 'nm_provinc',
    ifb.atributos_complementares ->> 'nm_sub_pro';

-- ============================================================================
-- 4. Tabela tecnica de geomorfologia
-- ============================================================================

CREATE OR REPLACE VIEW resultados.vw_tabela_geomorfologia AS
SELECT
    ifb.execucao_id,
    ifb.projeto_id,
    ifb.area_interesse_id,
    ifb.unidade_analise,
    ifb.unidade_analise_codigo,
    ifb.unidade_analise_nome,
    ifb.valor_principal AS legenda,
    ifb.atributos_complementares ->> 'nm_dominio' AS nm_dominio,
    ifb.atributos_complementares ->> 'nm_regiao' AS nm_regiao,
    ifb.atributos_complementares ->> 'nm_unidade' AS nm_unidade,
    ifb.atributos_complementares ->> 'categoria' AS categoria,
    ifb.atributos_complementares ->> 'natureza' AS natureza,
    ifb.atributos_complementares ->> 'forma' AS forma,
    ifb.atributos_complementares ->> 'dens_dren' AS dens_dren,
    ifb.atributos_complementares ->> 'aprof_inci' AS aprof_inci,
    ifb.atributos_complementares ->> 'niv_alt' AS niv_alt,
    ifb.atributos_complementares ->> 'compartime' AS compartime,
    round(sum(ifb.area_intersecao_m2)::numeric, 4) AS area_m2,
    round(sum(ifb.area_intersecao_ha)::numeric, 6) AS area_ha,
    round(sum(ifb.percentual_unidade_analise)::numeric, 8) AS percentual_unidade_analise
FROM resultados.intersecao_fisico_biotica AS ifb
WHERE ifb.tema = 'geomorfologia'
GROUP BY
    ifb.execucao_id,
    ifb.projeto_id,
    ifb.area_interesse_id,
    ifb.unidade_analise,
    ifb.unidade_analise_codigo,
    ifb.unidade_analise_nome,
    ifb.valor_principal,
    ifb.atributos_complementares ->> 'nm_dominio',
    ifb.atributos_complementares ->> 'nm_regiao',
    ifb.atributos_complementares ->> 'nm_unidade',
    ifb.atributos_complementares ->> 'categoria',
    ifb.atributos_complementares ->> 'natureza',
    ifb.atributos_complementares ->> 'forma',
    ifb.atributos_complementares ->> 'dens_dren',
    ifb.atributos_complementares ->> 'aprof_inci',
    ifb.atributos_complementares ->> 'niv_alt',
    ifb.atributos_complementares ->> 'compartime';

-- ============================================================================
-- 5. Tabela tecnica de hidrogeologia
-- ============================================================================

CREATE OR REPLACE VIEW resultados.vw_tabela_hidrogeologia AS
SELECT
    ifb.execucao_id,
    ifb.projeto_id,
    ifb.area_interesse_id,
    ifb.unidade_analise,
    ifb.unidade_analise_codigo,
    ifb.unidade_analise_nome,
    COALESCE(NULLIF(btrim(ifb.valor_principal), ''), 'Sem unidade hidrogeológica informada') AS unidade_hidrogeologica,
    ifb.atributos_complementares ->> 'cd_legenda' AS cd_legenda,
    ifb.atributos_complementares ->> 'litologia' AS litologia,
    ifb.atributos_complementares ->> 'provincia' AS provincia,
    ifb.atributos_complementares ->> 'dominio' AS dominio,
    ifb.atributos_complementares ->> 'vz_cl' AS vz_cl,
    ifb.atributos_complementares ->> 'vze_cl' AS vze_cl,
    ifb.atributos_complementares ->> 'vz_int_cl' AS vz_int_cl,
    ifb.atributos_complementares ->> 'vze_int_cl' AS vze_int_cl,
    ifb.atributos_complementares ->> 'domínio_da' AS dominio_da,
    round(sum(ifb.area_intersecao_m2)::numeric, 4) AS area_m2,
    round(sum(ifb.area_intersecao_ha)::numeric, 6) AS area_ha,
    round(sum(ifb.percentual_unidade_analise)::numeric, 8) AS percentual_unidade_analise
FROM resultados.intersecao_fisico_biotica AS ifb
WHERE ifb.tema = 'hidrogeologia'
GROUP BY
    ifb.execucao_id,
    ifb.projeto_id,
    ifb.area_interesse_id,
    ifb.unidade_analise,
    ifb.unidade_analise_codigo,
    ifb.unidade_analise_nome,
    ifb.valor_principal,
    ifb.atributos_complementares ->> 'cd_legenda',
    ifb.atributos_complementares ->> 'litologia',
    ifb.atributos_complementares ->> 'provincia',
    ifb.atributos_complementares ->> 'dominio',
    ifb.atributos_complementares ->> 'vz_cl',
    ifb.atributos_complementares ->> 'vze_cl',
    ifb.atributos_complementares ->> 'vz_int_cl',
    ifb.atributos_complementares ->> 'vze_int_cl',
    ifb.atributos_complementares ->> 'domínio_da';

-- ============================================================================
-- 6. Tabela tecnica de pedologia
-- ============================================================================

CREATE OR REPLACE VIEW resultados.vw_tabela_pedologia AS
SELECT
    ifb.execucao_id,
    ifb.projeto_id,
    ifb.area_interesse_id,
    ifb.unidade_analise,
    ifb.unidade_analise_codigo,
    ifb.unidade_analise_nome,
    ifb.valor_principal AS legenda_pedologica,
    ifb.atributos_complementares ->> 'area_km' AS area_km_origem,
    round(sum(ifb.area_intersecao_m2)::numeric, 4) AS area_m2,
    round(sum(ifb.area_intersecao_ha)::numeric, 6) AS area_ha,
    round(sum(ifb.percentual_unidade_analise)::numeric, 8) AS percentual_unidade_analise
FROM resultados.intersecao_fisico_biotica AS ifb
WHERE ifb.tema = 'pedologia'
GROUP BY
    ifb.execucao_id,
    ifb.projeto_id,
    ifb.area_interesse_id,
    ifb.unidade_analise,
    ifb.unidade_analise_codigo,
    ifb.unidade_analise_nome,
    ifb.valor_principal,
    ifb.atributos_complementares ->> 'area_km';

-- ============================================================================
-- 7. Tabela tecnica de vegetacao
-- ============================================================================

CREATE OR REPLACE VIEW resultados.vw_tabela_vegetacao AS
SELECT
    ifb.execucao_id,
    ifb.projeto_id,
    ifb.area_interesse_id,
    ifb.unidade_analise,
    ifb.unidade_analise_codigo,
    ifb.unidade_analise_nome,
    ifb.valor_principal AS legenda_vegetacao,
    ifb.atributos_complementares ->> 'cd_fito' AS cd_fito,
    ifb.atributos_complementares ->> 'cd_leg_2' AS cd_leg_2,
    ifb.atributos_complementares ->> 'clas_domi' AS clas_domi,
    ifb.atributos_complementares ->> 'nm_uveg' AS nm_uveg,
    ifb.atributos_complementares ->> 'nm_uantr' AS nm_uantr,
    ifb.atributos_complementares ->> 'nm_contat' AS nm_contat,
    ifb.atributos_complementares ->> 'nm_pretet' AS nm_pretet,
    ifb.atributos_complementares ->> 'legenda_1' AS legenda_1,
    ifb.atributos_complementares ->> 'legenda_2' AS legenda_2,
    round(sum(ifb.area_intersecao_m2)::numeric, 4) AS area_m2,
    round(sum(ifb.area_intersecao_ha)::numeric, 6) AS area_ha,
    round(sum(ifb.percentual_unidade_analise)::numeric, 8) AS percentual_unidade_analise
FROM resultados.intersecao_fisico_biotica AS ifb
WHERE ifb.tema = 'vegetacao'
GROUP BY
    ifb.execucao_id,
    ifb.projeto_id,
    ifb.area_interesse_id,
    ifb.unidade_analise,
    ifb.unidade_analise_codigo,
    ifb.unidade_analise_nome,
    ifb.valor_principal,
    ifb.atributos_complementares ->> 'cd_fito',
    ifb.atributos_complementares ->> 'cd_leg_2',
    ifb.atributos_complementares ->> 'clas_domi',
    ifb.atributos_complementares ->> 'nm_uveg',
    ifb.atributos_complementares ->> 'nm_uantr',
    ifb.atributos_complementares ->> 'nm_contat',
    ifb.atributos_complementares ->> 'nm_pretet',
    ifb.atributos_complementares ->> 'legenda_1',
    ifb.atributos_complementares ->> 'legenda_2';

-- ============================================================================
-- 8. Microbacias analisadas
-- ============================================================================

CREATE OR REPLACE VIEW resultados.vw_tabela_microbacias_fisico_biotico AS
SELECT DISTINCT
    ifb.execucao_id,
    ifb.projeto_id,
    ifb.area_interesse_id,
    ifb.atributos_complementares -> 'unidade_analise' ->> 'cd_micro' AS cd_micro,
    ifb.atributos_complementares -> 'unidade_analise' ->> 'nm_micro' AS nm_micro,
    ifb.atributos_complementares -> 'unidade_analise' ->> 'nm_rio_pri' AS nm_rio_pri,
    ifb.atributos_complementares -> 'unidade_analise' ->> 'cd_bacia' AS cd_bacia,
    ifb.atributos_complementares -> 'unidade_analise' ->> 'cd_ibge_mu' AS cd_ibge_mu,
    ifb.atributos_complementares -> 'unidade_analise' ->> 'sg_tipo' AS sg_tipo,
    ifb.atributos_complementares -> 'unidade_analise' ->> 'vl_qmin7' AS vl_qmin7,
    ifb.atributos_complementares -> 'unidade_analise' ->> 'nm_qmin7' AS nm_qmin7,
    ifb.atributos_complementares -> 'unidade_analise' ->> 'vl_qrest' AS vl_qrest,
    ifb.atributos_complementares -> 'unidade_analise' ->> 'vl_qsubt' AS vl_qsubt,
    ifb.atributos_complementares -> 'unidade_analise' ->> 'shape_area' AS shape_area,
    ifb.atributos_complementares -> 'unidade_analise' ->> 'shape_len' AS shape_len
FROM resultados.intersecao_fisico_biotica AS ifb
WHERE ifb.unidade_analise = 'microbacia';

-- ============================================================================
-- 9. Consultas de conferencia para uso manual apos execucao autorizada
-- ============================================================================

/*
-- Conferir sintese por unidade e tema
SELECT
    s.execucao_id,
    s.projeto_id,
    s.area_interesse_id,
    s.unidade_analise,
    s.unidade_analise_codigo,
    s.unidade_analise_nome,
    s.tema,
    s.total_classes,
    s.area_total_m2,
    s.area_total_ha,
    s.percentual_total
FROM resultados.vw_fisico_biotico_sintese_unidade_tema AS s
WHERE s.execucao_id = :execucao_id
  AND s.projeto_id = :projeto_id
  AND s.area_interesse_id = :area_interesse_id
ORDER BY
    s.unidade_analise,
    s.unidade_analise_codigo,
    s.tema;

-- Listar classes da area de interesse
SELECT
    c.tema,
    c.valor_principal,
    c.area_m2,
    c.area_ha,
    c.percentual_unidade_analise
FROM resultados.vw_fisico_biotico_classes AS c
WHERE c.execucao_id = :execucao_id
  AND c.projeto_id = :projeto_id
  AND c.area_interesse_id = :area_interesse_id
  AND c.unidade_analise = 'area_interesse'
ORDER BY
    c.tema,
    c.area_m2 DESC;

-- Listar classes do buffer
SELECT
    c.tema,
    c.valor_principal,
    c.area_m2,
    c.area_ha,
    c.percentual_unidade_analise
FROM resultados.vw_fisico_biotico_classes AS c
WHERE c.execucao_id = :execucao_id
  AND c.projeto_id = :projeto_id
  AND c.area_interesse_id = :area_interesse_id
  AND c.unidade_analise = 'buffer_1000m'
ORDER BY
    c.tema,
    c.area_m2 DESC;

-- Listar classes das microbacias
SELECT
    c.unidade_analise_codigo,
    c.unidade_analise_nome,
    c.tema,
    c.valor_principal,
    c.area_m2,
    c.area_ha,
    c.percentual_unidade_analise
FROM resultados.vw_fisico_biotico_classes AS c
WHERE c.execucao_id = :execucao_id
  AND c.projeto_id = :projeto_id
  AND c.area_interesse_id = :area_interesse_id
  AND c.unidade_analise = 'microbacia'
ORDER BY
    c.unidade_analise_codigo,
    c.tema,
    c.area_m2 DESC;

-- Conferir percentuais acima de 100 ou abaixo de 0
SELECT
    ifb.id,
    ifb.execucao_id,
    ifb.projeto_id,
    ifb.area_interesse_id,
    ifb.unidade_analise,
    ifb.tema,
    ifb.valor_principal,
    ifb.percentual_unidade_analise
FROM resultados.intersecao_fisico_biotica AS ifb
WHERE ifb.percentual_unidade_analise < 0
   OR ifb.percentual_unidade_analise > 100
ORDER BY
    ifb.execucao_id,
    ifb.projeto_id,
    ifb.area_interesse_id,
    ifb.unidade_analise,
    ifb.tema;

-- Conferir registros sem valor_principal
SELECT
    ifb.id,
    ifb.execucao_id,
    ifb.projeto_id,
    ifb.area_interesse_id,
    ifb.unidade_analise,
    ifb.tema,
    ifb.camada_origem,
    ifb.campo_principal
FROM resultados.intersecao_fisico_biotica AS ifb
WHERE ifb.valor_principal IS NULL
   OR btrim(ifb.valor_principal) = ''
ORDER BY
    ifb.execucao_id,
    ifb.projeto_id,
    ifb.area_interesse_id,
    ifb.unidade_analise,
    ifb.tema;
*/



