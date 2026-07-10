/*
EA2S SIG - 10_hidrografia_ana.sql

PROPOSTA LOCAL, AINDA NAO EXECUTADA.

Objetivo:
Criar a primeira versao do modulo de hidrografia ANA para o MVP EA2S SIG,
tratando hidrografia como camada linear e usando comprimento como metrica
principal.

Nao executar sem revisao e autorizacao explicita.
Nao alterar dados oficiais do schema hidrografia.
Nao misturar hidrografia na tabela resultados.intersecao_fisico_biotica.

Fontes reais identificadas:
- hidrografia."bh6_curso_dagua_ANA_2022": hidrografia ANA, SRID 4674,
  MULTILINESTRING, campo geometrico geom;
- hidrografia.microbacias_sigeo_sirhesc_aguassc: microbacias, SRID 29192,
  MULTIPOLYGON, campo geometrico geom.

Observacoes importantes:
- a tabela ANA nao possui campo explicito de nome do curso d'agua;
- nome_curso fica NULL nesta versao e nao deve ser preenchido com codigo;
- os principais identificadores sao idcda, cocursodag, nuordemcda e nunivotcda;
- atributos originais sao preservados em atributos_origem jsonb;
- calculos de comprimento devem ocorrer em EPSG:31982.
*/

-- ============================================================================
-- 1. Tabela de resultados - hidrografia linear
-- ============================================================================

CREATE TABLE IF NOT EXISTS resultados.intersecao_hidrografia (
    id bigserial PRIMARY KEY,
    execucao_id bigint NOT NULL,
    projeto_id bigint NOT NULL,
    area_interesse_id bigint NOT NULL,
    unidade_analise text NOT NULL,
    cd_micro text,
    nm_micro text,
    nm_rio_pri text,
    fonte_schema text NOT NULL,
    fonte_tabela text NOT NULL,
    fonte_camada text NOT NULL,
    fid_ana text,
    wtc_pk text,
    idcda text,
    cocursodag text,
    cocdadesag text,
    nunivotcda text,
    nuordemcda text,
    dedominial text,
    dsversao text,
    codigo_trecho text,
    codigo_curso text,
    nome_curso text,
    comprimento_m numeric,
    comprimento_km numeric,
    nucompcda_original numeric,
    atributos_origem jsonb,
    geom geometry(MultiLineString, 31982),
    criado_em timestamp DEFAULT now(),
    CONSTRAINT intersecao_hidrografia_unidade_chk CHECK (
        unidade_analise IN ('area_interesse', 'buffer_1000m', 'microbacia')
    )
);

ALTER TABLE resultados.intersecao_hidrografia
    ADD COLUMN IF NOT EXISTS execucao_id bigint,
    ADD COLUMN IF NOT EXISTS projeto_id bigint,
    ADD COLUMN IF NOT EXISTS area_interesse_id bigint,
    ADD COLUMN IF NOT EXISTS unidade_analise text,
    ADD COLUMN IF NOT EXISTS cd_micro text,
    ADD COLUMN IF NOT EXISTS nm_micro text,
    ADD COLUMN IF NOT EXISTS nm_rio_pri text,
    ADD COLUMN IF NOT EXISTS fonte_schema text,
    ADD COLUMN IF NOT EXISTS fonte_tabela text,
    ADD COLUMN IF NOT EXISTS fonte_camada text,
    ADD COLUMN IF NOT EXISTS fid_ana text,
    ADD COLUMN IF NOT EXISTS wtc_pk text,
    ADD COLUMN IF NOT EXISTS idcda text,
    ADD COLUMN IF NOT EXISTS cocursodag text,
    ADD COLUMN IF NOT EXISTS cocdadesag text,
    ADD COLUMN IF NOT EXISTS nunivotcda text,
    ADD COLUMN IF NOT EXISTS nuordemcda text,
    ADD COLUMN IF NOT EXISTS dedominial text,
    ADD COLUMN IF NOT EXISTS dsversao text,
    ADD COLUMN IF NOT EXISTS codigo_trecho text,
    ADD COLUMN IF NOT EXISTS codigo_curso text,
    ADD COLUMN IF NOT EXISTS nome_curso text,
    ADD COLUMN IF NOT EXISTS comprimento_m numeric,
    ADD COLUMN IF NOT EXISTS comprimento_km numeric,
    ADD COLUMN IF NOT EXISTS nucompcda_original numeric,
    ADD COLUMN IF NOT EXISTS atributos_origem jsonb,
    ADD COLUMN IF NOT EXISTS geom geometry(MultiLineString, 31982),
    ADD COLUMN IF NOT EXISTS criado_em timestamp DEFAULT now();

