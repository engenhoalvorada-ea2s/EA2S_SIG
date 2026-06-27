/*
EA2S SIG - 06_indicadores_derivados.sql

Matriz conceitual de indicadores derivados futuros.
Esta etapa nao implementa calculos ainda.

Os indicadores abaixo dependem da consolidacao dos resultados socioeconomicos,
da area da area de interesse e, em alguns casos, das intersecoes fisico-bioticas.
*/

-- ============================================================================
-- 1. Matriz conceitual de indicadores derivados futuros
-- ============================================================================

-- DENSIDADE POPULACIONAL
-- Codigo sugerido: DENS_POP
-- Formula futura: POP_TOTAL / area_interesse_ha
-- Unidade: habitantes por hectare
-- Dependencias: resultados.indicador_socioeconomico_resumo, projetos.area_interesse
-- Status: futuro

-- DENSIDADE DOMICILIAR
-- Codigo sugerido: DENS_DOM
-- Formula futura: DOM_TOTAL / area_interesse_ha
-- Unidade: domicilios por hectare
-- Dependencias: resultados.indicador_socioeconomico_resumo, projetos.area_interesse
-- Status: futuro

-- PERCENTUAL DE AGUA POR REDE GERAL
-- Codigo sugerido: PCT_AGUA_REDE_GERAL
-- Formula futura: AGUA_REDE_GERAL / DOM_TOTAL * 100
-- Unidade: percentual
-- Dependencias: AGUA_REDE_GERAL, DOM_TOTAL
-- Status: futuro

-- PERCENTUAL DE COLETA DE LIXO
-- Codigo sugerido: PCT_LIXO_COLETA
-- Formula futura: LIXO_COLETA / DOM_TOTAL * 100
-- Unidade: percentual
-- Dependencias: LIXO_COLETA, DOM_TOTAL
-- Status: futuro

-- PERCENTUAL DE ESGOTAMENTO SANITARIO ADEQUADO
-- Codigo sugerido: PCT_ESGOTO_ADEQUADO
-- Formula futura: ESGOTO_ADEQUADO / DOM_TOTAL * 100
-- Unidade: percentual
-- Dependencias: ESGOTO_ADEQUADO, DOM_TOTAL
-- Status: futuro

-- PERCENTUAL DE SOLUCOES SANITARIAS PRECARIAS
-- Codigo sugerido: PCT_ESGOTO_PRECARIO
-- Formula futura: ESGOTO_PRECARIO / DOM_TOTAL * 100
-- Unidade: percentual
-- Dependencias: indicador de esgoto precario ainda nao consolidado, DOM_TOTAL
-- Status: futuro

-- INDICADORES DE VULNERABILIDADE SOCIOAMBIENTAL
-- Codigo sugerido: VULN_SOCIOAMB
-- Formula futura: metodologia composta a definir pela EA2S
-- Unidade: indice ou classe ordinal
-- Dependencias: indicadores socioeconomicos, intersecoes fisico-bioticas,
-- criterios de exposicao ambiental e pesos tecnicos validados
-- Status: futuro

-- ============================================================================
-- 2. Pendencias antes de implementar
-- ============================================================================

-- TODO: Definir denominadores oficiais e tratamento de divisao por zero.
-- TODO: Definir se percentuais serao gravados em nova tabela ou em
-- resultados.indicador_socioeconomico_resumo.
-- TODO: Definir limites, classes e pesos dos indicadores de vulnerabilidade.
-- TODO: Validar quais indicadores podem ser apresentados como estimativas
-- derivadas e quais devem aparecer apenas como referencia metodologica.
