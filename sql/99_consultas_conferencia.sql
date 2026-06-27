/*
EA2S SIG - 99_consultas_conferencia.sql

Consultas de conferencia para uso apos execucoes autorizadas.
Nao altera dados.

Conferencia final validada no DBeaver: os 4 setores da execucao_id = 4, projeto_id = 1, area_interesse_id = 1 retornaram ok para as quatro tabelas socioeconomicas.

Substituir os parametros abaixo no DBeaver antes de executar:
- :id_processamento
- :id_projeto
- :id_area_interesse
*/

-- 1. Resumo de setores intersectados por execucao/projeto/area
SELECT
    si.execucao_id,
    si.projeto_id,
    si.area_interesse_id,
    count(*) AS qtd_setores,
    sum(si.area_intersecao_m2) AS area_intersecao_total_m2,
    sum(si.area_intersecao_ha) AS area_intersecao_total_ha,
    sum(si.percentual_area_interesse) AS fechamento_area_percentual,
    min(si.percentual_setor_intersectado) AS menor_percentual_setor,
    max(si.percentual_setor_intersectado) AS maior_percentual_setor
FROM resultados.setores_intersectados AS si
WHERE si.execucao_id = :id_processamento
  AND si.projeto_id = :id_projeto
  AND si.area_interesse_id = :id_area_interesse
GROUP BY
    si.execucao_id,
    si.projeto_id,
    si.area_interesse_id;

-- 2. Setores duplicados na mesma execucao
SELECT
    si.execucao_id,
    si.cd_setor,
    count(*) AS qtd_registros
FROM resultados.setores_intersectados AS si
WHERE si.execucao_id = :id_processamento
GROUP BY
    si.execucao_id,
    si.cd_setor
HAVING count(*) > 1
ORDER BY qtd_registros DESC, si.cd_setor;

-- 3. Percentuais fora da faixa esperada
SELECT
    si.execucao_id,
    si.cd_setor,
    si.percentual_setor_intersectado,
    si.percentual_area_interesse,
    si.area_setor_total_m2,
    si.area_intersecao_m2
FROM resultados.setores_intersectados AS si
WHERE si.execucao_id = :id_processamento
  AND (
      si.percentual_setor_intersectado < 0
      OR si.percentual_setor_intersectado > 100
      OR si.percentual_area_interesse < 0
      OR si.percentual_area_interesse > 100
  )
ORDER BY si.cd_setor;

-- 4. Indicadores calculados sem cadastro ativo
SELECT
    det.execucao_id,
    det.indicador_id,
    det.nome_logico_indicador,
    count(*) AS qtd_linhas
FROM resultados.indicador_socioeconomico_detalhe AS det
LEFT JOIN config.indicadores_mvp AS ind
    ON ind.id = det.indicador_id
WHERE det.execucao_id = :id_processamento
  AND ind.id IS NULL
GROUP BY
    det.execucao_id,
    det.indicador_id,
    det.nome_logico_indicador
ORDER BY det.nome_logico_indicador;

-- 5. Divergencia entre detalhe e resumo por indicador
WITH detalhe AS (
    SELECT
        det.execucao_id,
        det.projeto_id,
        det.area_interesse_id,
        det.indicador_id,
        det.nome_logico_indicador,
        sum(det.valor_estimado) AS valor_detalhe,
        count(*) AS numero_setores_detalhe
    FROM resultados.indicador_socioeconomico_detalhe AS det
    WHERE det.execucao_id = :id_processamento
      AND det.projeto_id = :id_projeto
      AND det.area_interesse_id = :id_area_interesse
    GROUP BY
        det.execucao_id,
        det.projeto_id,
        det.area_interesse_id,
        det.indicador_id,
        det.nome_logico_indicador
)
SELECT
    detalhe.execucao_id,
    detalhe.indicador_id,
    detalhe.nome_logico_indicador,
    detalhe.valor_detalhe,
    resumo.valor_estimado_total AS valor_resumo,
    detalhe.valor_detalhe - resumo.valor_estimado_total AS diferenca,
    detalhe.numero_setores_detalhe,
    resumo.numero_setores AS numero_setores_resumo
FROM detalhe
INNER JOIN resultados.indicador_socioeconomico_resumo AS resumo
    ON resumo.execucao_id = detalhe.execucao_id
    AND resumo.indicador_id = detalhe.indicador_id
WHERE abs(coalesce(detalhe.valor_detalhe, 0) - coalesce(resumo.valor_estimado_total, 0)) > 0.0001
   OR detalhe.numero_setores_detalhe <> resumo.numero_setores
ORDER BY detalhe.nome_logico_indicador;

-- 6. Area intersectada fechando proxima de 100% da area de interesse
SELECT
    si.execucao_id,
    si.projeto_id,
    si.area_interesse_id,
    ai.area_m2 AS area_interesse_m2,
    sum(si.area_intersecao_m2) AS area_setores_intersectada_m2,
    sum(si.percentual_area_interesse) AS percentual_cobertura_area_interesse
FROM resultados.setores_intersectados AS si
INNER JOIN projetos.area_interesse AS ai
    ON ai.id = si.area_interesse_id
    AND ai.projeto_id = si.projeto_id
WHERE si.execucao_id = :id_processamento
  AND si.projeto_id = :id_projeto
  AND si.area_interesse_id = :id_area_interesse
GROUP BY
    si.execucao_id,
    si.projeto_id,
    si.area_interesse_id,
    ai.area_m2;

-- 7. Indicadores habilitados sem detalhe calculado
SELECT
    ind.id AS indicador_id,
    ind.nome_logico,
    ind.tema,
    ind.subtema,
    ind.tabela_dados,
    ind.campo_valor
FROM config.indicadores_mvp AS ind
LEFT JOIN resultados.indicador_socioeconomico_detalhe AS det
    ON det.indicador_id = ind.id
    AND det.execucao_id = :id_processamento
    AND det.projeto_id = :id_projeto
    AND det.area_interesse_id = :id_area_interesse
WHERE ind.ativo = true
  AND det.id IS NULL
ORDER BY ind.prioridade NULLS LAST, ind.nome_logico;
-- 8. Setores intersectados sem valor socioeconomico estimado por indicador
SELECT
    det.execucao_id,
    det.indicador_id,
    det.nome_logico_indicador,
    count(*) AS setores_sem_valor
FROM resultados.indicador_socioeconomico_detalhe AS det
WHERE det.execucao_id = :id_processamento
  AND det.projeto_id = :id_projeto
  AND det.area_interesse_id = :id_area_interesse
  AND det.valor_original IS NULL
GROUP BY
    det.execucao_id,
    det.indicador_id,
    det.nome_logico_indicador
ORDER BY det.nome_logico_indicador;

-- 9. Conferencia das chaves setoriais cadastradas para tabelas socioeconomicas
SELECT
    ind.id AS indicador_id,
    ind.nome_logico,
    ind.tabela_dados,
    ind.campo_codigo_setor,
    ind.campo_valor
FROM config.indicadores_mvp AS ind
WHERE ind.tabela_dados IN (
    'agregados_por_setores_caracteristicas_domicilio1_br',
    'agregados_por_setores_caracteristicas_domicilio2_br',
    'agregados_por_setores_caracteristicas_domicilio3_br',
    'agregados_por_setores_renda_responsavel_br'
)
ORDER BY ind.tabela_dados, ind.nome_logico;