ALTER TABLE resultados.intersecao_hidrografia
    ALTER COLUMN execucao_id SET NOT NULL,
    ALTER COLUMN projeto_id SET NOT NULL,
    ALTER COLUMN area_interesse_id SET NOT NULL,
    ALTER COLUMN unidade_analise SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_intersecao_hidrografia_execucao
    ON resultados.intersecao_hidrografia(execucao_id);

CREATE INDEX IF NOT EXISTS idx_intersecao_hidrografia_projeto
    ON resultados.intersecao_hidrografia(projeto_id);

CREATE INDEX IF NOT EXISTS idx_intersecao_hidrografia_area
    ON resultados.intersecao_hidrografia(area_interesse_id);

CREATE INDEX IF NOT EXISTS idx_intersecao_hidrografia_contexto
    ON resultados.intersecao_hidrografia(execucao_id, projeto_id, area_interesse_id);

CREATE INDEX IF NOT EXISTS idx_intersecao_hidrografia_unidade
    ON resultados.intersecao_hidrografia(unidade_analise);

CREATE INDEX IF NOT EXISTS idx_intersecao_hidrografia_cd_micro
    ON resultados.intersecao_hidrografia(cd_micro);

CREATE INDEX IF NOT EXISTS idx_intersecao_hidrografia_cocursodag
    ON resultados.intersecao_hidrografia(cocursodag);

CREATE INDEX IF NOT EXISTS idx_intersecao_hidrografia_idcda
    ON resultados.intersecao_hidrografia(idcda);

CREATE INDEX IF NOT EXISTS idx_intersecao_hidrografia_geom
    ON resultados.intersecao_hidrografia USING gist(geom);

-- ============================================================================
-- 2. Funcao de processamento
-- ============================================================================

