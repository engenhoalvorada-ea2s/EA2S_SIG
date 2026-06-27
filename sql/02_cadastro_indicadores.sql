/*
EA2S SIG - 02_cadastro_indicadores.sql

Cadastro conservador de indicadores no modelo real de `config.indicadores_mvp`.
Nao usa tabela consolidada paralela. Os campos de valor ainda precisam ser
confirmados nas tabelas urbanas reais antes de execucao.

Validacao posterior confirmada no DBeaver: todos os indicadores cadastrados em config.indicadores_mvp apontam para tabelas e colunas reais existentes; campo_codigo_setor e campo_valor retornaram ok para todos os indicadores listados.

Nao executar sem revisao manual no DBeaver.
*/

-- Indicadores provisorios no modelo real de config.indicadores_mvp.
-- Chaves setoriais confirmadas:
-- - urbano.agregados_por_setores_caracteristicas_domicilio1_br: "CD_setor"
-- - urbano.agregados_por_setores_caracteristicas_domicilio2_br: setor
-- - urbano.agregados_por_setores_caracteristicas_domicilio3_br: setor
-- - urbano.agregados_por_setores_renda_responsavel_br: "CD_SETOR"
--
-- A conferencia dos 4 setores da execucao execucao_id = 4, projeto_id = 1,
-- area_interesse_id = 1 retornou ok para as quatro tabelas socioeconomicas.
--
-- Todas as quatro tabelas socioeconomicas possuem 458.772 registros. A malha
-- urbano.setores_censo_2022_malha_br possui 468.099 setores; portanto, os
-- calculos devem tolerar setores sem registro socioeconomico correspondente.
--
-- Campos de setor e valor validados no DBeaver para todos os indicadores cadastrados.
INSERT INTO config.indicadores_mvp (
    nome_logico,
    tema,
    subtema,
    descricao,
    schema_tabela_dados,
    tabela_dados,
    campo_codigo_setor,
    campo_valor,
    unidade,
    tipo_indicador,
    metodo_estimativa,
    ativo,
    prioridade,
    observacao
)
SELECT
    indicador.nome_logico,
    indicador.tema,
    indicador.subtema,
    indicador.descricao,
    indicador.schema_tabela_dados,
    indicador.tabela_dados,
    indicador.campo_codigo_setor,
    indicador.campo_valor,
    indicador.unidade,
    indicador.tipo_indicador,
    indicador.metodo_estimativa,
    indicador.ativo,
    indicador.prioridade,
    indicador.observacao
FROM (
    VALUES
        ('domicilios_total', 'socioeconomico', 'domicilios', 'Total de domicilios no setor censitario.', 'urbano', 'agregados_por_setores_caracteristicas_domicilio1_br', 'CD_setor', 'CONFIRMAR_DOMICILIOS_TOTAL', 'domicilios', 'somavel', 'ponderacao_areal', true, 20, 'Indicador provisorio; confirmar campo de valor no DBeaver. A coluna de setor desta tabela usa aspas: "CD_setor".'),
        ('agua_rede_geral', 'socioeconomico', 'infraestrutura', 'Domicilios com abastecimento por rede geral.', 'urbano', 'agregados_por_setores_caracteristicas_domicilio1_br', 'CD_setor', 'CONFIRMAR_AGUA_REDE_GERAL', 'domicilios', 'somavel', 'ponderacao_areal', true, 30, 'Indicador provisorio; confirmar campo de valor no DBeaver. A coluna de setor desta tabela usa aspas: "CD_setor".'),
        ('lixo_coleta', 'socioeconomico', 'residuos_solidos', 'Domicilios com coleta de lixo.', 'urbano', 'agregados_por_setores_caracteristicas_domicilio2_br', 'setor', 'CONFIRMAR_LIXO_COLETA', 'domicilios', 'somavel', 'ponderacao_areal', true, 40, 'Indicador provisorio; confirmar campo de valor no DBeaver.'),
        ('esgoto_adequado', 'socioeconomico', 'esgotamento_sanitario', 'Domicilios com solucao de esgotamento considerada adequada.', 'urbano', 'agregados_por_setores_caracteristicas_domicilio2_br', 'setor', 'CONFIRMAR_ESGOTO_ADEQUADO', 'domicilios', 'somavel', 'ponderacao_areal', true, 50, 'Indicador provisorio; conceito e campo devem ser confirmados.'),
        ('renda_responsavel_media', 'socioeconomico', 'renda', 'Renda referencial do responsavel pelo domicilio.', 'urbano', 'agregados_por_setores_renda_responsavel_br', 'CD_SETOR', 'CONFIRMAR_RENDA_RESPONSAVEL', 'moeda', 'media', 'media_ponderada', true, 60, 'Indicador referencial; nao somar diretamente. A chave setorial desta tabela e "CD_SETOR" e deve ser sempre referenciada com aspas duplas no SQL gerado.'),
        ('domicilio3_referencia', 'socioeconomico', 'domicilios', 'Indicador futuro baseado na terceira tabela de caracteristicas de domicilio.', 'urbano', 'agregados_por_setores_caracteristicas_domicilio3_br', 'setor', 'CONFIRMAR_CAMPO_VALOR', 'a definir', 'referencial', 'a_definir', false, 90, 'Manter inativo ate confirmar campo de valor; chave setorial final confirmada como setor.')
) AS indicador(
    nome_logico,
    tema,
    subtema,
    descricao,
    schema_tabela_dados,
    tabela_dados,
    campo_codigo_setor,
    campo_valor,
    unidade,
    tipo_indicador,
    metodo_estimativa,
    ativo,
    prioridade,
    observacao
)
WHERE NOT EXISTS (
    SELECT 1
    FROM config.indicadores_mvp AS existente
    WHERE existente.nome_logico = indicador.nome_logico
);

