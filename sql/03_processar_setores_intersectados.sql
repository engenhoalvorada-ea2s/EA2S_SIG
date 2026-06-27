/*
EA2S SIG - 03_processar_setores_intersectados.sql

Conteudo sincronizado com a funcao real extraida do banco via pg_get_functiondef
e validada no DBeaver.

Preservar:
- assinatura e ordem dos parametros;
- p_execucao_id bigint DEFAULT NULL;
- RETURNS TABLE;
- tabelas e colunas reais;
- DELETE controlado por execucao_id, projeto_id e area_interesse_id;
- logs em logs.processamento;
- tratamento de erro;
- aliases explicitos para evitar ambiguidade.

Nao executar sem autorizacao explicita.
*/

CREATE OR REPLACE FUNCTION resultados.processar_setores_intersectados(
    p_projeto_id bigint,
    p_area_interesse_id bigint,
    p_execucao_id bigint DEFAULT NULL::bigint
)
RETURNS TABLE (
    resultado_execucao_id bigint,
    setores_processados integer,
    area_total_intersectada_m2 numeric
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_execucao_id bigint;
    v_setores_processados integer := 0;
    v_area_total_intersectada_m2 numeric := 0;
BEGIN
    IF p_execucao_id IS NULL THEN
        INSERT INTO resultados.execucao (
            projeto_id,
            nome,
            tipo_execucao,
            status,
            parametros,
            iniciado_em,
            usuario
        )
        VALUES (
            p_projeto_id,
            'Processamento de setores intersectados',
            'setores_intersectados',
            'em_execucao',
            jsonb_build_object('area_interesse_id', p_area_interesse_id),
            now(),
            current_user
        )
        RETURNING id INTO v_execucao_id;
    ELSE
        v_execucao_id := p_execucao_id;
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
        v_execucao_id,
        p_projeto_id,
        'info',
        'processar_setores_intersectados',
        'Inicio do processamento de setores intersectados.',
        'area_interesse_id=' || p_area_interesse_id::text
    );

    DELETE FROM resultados.setores_intersectados AS si
    WHERE si.execucao_id = v_execucao_id
      AND si.projeto_id = p_projeto_id
      AND si.area_interesse_id = p_area_interesse_id;

    WITH area_interesse_base AS (
        SELECT
            ai.id AS area_interesse_id,
            ai.projeto_id AS projeto_id,
            ST_Transform(ai.geom, 31982) AS geom_31982,
            ST_Area(ST_Transform(ai.geom, 31982)) AS area_interesse_m2
        FROM projetos.area_interesse AS ai
        WHERE ai.id = p_area_interesse_id
          AND ai.projeto_id = p_projeto_id
    ),
    setores_base AS (
        SELECT
            public.ea2s_normalizar_codigo_setor(sc.cd_setor::text) AS cd_setor,
            ST_Transform(sc.geom, 31982) AS geom_31982
        FROM urbano.setores_censo_2022_malha_br AS sc
        WHERE sc.geom IS NOT NULL
    ),
    intersecoes AS (
        SELECT
            v_execucao_id AS execucao_id,
            ai.projeto_id AS projeto_id,
            ai.area_interesse_id AS area_interesse_id,
            setor.cd_setor AS cd_setor,
            ST_Multi(ST_CollectionExtract(ST_Intersection(setor.geom_31982, ai.geom_31982), 3)) AS geom,
            ST_Area(setor.geom_31982) AS area_setor_total_m2,
            ai.area_interesse_m2 AS area_interesse_m2
        FROM area_interesse_base AS ai
        INNER JOIN setores_base AS setor
            ON ST_Intersects(setor.geom_31982, ai.geom_31982)
        WHERE setor.cd_setor IS NOT NULL
          AND ST_IsValid(setor.geom_31982)
          AND ST_IsValid(ai.geom_31982)
    ),
    calculos AS (
        SELECT
            inter.execucao_id AS execucao_id,
            inter.projeto_id AS projeto_id,
            inter.area_interesse_id AS area_interesse_id,
            inter.cd_setor AS cd_setor,
            ST_Area(inter.geom) AS area_intersecao_m2,
            ST_Area(inter.geom) / 10000.0 AS area_intersecao_ha,
            inter.area_setor_total_m2 AS area_setor_total_m2,
            CASE
                WHEN inter.area_setor_total_m2 > 0 THEN (ST_Area(inter.geom) / inter.area_setor_total_m2) * 100
                ELSE 0
            END AS percentual_setor_intersectado,
            CASE
                WHEN inter.area_interesse_m2 > 0 THEN (ST_Area(inter.geom) / inter.area_interesse_m2) * 100
                ELSE 0
            END AS percentual_area_interesse,
            inter.geom AS geom
        FROM intersecoes AS inter
        WHERE NOT ST_IsEmpty(inter.geom)
          AND ST_Area(inter.geom) > 0
    )
    INSERT INTO resultados.setores_intersectados (
        execucao_id,
        projeto_id,
        area_interesse_id,
        cd_setor,
        area_intersecao_m2,
        area_intersecao_ha,
        area_setor_total_m2,
        percentual_setor_intersectado,
        percentual_area_interesse,
        geom
    )
    SELECT
        calc.execucao_id,
        calc.projeto_id,
        calc.area_interesse_id,
        calc.cd_setor,
        calc.area_intersecao_m2,
        calc.area_intersecao_ha,
        calc.area_setor_total_m2,
        calc.percentual_setor_intersectado,
        calc.percentual_area_interesse,
        calc.geom
    FROM calculos AS calc;

    SELECT
        count(*)::integer,
        coalesce(sum(si.area_intersecao_m2), 0)
    INTO
        v_setores_processados,
        v_area_total_intersectada_m2
    FROM resultados.setores_intersectados AS si
    WHERE si.execucao_id = v_execucao_id
      AND si.projeto_id = p_projeto_id
      AND si.area_interesse_id = p_area_interesse_id;

    UPDATE resultados.execucao AS exe
    SET
        status = 'concluida',
        mensagem = 'Processamento de setores intersectados concluido.',
        finalizado_em = now()
    WHERE exe.id = v_execucao_id;

    INSERT INTO logs.processamento (
        execucao_id,
        projeto_id,
        nivel,
        etapa,
        mensagem,
        detalhe
    )
    VALUES (
        v_execucao_id,
        p_projeto_id,
        'info',
        'processar_setores_intersectados',
        'Processamento de setores intersectados concluido.',
        'area_interesse_id=' || p_area_interesse_id::text ||
        '; setores_processados=' || v_setores_processados::text ||
        '; area_total_intersectada_m2=' || v_area_total_intersectada_m2::text
    );

    RETURN QUERY
    SELECT
        v_execucao_id AS resultado_execucao_id,
        v_setores_processados AS setores_processados,
        v_area_total_intersectada_m2 AS area_total_intersectada_m2;
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
            coalesce(v_execucao_id, p_execucao_id),
            p_projeto_id,
            'erro',
            'processar_setores_intersectados',
            SQLERRM,
            'area_interesse_id=' || p_area_interesse_id::text || '; sqlstate=' || SQLSTATE
        );

        IF v_execucao_id IS NOT NULL THEN
            UPDATE resultados.execucao AS exe
            SET
                status = 'erro',
                mensagem = SQLERRM,
                finalizado_em = now()
            WHERE exe.id = v_execucao_id;
        END IF;

        RAISE;
END;
$$;

-- Chamada validada manualmente no DBeaver:
-- SELECT * FROM resultados.processar_setores_intersectados(1, 1, 4);
-- Resultado validado: resultado_execucao_id = 4, 4 setores, area total = 340007.1304 m2.