CREATE OR REPLACE FUNCTION resultados.processar_hidrografia_ana_mvp(
    p_execucao_id bigint,
    p_projeto_id bigint,
    p_area_interesse_id bigint
)
RETURNS TABLE (
    resultado_execucao_id bigint,
    trechos_processados integer,
    comprimento_total_m numeric,
    comprimento_total_km numeric
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_trechos_processados integer := 0;
    v_comprimento_total_m numeric := 0;
    v_comprimento_total_km numeric := 0;
BEGIN
    IF p_execucao_id IS NULL THEN
        RAISE EXCEPTION 'execucao_id nao pode ser nulo.';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM resultados.execucao AS e
        WHERE e.id = p_execucao_id
          AND e.projeto_id = p_projeto_id
    ) THEN
        RAISE EXCEPTION
            'execucao_id informado nao existe para o projeto. execucao_id=%, projeto_id=%',
            p_execucao_id,
            p_projeto_id;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM projetos.area_interesse AS ai
        WHERE ai.id = p_area_interesse_id
          AND ai.projeto_id = p_projeto_id
    ) THEN
        RAISE EXCEPTION
            'Area de interesse nao encontrada. projeto_id=%, area_interesse_id=%',
            p_projeto_id,
            p_area_interesse_id;
    END IF;

    INSERT INTO logs.processamento (
        execucao_id,
        projeto_id,
        nivel,
        etapa,
        mensagem,
        detalhe
    )
    VALUES (
        p_execucao_id,
        p_projeto_id,
        'info',
        'processar_hidrografia_ana_mvp',
        'Inicio do processamento de hidrografia ANA.',
        jsonb_build_object(
            'area_interesse_id', p_area_interesse_id,
            'fonte_schema', 'hidrografia',
            'fonte_tabela', 'bh6_curso_dagua_ANA_2022',
            'fonte_camada', 'hidrografia_ana',
            'srid_origem_ana', 4674,
            'srid_saida', 31982
        )
    );

    DELETE FROM resultados.intersecao_hidrografia AS ih
    WHERE ih.execucao_id = p_execucao_id
      AND ih.projeto_id = p_projeto_id
      AND ih.area_interesse_id = p_area_interesse_id;

    WITH area_interesse AS (
        SELECT
            ai.id AS area_interesse_id,
            ai.projeto_id AS projeto_id,
            ST_Multi(
                ST_CollectionExtract(
                    ST_MakeValid(ST_Transform(ai.geom, 31982)),
                    3
                )
            )::geometry(MultiPolygon, 31982) AS geom_31982
        FROM projetos.area_interesse AS ai
        WHERE ai.id = p_area_interesse_id
          AND ai.projeto_id = p_projeto_id
    ),
    microbacias AS (
        SELECT
            mb.cd_micro::text AS cd_micro,
            mb.nm_micro::text AS nm_micro,
            mb.nm_rio_pri::text AS nm_rio_pri,
            ST_Multi(
                ST_CollectionExtract(
                    ST_MakeValid(ST_Transform(mb.geom, 31982)),
                    3
                )
            )::geometry(MultiPolygon, 31982) AS geom_31982
        FROM hidrografia.microbacias_sigeo_sirhesc_aguassc AS mb
        INNER JOIN area_interesse AS ai
            ON mb.geom && ST_Transform(ai.geom_31982, 29192)
           AND ST_Intersects(
                ST_MakeValid(ST_Transform(mb.geom, 31982)),
                ai.geom_31982
           )
    ),
    unidades_analise AS (
        SELECT
            'area_interesse'::text AS unidade_analise,
            NULL::text AS cd_micro,
            NULL::text AS nm_micro,
            NULL::text AS nm_rio_pri,
            ai.geom_31982 AS geom_31982
        FROM area_interesse AS ai

        UNION ALL

        SELECT
            'buffer_1000m'::text AS unidade_analise,
            NULL::text AS cd_micro,
            NULL::text AS nm_micro,
            NULL::text AS nm_rio_pri,
            ST_Multi(
                ST_CollectionExtract(
                    ST_MakeValid(ST_Buffer(ai.geom_31982, 1000)),
                    3
                )
            )::geometry(MultiPolygon, 31982) AS geom_31982
        FROM area_interesse AS ai

        UNION ALL

        SELECT
            'microbacia'::text AS unidade_analise,
            mb.cd_micro,
            mb.nm_micro,
            mb.nm_rio_pri,
            mb.geom_31982
        FROM microbacias AS mb
    ),
    hidrografia_base AS (
        SELECT
            h.fid::text AS fid_ana,
            h.wtc_pk::text AS wtc_pk,
            h.idcda::text AS idcda,
            h.cocursodag::text AS cocursodag,
            h.cocdadesag::text AS cocdadesag,
            h.nunivotcda::text AS nunivotcda,
            h.nuordemcda::text AS nuordemcda,
            h.dedominial::text AS dedominial,
            h.dsversao::text AS dsversao,
            h.nucompcda::numeric AS nucompcda_original,
            to_jsonb(h) - 'geom' - 'geometry' AS atributos_origem,
            ST_Multi(
                ST_CollectionExtract(
                    ST_MakeValid(ST_Transform(h.geom, 31982)),
                    2
                )
            )::geometry(MultiLineString, 31982) AS geom_31982
        FROM hidrografia."bh6_curso_dagua_ANA_2022" AS h
        WHERE h.geom IS NOT NULL
    ),
    intersecoes AS (
        SELECT
            p_execucao_id AS execucao_id,
            p_projeto_id AS projeto_id,
            p_area_interesse_id AS area_interesse_id,
            ua.unidade_analise,
            ua.cd_micro,
            ua.nm_micro,
            ua.nm_rio_pri,
            'hidrografia'::text AS fonte_schema,
            'bh6_curso_dagua_ANA_2022'::text AS fonte_tabela,
            'hidrografia_ana'::text AS fonte_camada,
            hb.fid_ana,
            hb.wtc_pk,
            hb.idcda,
            hb.cocursodag,
            hb.cocdadesag,
            hb.nunivotcda,
            hb.nuordemcda,
            hb.dedominial,
            hb.dsversao,
            hb.idcda AS codigo_trecho,
            hb.cocursodag AS codigo_curso,
            NULL::text AS nome_curso,
            hb.nucompcda_original,
            hb.atributos_origem,
            ST_Multi(
                ST_CollectionExtract(
                    ST_MakeValid(ST_Intersection(hb.geom_31982, ua.geom_31982)),
                    2
                )
            )::geometry(MultiLineString, 31982) AS geom
        FROM unidades_analise AS ua
        INNER JOIN hidrografia_base AS hb
            ON hb.geom_31982 && ua.geom_31982
           AND ST_Intersects(hb.geom_31982, ua.geom_31982)
    ),
    intersecoes_validas AS (
        SELECT
            inter.execucao_id,
            inter.projeto_id,
            inter.area_interesse_id,
            inter.unidade_analise,
            inter.cd_micro,
            inter.nm_micro,
            inter.nm_rio_pri,
            inter.fonte_schema,
            inter.fonte_tabela,
            inter.fonte_camada,
            inter.fid_ana,
            inter.wtc_pk,
            inter.idcda,
            inter.cocursodag,
            inter.cocdadesag,
            inter.nunivotcda,
            inter.nuordemcda,
            inter.dedominial,
            inter.dsversao,
            inter.codigo_trecho,
            inter.codigo_curso,
            inter.nome_curso,
            round(ST_Length(inter.geom)::numeric, 4) AS comprimento_m,
            round((ST_Length(inter.geom) / 1000.0)::numeric, 6) AS comprimento_km,
            inter.nucompcda_original,
            inter.atributos_origem,
            inter.geom
        FROM intersecoes AS inter
        WHERE inter.geom IS NOT NULL
          AND NOT ST_IsEmpty(inter.geom)
          AND ST_Length(inter.geom) > 0
    )
    INSERT INTO resultados.intersecao_hidrografia (
        execucao_id,
        projeto_id,
        area_interesse_id,
        unidade_analise,
        cd_micro,
        nm_micro,
        nm_rio_pri,
        fonte_schema,
        fonte_tabela,
        fonte_camada,
        fid_ana,
        wtc_pk,
        idcda,
        cocursodag,
        cocdadesag,
        nunivotcda,
        nuordemcda,
        dedominial,
        dsversao,
        codigo_trecho,
        codigo_curso,
        nome_curso,
        comprimento_m,
        comprimento_km,
        nucompcda_original,
        atributos_origem,
        geom
    )
    SELECT
        iv.execucao_id,
        iv.projeto_id,
        iv.area_interesse_id,
        iv.unidade_analise,
        iv.cd_micro,
        iv.nm_micro,
        iv.nm_rio_pri,
        iv.fonte_schema,
        iv.fonte_tabela,
        iv.fonte_camada,
        iv.fid_ana,
        iv.wtc_pk,
        iv.idcda,
        iv.cocursodag,
        iv.cocdadesag,
        iv.nunivotcda,
        iv.nuordemcda,
        iv.dedominial,
        iv.dsversao,
        iv.codigo_trecho,
        iv.codigo_curso,
        iv.nome_curso,
        iv.comprimento_m,
        iv.comprimento_km,
        iv.nucompcda_original,
        iv.atributos_origem,
        iv.geom
    FROM intersecoes_validas AS iv;

    SELECT
        count(*)::integer,
        coalesce(sum(ih.comprimento_m), 0),
        coalesce(sum(ih.comprimento_km), 0)
    INTO
        v_trechos_processados,
        v_comprimento_total_m,
        v_comprimento_total_km
    FROM resultados.intersecao_hidrografia AS ih
    WHERE ih.execucao_id = p_execucao_id
      AND ih.projeto_id = p_projeto_id
      AND ih.area_interesse_id = p_area_interesse_id;

    INSERT INTO logs.processamento (
        execucao_id,
        projeto_id,
        nivel,
        etapa,
        mensagem,
        detalhe
    )
    VALUES (
        p_execucao_id,
        p_projeto_id,
        'info',
        'processar_hidrografia_ana_mvp',
        'Processamento de hidrografia ANA concluido.',
        jsonb_build_object(
            'area_interesse_id', p_area_interesse_id,
            'trechos_processados', v_trechos_processados,
            'comprimento_total_m', v_comprimento_total_m,
            'comprimento_total_km', v_comprimento_total_km
        )
    );

    RETURN QUERY
    SELECT
        p_execucao_id AS resultado_execucao_id,
        v_trechos_processados AS trechos_processados,
        v_comprimento_total_m AS comprimento_total_m,
        v_comprimento_total_km AS comprimento_total_km;
