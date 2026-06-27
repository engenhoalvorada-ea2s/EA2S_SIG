/*
EA2S SIG - 01_schema_mvp.sql

Script conservador de preparacao minima para o banco real `ea2s_sig`.
Nao cria estrutura paralela e nao recria objetos operacionais ja existentes.

Objetos reais confirmados e preservados:
- projetos.projeto
- projetos.area_interesse
- resultados.execucao
- logs.processamento
- resultados.setores_intersectados
- resultados.indicador_socioeconomico_detalhe
- resultados.indicador_socioeconomico_resumo
- config.indicadores_mvp
- metadados.dicionario_indicadores

Nao alterar schemas oficiais: urbano, geologia, geomorfologia, pedologia,
vegetacao, hidrografia, hidrogeologia e topografia.
Revisar no DBeaver antes de qualquer execucao.
*/

CREATE SCHEMA IF NOT EXISTS projetos;
CREATE SCHEMA IF NOT EXISTS config;
CREATE SCHEMA IF NOT EXISTS metadados;
CREATE SCHEMA IF NOT EXISTS resultados;
CREATE SCHEMA IF NOT EXISTS logs;

-- Funcoes auxiliares usadas pelos scripts do MVP.
-- Mantidas sem criar tabelas novas nem alterar dados oficiais.
CREATE OR REPLACE FUNCTION public.ea2s_normalizar_codigo_setor(p_codigo text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT NULLIF(regexp_replace(coalesce(p_codigo, ''), '[^0-9]', '', 'g'), '');
$$;

CREATE OR REPLACE FUNCTION public.ea2s_safe_numeric(p_valor text)
RETURNS numeric
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    v_limpo text;
BEGIN
    v_limpo := NULLIF(trim(replace(coalesce(p_valor, ''), ',', '.')), '');

    IF v_limpo IS NULL THEN
        RETURN NULL;
    END IF;

    RETURN v_limpo::numeric;
EXCEPTION
    WHEN invalid_text_representation OR numeric_value_out_of_range THEN
        RETURN NULL;
END;
$$;

/*
Estrutura real usada pelos scripts seguintes:

projetos.projeto(id, codigo, nome, cliente, municipio, uf, atividade,
tipo_estudo, descricao, status, responsavel, data_cadastro, data_atualizacao)

projetos.area_interesse(id, projeto_id, nome, tipo, fonte, observacao,
srid_origem, area_m2, area_ha, geom, data_cadastro, data_atualizacao)

resultados.execucao(id, projeto_id, nome, tipo_execucao, status, parametros,
mensagem, iniciado_em, finalizado_em, usuario)

logs.processamento(id, execucao_id, projeto_id, nivel, etapa, mensagem,
detalhe, criado_em)

resultados.setores_intersectados(id, execucao_id, projeto_id, area_interesse_id,
cd_setor, area_intersecao_m2, area_intersecao_ha, area_setor_total_m2,
percentual_setor_intersectado, percentual_area_interesse, geom, data_cadastro)

resultados.indicador_socioeconomico_detalhe(id, execucao_id, projeto_id,
area_interesse_id, indicador_id, cd_setor, nome_logico_indicador, tema,
subtema, tabela_origem, campo_origem, valor_original,
percentual_setor_intersectado, valor_estimado, metodo_estimativa, observacao,
data_cadastro)

resultados.indicador_socioeconomico_resumo(id, execucao_id, projeto_id,
area_interesse_id, indicador_id, nome_logico_indicador, tema, subtema,
descricao, unidade, valor_estimado_total, valor_medio_ponderado,
numero_setores, area_total_intersectada_m2, metodo_estimativa, observacao,
data_cadastro)

config.indicadores_mvp(id, nome_logico, tema, subtema, descricao,
schema_tabela_dados, tabela_dados, campo_codigo_setor, campo_valor, unidade,
tipo_indicador, metodo_estimativa, ativo, prioridade, observacao,
data_cadastro, data_atualizacao)

metadados.dicionario_indicadores(id, fonte, tema, subtema, tabela_banco, campo,
descricao_oficial, unidade, tipo_dado, tipo_calculo, metodo_estimativa,
usar_no_mvp, prioridade, observacao, data_cadastro, data_atualizacao)
*/