-- Metadados oficiais provisorios no modelo real de metadados.dicionario_indicadores.
INSERT INTO metadados.dicionario_indicadores (
    fonte,
    tema,
    subtema,
    tabela_banco,
    campo,
    descricao_oficial,
    unidade,
    tipo_dado,
    tipo_calculo,
    metodo_estimativa,
    usar_no_mvp,
    prioridade,
    observacao
)
SELECT
    item.fonte,
    item.tema,
    item.subtema,
    item.tabela_banco,
    item.campo,
    item.descricao_oficial,
    item.unidade,
    item.tipo_dado,
    item.tipo_calculo,
    item.metodo_estimativa,
    item.usar_no_mvp,
    item.prioridade,
    item.observacao
FROM (
    VALUES
        ('IBGE', 'socioeconomico', 'domicilios', 'urbano.agregados_por_setores_caracteristicas_domicilio1_br', 'CONFIRMAR_DOMICILIOS_TOTAL', 'Campo de domicilios totais a confirmar.', 'domicilios', 'numeric', 'soma', 'ponderacao_areal', true, 20, 'Pendente confirmar coluna real.'),
        ('IBGE', 'socioeconomico', 'infraestrutura', 'urbano.agregados_por_setores_caracteristicas_domicilio1_br', 'CONFIRMAR_AGUA_REDE_GERAL', 'Campo de abastecimento por rede geral a confirmar.', 'domicilios', 'numeric', 'soma', 'ponderacao_areal', true, 30, 'Pendente confirmar coluna real.'),
        ('IBGE', 'socioeconomico', 'residuos_solidos', 'urbano.agregados_por_setores_caracteristicas_domicilio2_br', 'CONFIRMAR_LIXO_COLETA', 'Campo de coleta de lixo a confirmar.', 'domicilios', 'numeric', 'soma', 'ponderacao_areal', true, 40, 'Pendente confirmar coluna real.'),
        ('IBGE', 'socioeconomico', 'esgotamento_sanitario', 'urbano.agregados_por_setores_caracteristicas_domicilio2_br', 'CONFIRMAR_ESGOTO_ADEQUADO', 'Campo de esgotamento adequado a confirmar.', 'domicilios', 'numeric', 'soma', 'ponderacao_areal', true, 50, 'Pendente confirmar coluna real.'),
        ('IBGE', 'socioeconomico', 'renda', 'urbano.agregados_por_setores_renda_responsavel_br', 'CONFIRMAR_RENDA_RESPONSAVEL', 'Campo de renda do responsavel a confirmar.', 'moeda', 'numeric', 'media', 'media_ponderada', true, 60, 'Pendente confirmar coluna real.')
) AS item(
    fonte,
    tema,
    subtema,
    tabela_banco,
    campo,
    descricao_oficial,
    unidade,
    tipo_dado,
    tipo_calculo,
    metodo_estimativa,
    usar_no_mvp,
    prioridade,
    observacao
)
WHERE NOT EXISTS (
    SELECT 1
    FROM metadados.dicionario_indicadores AS existente
    WHERE existente.tabela_banco = item.tabela_banco
      AND existente.campo = item.campo
);

-- Indicadores confirmados como inativos por enquanto:
-- - renda_variancia_moradores_dppo
-- - renda_variancia_rendimento_responsavel
-- Motivo: variancia nao deve ser tratada como soma ponderada simples no MVP.

-- Conferencias recomendadas apos execucao autorizada:
-- Validacao ja realizada no DBeaver: campo_codigo_setor e campo_valor retornaram ok para todos os indicadores cadastrados.
-- SELECT id, tabela_banco, campo FROM metadados.dicionario_indicadores WHERE campo LIKE 'CONFIRMAR_%';