EXCEPTION
    WHEN OTHERS THEN
        INSERT INTO logs.processamento (
            execucao_id,
            projeto_id,
            nivel,
            etapa,
            mensagem,
            detalhe
        )
        VALUES (
            p_execucao_id,
            p_projeto_id,
            'erro',
            'processar_hidrografia_ana_mvp',
            SQLERRM,
            jsonb_build_object(
                'area_interesse_id', p_area_interesse_id,
                'sqlstate', SQLSTATE
            )
        );

        RAISE;
END;
$$;

-- ============================================================================
-- 3. Views tecnicas e de relatorio
-- ============================================================================

-- Views de apresentacao podem ser recriadas com nova estrutura de colunas.
-- Nao usar CASCADE e nao apagar tabelas-base.
DROP VIEW IF EXISTS resultados.vw_hidrografia_resumo;
DROP VIEW IF EXISTS resultados.vw_hidrografia_microbacias;
DROP VIEW IF EXISTS resultados.vw_hidrografia_buffer_1000m;
DROP VIEW IF EXISTS resultados.vw_hidrografia_area_interesse;

CREATE OR REPLACE VIEW resultados.vw_hidrografia_area_interesse AS
SELECT
    ih.execucao_id,
    ih.projeto_id,
    ih.area_interesse_id,
    ih.unidade_analise,
    ih.cd_micro,
    ih.nm_micro,
    ih.nm_rio_pri,
    ih.fid_ana,
    ih.wtc_pk,
    ih.idcda,
    ih.cocursodag,
    ih.cocdadesag,
    ih.nunivotcda,
    ih.nuordemcda,
    ih.dedominial,
    ih.dsversao,
    ih.codigo_trecho,
    ih.codigo_curso,
    ih.nome_curso,
    ih.comprimento_m,
    ih.comprimento_km,
    ih.nucompcda_original,
    ih.atributos_origem::text AS atributos_origem_json,
    ih.geom
