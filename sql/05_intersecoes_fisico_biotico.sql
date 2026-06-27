/*
EA2S SIG - 05_intersecoes_fisico_biotico.sql

PROPOSTA LOCAL, AINDA NAO EXECUTADA.

Objetivo:
Definir estrutura inicial revisavel para a tabela
resultados.intersecao_fisico_biotica e para a funcao futura de intersecoes
entre unidades de analise e camadas ambientais.

Nao executar sem revisao e autorizacao explicita.
Nao alterar dados oficiais dos schemas geologia, geomorfologia, hidrogeologia,
pedologia, vegetacao, hidrografia ou urbano.

Este script proposto cria/altera apenas objetos no schema resultados e grava
logs no schema logs ja existente.

Regras metodologicas:
- transformar geometrias para EPSG:31982 antes de calcular areas;
- usar ST_MakeValid, ST_CollectionExtract(..., 3) e ST_Multi para garantir saida MultiPolygon;
- calcular area em m2, hectares e percentual da unidade de analise;
- guardar atributos complementares em jsonb;
- preservar atributos originais da feicao oficial em atributos_origem jsonb, sem geometria;
- unidades previstas: area_interesse, buffer_1000m, microbacia;
- buffer_1000m representa o buffer completo de 1000 m ao redor da area, incluindo a propria area;
- entorno_1000m, excluindo a area de interesse, pode ser avaliado como melhoria futura;
- microbacia considera todas as microbacias interceptadas pela area de interesse;
- a microbacia dominante podera ser indicada posteriormente em tabela de resumo ou texto tecnico;
- temas previstos: geologia, geomorfologia, hidrogeologia, pedologia, vegetacao.

Observacao de performance:
- a proposta usa filtros de bounding box (&&) antes de transformar/intersectar
  geometrias completas nas microbacias e camadas ambientais;
- melhorias futuras podem incluir indices funcionais, materializacao previa em
  EPSG:31982 ou tabelas intermediarias por unidade de analise.
*/

-- ============================================================================
-- 1. Tabela proposta
-- ============================================================================

CREATE TABLE IF NOT EXISTS resultados.intersecao_fisico_biotica (
    id bigserial PRIMARY KEY,
    execucao_id bigint NOT NULL,
    projeto_id bigint NOT NULL,
    area_interesse_id bigint NOT NULL,
    unidade_analise text NOT NULL,
    unidade_analise_codigo text,
    unidade_analise_nome text,
    tema text NOT NULL,
    camada_origem text NOT NULL,
    fonte_schema text,
    fonte_tabela text,
    fonte_camada text,
    feicao_origem_id text,
    campo_principal text,
    valor_principal text,
    atributos_complementares jsonb,
    atributos_origem jsonb,
    area_intersecao_m2 numeric,
    area_intersecao_ha numeric,
    area_unidade_analise_m2 numeric,
    percentual_unidade_analise numeric,
    geom geometry(MultiPolygon, 31982),
    data_cadastro timestamp DEFAULT now(),
    CONSTRAINT intersecao_fisico_biotica_unidade_chk CHECK (
        unidade_analise IN ('area_interesse', 'buffer_1000m', 'microbacia')
    ),
    CONSTRAINT intersecao_fisico_biotica_tema_chk CHECK (
        tema IN ('geologia', 'geomorfologia', 'hidrogeologia', 'pedologia', 'vegetacao')
    ),
    CONSTRAINT intersecao_fisico_biotica_percentual_chk CHECK (
        percentual_unidade_analise IS NULL
        OR (percentual_unidade_analise >= 0 AND percentual_unidade_analise <= 100)
    )
);

ALTER TABLE resultados.intersecao_fisico_biotica
    ADD COLUMN IF NOT EXISTS unidade_analise_codigo text,
    ADD COLUMN IF NOT EXISTS unidade_analise_nome text,
    ADD COLUMN IF NOT EXISTS feicao_origem_id text,
    ADD COLUMN IF NOT EXISTS fonte_schema text,
    ADD COLUMN IF NOT EXISTS fonte_tabela text,
    ADD COLUMN IF NOT EXISTS fonte_camada text,
    ADD COLUMN IF NOT EXISTS atributos_origem jsonb;

ALTER TABLE resultados.intersecao_fisico_biotica
    ALTER COLUMN execucao_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_intersecao_fisico_biotica_contexto
    ON resultados.intersecao_fisico_biotica(execucao_id, projeto_id, area_interesse_id);

