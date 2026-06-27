/*
EA2S SIG - 04_calcular_indicadores_socioeconomicos.sql

Conteudo sincronizado com a funcao real extraida do banco via pg_get_functiondef
e validada no DBeaver.

Preservar:
- assinatura e ordem dos parametros: p_execucao_id, p_projeto_id, p_area_interesse_id;
- RETURNS TABLE;
- JOIN com a tabela de origem, nao LEFT JOIN;
- filtro de valores nulos/nao numericos com public.ea2s_safe_numeric(... ) IS NOT NULL;
- DELETE controlado por execucao_id, projeto_id e area_interesse_id;
- logs em logs.processamento;
- aliases explicitos para evitar ambiguidade.

Observacao: usar LEFT JOIN para manter setores sem dados socioeconomicos pode ser
uma melhoria futura, mas nao faz parte da funcao validada no banco.
Nao executar sem autorizacao explicita.
*/

CREATE OR REPLACE FUNCTION resultados.calcular_indicadores_socioeconomicos_mvp(
    p_execucao_id bigint,
    p_projeto_id bigint,
    p_area_interesse_id bigint
)
RETURNS TABLE (
    total_indicadores_processados integer,
    total_registros_detalhe integer
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_ind record;
    v_sql text;
    v_total_indicadores_processados integer := 0;
    v_total_registros_detalhe integer := 0;
    v_registros_indicador integer := 0;
BEGIN
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
        'calcular_indicadores_socioeconomicos_mvp',
        'Inicio do calculo de indicadores socioeconomicos.',
        'area_interesse_id=' || p_area_interesse_id::text
    );

    DELETE FROM resultados.indicador_socioeconomico_detalhe AS det
    WHERE det.execucao_id = p_execucao_id
      AND det.projeto_id = p_projeto_id
      AND det.area_interesse_id = p_area_interesse_id;

    DELETE FROM resultados.indicador_socioeconomico_resumo AS res
    WHERE res.execucao_id = p_execucao_id
      AND res.projeto_id = p_projeto_id
      AND res.area_interesse_id = p_area_interesse_id;

    FOR v_ind IN
        SELECT
            ind.id AS indicador_id,
            ind.nome_logico AS nome_logico,
            ind.tema AS tema,
            ind.subtema AS subtema,
            ind.descricao AS descricao,
            ind.schema_tabela_dados AS schema_tabela_dados,
            ind.tabela_dados AS tabela_dados,
            ind.campo_codigo_setor AS campo_codigo_setor,
            ind.campo_valor AS campo_valor,
            ind.unidade AS unidade,
            ind.tipo_indicador AS tipo_indicador,
            ind.metodo_estimativa AS metodo_estimativa
        FROM config.indicadores_mvp AS ind
        WHERE ind.ativo = true
        ORDER BY ind.prioridade NULLS LAST, ind.id
    LOOP
        v_sql := format($fmt$
            INSERT INTO resultados.indicador_socioeconomico_detalhe (
                execucao_id,
                projeto_id,
                area_interesse_id,
                indicador_id,
                cd_setor,
                nome_logico_indicador,
                tema,
                subtema,
                tabela_origem,
                campo_origem,
                valor_original,
                percentual_setor_intersectado,
                valor_estimado,
                metodo_estimativa,
                observacao
            )
            SELECT
                si.execucao_id AS execucao_id,
                si.projeto_id AS projeto_id,
                si.area_interesse_id AS area_interesse_id,
                %s AS indicador_id,
                si.cd_setor AS cd_setor,
                %L AS nome_logico_indicador,
                %L AS tema,
                %L AS subtema,
                %L AS tabela_origem,
                %L AS campo_origem,
                public.ea2s_safe_numeric(d.%I::text) AS valor_original,
                si.percentual_setor_intersectado AS percentual_setor_intersectado,
                public.ea2s_safe_numeric(d.%I::text) * (si.percentual_setor_intersectado / 100.0) AS valor_estimado,
                %L AS metodo_estimativa,
                'Estimativa por ponderacao areal a partir de setores intersectados.' AS observacao
            FROM resultados.setores_intersectados AS si
            JOIN %I.%I AS d
                ON public.ea2s_normalizar_codigo_setor(d.%I::text) = si.cd_setor
            WHERE si.execucao_id = $1
              AND si.projeto_id = $2
              AND si.area_interesse_id = $3
              AND public.ea2s_safe_numeric(d.%I::text) IS NOT NULL
        $fmt$,
            v_ind.indicador_id,
            v_ind.nome_logico,
            v_ind.tema,
            v_ind.subtema,
            v_ind.schema_tabela_dados || '.' || v_ind.tabela_dados,
            v_ind.campo_valor,
            v_ind.campo_valor,
            v_ind.campo_valor,
            v_ind.metodo_estimativa,
            v_ind.schema_tabela_dados,
            v_ind.tabela_dados,
            v_ind.campo_codigo_setor,
            v_ind.campo_valor
        );

        EXECUTE v_sql USING p_execucao_id, p_projeto_id, p_area_interesse_id;
        GET DIAGNOSTICS v_registros_indicador = ROW_COUNT;

        IF v_registros_indicador > 0 THEN
            v_total_indicadores_processados := v_total_indicadores_processados + 1;
            v_total_registros_detalhe := v_total_registros_detalhe + v_registros_indicador;

            INSERT INTO resultados.indicador_socioeconomico_resumo (
                execucao_id,
                projeto_id,
                area_interesse_id,
                indicador_id,
                nome_logico_indicador,
                tema,
                subtema,
                descricao,
                unidade,
                valor_estimado_total,
                valor_medio_ponderado,
                numero_setores,
                area_total_intersectada_m2,
                metodo_estimativa,
                observacao
            )
            SELECT
                p_execucao_id AS execucao_id,
                p_projeto_id AS projeto_id,
                p_area_interesse_id AS area_interesse_id,
                v_ind.indicador_id AS indicador_id,
                v_ind.nome_logico AS nome_logico_indicador,
                v_ind.tema AS tema,
                v_ind.subtema AS subtema,
                v_ind.descricao AS descricao,
                v_ind.unidade AS unidade,
                sum(det.valor_estimado) AS valor_estimado_total,
                sum(det.valor_estimado) / NULLIF(sum(si.percentual_setor_intersectado / 100.0), 0) AS valor_medio_ponderado,
                count(det.id)::integer AS numero_setores,
                sum(si.area_intersecao_m2) AS area_total_intersectada_m2,
                v_ind.metodo_estimativa AS metodo_estimativa,
                'Resumo calculado a partir dos detalhes por setor.' AS observacao
            FROM resultados.indicador_socioeconomico_detalhe AS det
            JOIN resultados.setores_intersectados AS si
                ON si.execucao_id = det.execucao_id
                AND si.projeto_id = det.projeto_id
                AND si.area_interesse_id = det.area_interesse_id
                AND si.cd_setor = det.cd_setor
            WHERE det.execucao_id = p_execucao_id
              AND det.projeto_id = p_projeto_id
              AND det.area_interesse_id = p_area_interesse_id
              AND det.indicador_id = v_ind.indicador_id;
        END IF;
    END LOOP;

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
        'calcular_indicadores_socioeconomicos_mvp',
        'Calculo de indicadores socioeconomicos concluido.',
        'area_interesse_id=' || p_area_interesse_id::text ||
        '; total_indicadores_processados=' || v_total_indicadores_processados::text ||
        '; total_registros_detalhe=' || v_total_registros_detalhe::text
    );

    RETURN QUERY
    SELECT
        v_total_indicadores_processados AS total_indicadores_processados,
        v_total_registros_detalhe AS total_registros_detalhe;
END;
$$;

-- Chamada validada manualmente no DBeaver:
-- SELECT * FROM resultados.calcular_indicadores_socioeconomicos_mvp(4, 1, 1);
-- Resultado validado: gerou registros em resultados.indicador_socioeconomico_detalhe e resultados.indicador_socioeconomico_resumo.