FROM resultados.intersecao_hidrografia AS ih
WHERE ih.unidade_analise = 'area_interesse';

CREATE OR REPLACE VIEW resultados.vw_hidrografia_buffer_1000m AS
SELECT
    ih.execucao_id,
    ih.projeto_id,
    ih.area_interesse_id,
    ih.unidade_analise,
    ih.cd_micro,
    ih.nm_micro,
    ih.nm_rio_pri,
    ih.fid_ana,
    ih.wtc_pk,
    ih.idcda,
    ih.cocursodag,
    ih.cocdadesag,
    ih.nunivotcda,
    ih.nuordemcda,
    ih.dedominial,
    ih.dsversao,
    ih.codigo_trecho,
    ih.codigo_curso,
    ih.nome_curso,
    ih.comprimento_m,
    ih.comprimento_km,
    ih.nucompcda_original,
    ih.atributos_origem::text AS atributos_origem_json,
    ih.geom
FROM resultados.intersecao_hidrografia AS ih
WHERE ih.unidade_analise = 'buffer_1000m';

CREATE OR REPLACE VIEW resultados.vw_hidrografia_microbacias AS
SELECT
    ih.execucao_id,
    ih.projeto_id,
    ih.area_interesse_id,
    ih.unidade_analise,
    ih.cd_micro,
    ih.nm_micro,
    ih.nm_rio_pri,
    ih.fid_ana,
    ih.wtc_pk,
    ih.idcda,
    ih.cocursodag,
    ih.cocdadesag,
    ih.nunivotcda,
    ih.nuordemcda,
    ih.dedominial,
    ih.dsversao,
    ih.codigo_trecho,
    ih.codigo_curso,
    ih.nome_curso,
    ih.comprimento_m,
    ih.comprimento_km,
    ih.nucompcda_original,
    ih.atributos_origem::text AS atributos_origem_json,
    ih.geom