CREATE INDEX IF NOT EXISTS idx_intersecao_fisico_biotica_unidade_tema
    ON resultados.intersecao_fisico_biotica(unidade_analise, tema);

CREATE INDEX IF NOT EXISTS idx_intersecao_fisico_biotica_geom
    ON resultados.intersecao_fisico_biotica USING gist(geom);

-- ============================================================================
-- 2. Funcao proposta
-- ============================================================================

CREATE OR REPLACE FUNCTION resultados.processar_intersecoes_fisico_bioticas_mvp(
    p_execucao_id bigint,
    p_projeto_id bigint,
    p_area_interesse_id bigint
)
RETURNS TABLE (
    total_registros integer,
    area_total_registrada_m2 numeric
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_total_registros integer := 0;
    v_area_total_registrada_m2 numeric := 0;
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
        'processar_intersecoes_fisico_bioticas_mvp',
        'Inicio do processamento de intersecoes fisico-bioticas.',
        jsonb_build_object(
            'area_interesse_id', p_area_interesse_id
        )
    );

    DELETE FROM resultados.intersecao_fisico_biotica AS ifb
    WHERE ifb.execucao_id = p_execucao_id
      AND ifb.projeto_id = p_projeto_id
      AND ifb.area_interesse_id = p_area_interesse_id;

    WITH area_interesse AS (
        SELECT
            ai.id AS area_interesse_id,
            ai.projeto_id AS projeto_id,
            ai.nome AS area_interesse_nome,
            ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Transform(ai.geom, 31982)), 3))::geometry(MultiPolygon, 31982) AS geom_31982
        FROM projetos.area_interesse AS ai
        WHERE ai.id = p_area_interesse_id
          AND ai.projeto_id = p_projeto_id
    ),
    microbacia_base AS (
        SELECT
            mb.cd_micro,
            mb.nm_micro,
            mb.nm_rio_pri,
            mb.cd_otto_1,
            mb.cd_otto_2,
            mb.cd_otto_3,
            mb.cd_otto_4,
            mb.cd_otto_5,
            mb.cd_otto_6,
            mb.cd_otto_7,
            mb.cd_bacia,
            mb.cd_ibge_mu,
            mb.sg_tipo,
            mb.vl_qmin7,
            mb.nm_qmin7,
            mb.vl_qrest,
            mb.vl_qsubt,
            mb.shape_area,
            mb.shape_len,
            ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Transform(mb.geom, 31982)), 3))::geometry(MultiPolygon, 31982) AS geom_31982
        FROM hidrografia.microbacias_sigeo_sirhesc_aguassc AS mb
        INNER JOIN area_interesse AS ai
            ON mb.geom && ST_Transform(ai.geom_31982, 29192)
            AND ST_Intersects(ST_MakeValid(ST_Transform(mb.geom, 31982)), ai.geom_31982)
    ),
    unidades_analise AS (
        SELECT
            'area_interesse'::text AS unidade_analise,
            ai.area_interesse_id::text AS unidade_analise_codigo,
            COALESCE(ai.area_interesse_nome, 'Area de interesse')::text AS unidade_analise_nome,
            ai.geom_31982 AS geom_31982,
            jsonb_build_object('origem', 'projetos.area_interesse') AS atributos_unidade
        FROM area_interesse AS ai

        UNION ALL

        SELECT
            'buffer_1000m'::text AS unidade_analise,
            ai.area_interesse_id::text AS unidade_analise_codigo,
            ('Buffer 1000 m - ' || COALESCE(ai.area_interesse_nome, 'area de interesse'))::text AS unidade_analise_nome,
            ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Buffer(ai.geom_31982, 1000)), 3))::geometry(MultiPolygon, 31982) AS geom_31982,
            jsonb_build_object(
                'distancia_m', 1000,
                'origem', 'buffer completo da area_interesse',
                'inclui_area_interesse', true
            ) AS atributos_unidade
        FROM area_interesse AS ai

        UNION ALL

        SELECT
            'microbacia'::text AS unidade_analise,
            mb.cd_micro::text AS unidade_analise_codigo,
            mb.nm_micro::text AS unidade_analise_nome,
            mb.geom_31982 AS geom_31982,
            jsonb_build_object(
                'cd_micro', mb.cd_micro,
                'nm_micro', mb.nm_micro,
                'nm_rio_pri', mb.nm_rio_pri,
                'cd_otto_1', mb.cd_otto_1,
                'cd_otto_2', mb.cd_otto_2,
                'cd_otto_3', mb.cd_otto_3,
                'cd_otto_4', mb.cd_otto_4,
                'cd_otto_5', mb.cd_otto_5,
                'cd_otto_6', mb.cd_otto_6,
                'cd_otto_7', mb.cd_otto_7,
                'cd_bacia', mb.cd_bacia,
                'cd_ibge_mu', mb.cd_ibge_mu,
                'sg_tipo', mb.sg_tipo,
                'vl_qmin7', mb.vl_qmin7,
                'nm_qmin7', mb.nm_qmin7,
                'vl_qrest', mb.vl_qrest,
                'vl_qsubt', mb.vl_qsubt,
                'shape_area', mb.shape_area,
                'shape_len', mb.shape_len
            ) AS atributos_unidade
        FROM microbacia_base AS mb
    ),
    camadas AS (
        SELECT
            ua.unidade_analise,
            ua.unidade_analise_codigo,
            ua.unidade_analise_nome,
            'geologia'::text AS tema,
            'geologia.geologia_br_bdia_2025'::text AS camada_origem,
            'geologia'::text AS fonte_schema,
            'geologia_br_bdia_2025'::text AS fonte_tabela,
            'geologia'::text AS fonte_camada,
            geo.id::text AS feicao_origem_id,
            'nm_unidade'::text AS campo_principal,
            geo.nm_unidade::text AS valor_principal,
            jsonb_build_object(
                'letra_simb', geo.letra_simb,
                'nm_lito1', geo.nm_lito1,
                'nm_lito2', geo.nm_lito2,
                'nm_lito3', geo.nm_lito3,
                'nm_lito4', geo.nm_lito4,
                'nm_tempo_g', geo.nm_tempo_g,
                'nm_provinc', geo.nm_provinc,
                'nm_sub_pro', geo.nm_sub_pro
            ) || jsonb_build_object('unidade_analise', ua.atributos_unidade) AS atributos_complementares,
            to_jsonb(geo) - 'geom' - 'geometry' AS atributos_origem,
            ua.geom_31982 AS geom_unidade,
            ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Transform(geo.geom, 31982)), 3))::geometry(MultiPolygon, 31982) AS geom_camada
        FROM unidades_analise AS ua
        INNER JOIN geologia.geologia_br_bdia_2025 AS geo
            ON geo.geom && ST_Transform(ua.geom_31982, 4674)
            AND ST_Intersects(ST_MakeValid(ST_Transform(geo.geom, 31982)), ua.geom_31982)

        UNION ALL

        SELECT
            ua.unidade_analise,
            ua.unidade_analise_codigo,
            ua.unidade_analise_nome,
            'geomorfologia'::text AS tema,
            'geomorfologia.geomorfo_br_bdia_2025'::text AS camada_origem,
            'geomorfologia'::text AS fonte_schema,
            'geomorfo_br_bdia_2025'::text AS fonte_tabela,
            'geomorfologia'::text AS fonte_camada,
            geomorfo.id::text AS feicao_origem_id,
            'legenda'::text AS campo_principal,
            geomorfo.legenda::text AS valor_principal,
            jsonb_build_object(
                'nm_dominio', geomorfo.nm_dominio,
                'nm_regiao', geomorfo.nm_regiao,
                'nm_unidade', geomorfo.nm_unidade,
                'categoria', geomorfo.categoria,
                'natureza', geomorfo.natureza,
                'forma', geomorfo.forma,
                'dens_dren', geomorfo.dens_dren,
                'aprof_inci', geomorfo.aprof_inci,
                'niv_alt', geomorfo.niv_alt,
                'compartime', geomorfo.compartime
            ) || jsonb_build_object('unidade_analise', ua.atributos_unidade) AS atributos_complementares,
            to_jsonb(geomorfo) - 'geom' - 'geometry' AS atributos_origem,
            ua.geom_31982 AS geom_unidade,
            ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Transform(geomorfo.geom, 31982)), 3))::geometry(MultiPolygon, 31982) AS geom_camada
        FROM unidades_analise AS ua
        INNER JOIN geomorfologia.geomorfo_br_bdia_2025 AS geomorfo
            ON geomorfo.geom && ST_Transform(ua.geom_31982, 4674)
            AND ST_Intersects(ST_MakeValid(ST_Transform(geomorfo.geom, 31982)), ua.geom_31982)

        UNION ALL

        SELECT
            ua.unidade_analise,
            ua.unidade_analise_codigo,
            ua.unidade_analise_nome,
            'hidrogeologia'::text AS tema,
            'hidrogeologia.hidrogeologico_sul_bdia_2025'::text AS camada_origem,
            'hidrogeologia'::text AS fonte_schema,
            'hidrogeologico_sul_bdia_2025'::text AS fonte_tabela,
            'hidrogeologia'::text AS fonte_camada,
            hidro.id::text AS feicao_origem_id,
            'nome_unida'::text AS campo_principal,
            hidro.nome_unida::text AS valor_principal,
            jsonb_build_object(
                'cd_legenda', hidro.cd_legenda,
                'litologia', hidro.litologia,
                'provincia', hidro.provincia,
                'dominio', hidro.dominio,
                'vz_cl', hidro.vz_cl,
                'vze_cl', hidro.vze_cl,
                'vz_int_cl', hidro.vz_int_cl,
                'vze_int_cl', hidro.vze_int_cl,
                'domínio_da', hidro."domínio_da"
            ) || jsonb_build_object('unidade_analise', ua.atributos_unidade) AS atributos_complementares,
            to_jsonb(hidro) - 'geom' - 'geometry' AS atributos_origem,
            ua.geom_31982 AS geom_unidade,
            ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Transform(hidro.geom, 31982)), 3))::geometry(MultiPolygon, 31982) AS geom_camada
        FROM unidades_analise AS ua
        INNER JOIN hidrogeologia.hidrogeologico_sul_bdia_2025 AS hidro
            ON hidro.geom && ST_Transform(ua.geom_31982, 4674)
            AND ST_Intersects(ST_MakeValid(ST_Transform(hidro.geom, 31982)), ua.geom_31982)

        UNION ALL

        SELECT
            ua.unidade_analise,
            ua.unidade_analise_codigo,
            ua.unidade_analise_nome,
            'pedologia'::text AS tema,
            'pedologia.pedo_ordem_ibge_br'::text AS camada_origem,
            'pedologia'::text AS fonte_schema,
            'pedo_ordem_ibge_br'::text AS fonte_tabela,
            'pedologia'::text AS fonte_camada,
            pedo.id::text AS feicao_origem_id,
            'legenda'::text AS campo_principal,
            pedo.legenda::text AS valor_principal,
            jsonb_build_object(
                'area_km', pedo.area_km
            ) || jsonb_build_object('unidade_analise', ua.atributos_unidade) AS atributos_complementares,
            to_jsonb(pedo) - 'geom' - 'geometry' AS atributos_origem,
            ua.geom_31982 AS geom_unidade,
            ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Transform(pedo.geom, 31982)), 3))::geometry(MultiPolygon, 31982) AS geom_camada
        FROM unidades_analise AS ua
        INNER JOIN pedologia.pedo_ordem_ibge_br AS pedo
            ON pedo.geom && ST_Transform(ua.geom_31982, 4674)
            AND ST_Intersects(ST_MakeValid(ST_Transform(pedo.geom, 31982)), ua.geom_31982)

        UNION ALL

        SELECT
            ua.unidade_analise,
            ua.unidade_analise_codigo,
            ua.unidade_analise_nome,
            'vegetacao'::text AS tema,
            'vegetacao.vegetacao_br_bdia_2025'::text AS camada_origem,
            'vegetacao'::text AS fonte_schema,
            'vegetacao_br_bdia_2025'::text AS fonte_tabela,
            'vegetacao'::text AS fonte_camada,
            veg.id::text AS feicao_origem_id,
            'legenda'::text AS campo_principal,
            veg.legenda::text AS valor_principal,
            jsonb_build_object(
                'cd_fito', veg.cd_fito,
                'cd_leg_2', veg.cd_leg_2,
                'clas_domi', veg.clas_domi,
                'nm_uveg', veg.nm_uveg,
                'nm_uantr', veg.nm_uantr,
                'nm_contat', veg.nm_contat,
                'nm_pretet', veg.nm_pretet,
                'legenda_1', veg.legenda_1,
                'legenda_2', veg.legenda_2
            ) || jsonb_build_object('unidade_analise', ua.atributos_unidade) AS atributos_complementares,
            to_jsonb(veg) - 'geom' - 'geometry' AS atributos_origem,
            ua.geom_31982 AS geom_unidade,
            ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Transform(veg.geom, 31982)), 3))::geometry(MultiPolygon, 31982) AS geom_camada
        FROM unidades_analise AS ua
        INNER JOIN vegetacao.vegetacao_br_bdia_2025 AS veg
            ON veg.geom && ST_Transform(ua.geom_31982, 4674)
            AND ST_Intersects(ST_MakeValid(ST_Transform(veg.geom, 31982)), ua.geom_31982)
    ),
    intersecoes AS (
        SELECT
            camada.unidade_analise,
            camada.unidade_analise_codigo,
            camada.unidade_analise_nome,
            camada.tema,
            camada.camada_origem,
            camada.fonte_schema,
            camada.fonte_tabela,
            camada.fonte_camada,
            camada.feicao_origem_id,
            camada.campo_principal,
            camada.valor_principal,
            camada.atributos_complementares,
            camada.atributos_origem,
            ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Intersection(camada.geom_unidade, camada.geom_camada)), 3))::geometry(MultiPolygon, 31982) AS geom,
            ST_Area(camada.geom_unidade) AS area_unidade_analise_m2
        FROM camadas AS camada
    ),
    intersecoes_validas AS (
        SELECT
            inter.unidade_analise,
            inter.unidade_analise_codigo,
            inter.unidade_analise_nome,
            inter.tema,
            inter.camada_origem,
            inter.fonte_schema,
            inter.fonte_tabela,
            inter.fonte_camada,
            inter.feicao_origem_id,
            inter.campo_principal,
            inter.valor_principal,
            inter.atributos_complementares,
            inter.atributos_origem,
            round(ST_Area(inter.geom)::numeric, 4) AS area_intersecao_m2,
            round((ST_Area(inter.geom) / 10000.0)::numeric, 6) AS area_intersecao_ha,
            round(inter.area_unidade_analise_m2::numeric, 4) AS area_unidade_analise_m2,
            CASE
                WHEN inter.area_unidade_analise_m2 > 0 THEN round(
                    LEAST(
                        100.0,
                        GREATEST(
                            0.0,
                            (ST_Area(inter.geom) / inter.area_unidade_analise_m2) * 100.0
                        )
                    )::numeric,
                    8
                )
                ELSE NULL
            END AS percentual_unidade_analise,
            inter.geom
        FROM intersecoes AS inter
        WHERE NOT ST_IsEmpty(inter.geom)
          AND ST_Area(inter.geom) > 0
    )
    INSERT INTO resultados.intersecao_fisico_biotica (
        execucao_id,
        projeto_id,
        area_interesse_id,
        unidade_analise,
        unidade_analise_codigo,
        unidade_analise_nome,
        tema,
        camada_origem,
        fonte_schema,
        fonte_tabela,
        fonte_camada,
        feicao_origem_id,
        campo_principal,
        valor_principal,
        atributos_complementares,
        atributos_origem,
        area_intersecao_m2,
        area_intersecao_ha,
        area_unidade_analise_m2,
        percentual_unidade_analise,
        geom
    )
    SELECT
        p_execucao_id,
        p_projeto_id,
        p_area_interesse_id,
        iv.unidade_analise,
        iv.unidade_analise_codigo,
        iv.unidade_analise_nome,
        iv.tema,
        iv.camada_origem,
        iv.fonte_schema,
        iv.fonte_tabela,
        iv.fonte_camada,
        iv.feicao_origem_id,
        iv.campo_principal,
        iv.valor_principal,
        iv.atributos_complementares,
        iv.atributos_origem,
        iv.area_intersecao_m2,
        iv.area_intersecao_ha,
        iv.area_unidade_analise_m2,
        iv.percentual_unidade_analise,
        iv.geom
    FROM intersecoes_validas AS iv;

    SELECT
        count(*)::integer,
        coalesce(sum(ifb.area_intersecao_m2), 0)
    INTO
        v_total_registros,
        v_area_total_registrada_m2
    FROM resultados.intersecao_fisico_biotica AS ifb
    WHERE ifb.execucao_id = p_execucao_id
      AND ifb.projeto_id = p_projeto_id
      AND ifb.area_interesse_id = p_area_interesse_id;

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
        'processar_intersecoes_fisico_bioticas_mvp',
        'Processamento de intersecoes fisico-bioticas concluido.',
        jsonb_build_object(
            'area_interesse_id', p_area_interesse_id,
            'total_registros', v_total_registros,
            'area_total_registrada_m2', v_area_total_registrada_m2
        )
    );

    RETURN QUERY
    SELECT
        v_total_registros AS total_registros,
        v_area_total_registrada_m2 AS area_total_registrada_m2;
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
            'processar_intersecoes_fisico_bioticas_mvp',
            SQLERRM,
            jsonb_build_object(
                'area_interesse_id', p_area_interesse_id,
                'sqlstate', SQLSTATE
            )
        );

        RAISE;
END;
$$;

-- Exemplo futuro, somente apos revisao e autorizacao:
-- SELECT * FROM resultados.processar_intersecoes_fisico_bioticas_mvp(4, 1, 1);