FROM resultados.intersecao_hidrografia AS ih
WHERE ih.unidade_analise = 'microbacia';

CREATE OR REPLACE VIEW resultados.vw_hidrografia_resumo AS
SELECT
    ih.execucao_id,
    ih.projeto_id,
    ih.area_interesse_id,
    ih.unidade_analise,
    ih.cd_micro,
    ih.nm_micro,
    ih.nm_rio_pri,
    ih.nuordemcda,
    ih.nunivotcda,
    count(*)::integer AS quantidade_trechos,
    round(sum(ih.comprimento_m)::numeric, 4) AS comprimento_total_m,
    round(sum(ih.comprimento_km)::numeric, 6) AS comprimento_total_km
FROM resultados.intersecao_hidrografia AS ih
GROUP BY
    ih.execucao_id,
    ih.projeto_id,
    ih.area_interesse_id,
    ih.unidade_analise,
    ih.cd_micro,
    ih.nm_micro,
    ih.nm_rio_pri,
    ih.nuordemcda,
    ih.nunivotcda;

-- ============================================================================
-- 4. Consultas de conferencia para uso manual apos execucao autorizada
-- ============================================================================

/*
-- Processar hidrografia ANA:
SELECT *
FROM resultados.processar_hidrografia_ana_mvp(7::bigint, 1::bigint, 1::bigint);

-- Conferir resumo:
SELECT *
FROM resultados.vw_hidrografia_resumo
WHERE execucao_id = 7
  AND projeto_id = 1
  AND area_interesse_id = 1
ORDER BY unidade_analise, nm_micro, nuordemcda, nunivotcda;

-- Conferir trechos por area de interesse:
SELECT *
FROM resultados.vw_hidrografia_area_interesse
WHERE execucao_id = 7
  AND projeto_id = 1
  AND area_interesse_id = 1
ORDER BY comprimento_m DESC;

-- Conferir trechos por buffer:
SELECT *
FROM resultados.vw_hidrografia_buffer_1000m
WHERE execucao_id = 7
  AND projeto_id = 1
  AND area_interesse_id = 1
ORDER BY comprimento_m DESC;

-- Conferir trechos por microbacia:
SELECT *
FROM resultados.vw_hidrografia_microbacias
WHERE execucao_id = 7
  AND projeto_id = 1
  AND area_interesse_id = 1
ORDER BY nm_micro, comprimento_m DESC;
*/
