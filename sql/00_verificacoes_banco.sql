/*
EA2S SIG - 00_verificacoes_banco.sql

Consultas seguras de leitura para conferencia inicial do banco.
Nao altera dados, schemas, tabelas ou funcoes.
*/

-- 1. Banco, usuario e porta atuais
SELECT
    current_database() AS banco_atual,
    current_user AS usuario_atual,
    inet_server_port() AS porta;

-- 2. Extensao PostGIS
SELECT
    'postgis' AS extensao_esperada,
    pg_extension.extname AS extensao_encontrada,
    pg_extension.extversion AS versao,
    CASE
        WHEN pg_extension.extname IS NULL THEN 'nao encontrada'
        ELSE 'encontrada'
    END AS status
FROM (VALUES ('postgis')) AS esperado(extname)
LEFT JOIN pg_extension
    ON pg_extension.extname = esperado.extname;

-- 3. Schemas esperados
SELECT
    esperado.schema_name,
    CASE
        WHEN pg_namespace.nspname IS NULL THEN 'nao encontrado'
        ELSE 'encontrado'
    END AS status
FROM (
    VALUES
        ('projetos'),
        ('config'),
        ('metadados'),
        ('resultados'),
        ('logs'),
        ('urbano'),
        ('social'),
        ('geologia'),
        ('geomorfologia'),
        ('pedologia'),
        ('vegetacao'),
        ('hidrografia'),
        ('topografia'),
        ('hidrogeologia')
) AS esperado(schema_name)
LEFT JOIN pg_namespace
    ON pg_namespace.nspname = esperado.schema_name
ORDER BY esperado.schema_name;

-- 4. Tabelas operacionais esperadas
SELECT
    esperado.schema_name,
    esperado.object_name,
    CASE
        WHEN information_schema.tables.table_name IS NULL THEN 'nao encontrada'
        ELSE 'encontrada'
    END AS status
FROM (
    VALUES
        ('logs', 'processamento'),
        ('metadados', 'dicionario_indicadores'),
        ('config', 'indicadores_mvp'),
        ('resultados', 'setores_intersectados'),
        ('resultados', 'indicador_socioeconomico_detalhe'),
        ('resultados', 'indicador_socioeconomico_resumo'),
        ('resultados', 'produto_gerado')
) AS esperado(schema_name, object_name)
LEFT JOIN information_schema.tables
    ON information_schema.tables.table_schema = esperado.schema_name
    AND information_schema.tables.table_name = esperado.object_name
ORDER BY esperado.schema_name, esperado.object_name;

-- 5. Funcoes esperadas com assinatura exata
SELECT
    esperado.schema_name,
    esperado.function_name,
    esperado.argumentos AS assinatura_esperada,
    CASE
        WHEN pg_proc.oid IS NULL THEN 'nao encontrada'
        ELSE 'encontrada'
    END AS status
FROM (
    VALUES
        ('public', 'ea2s_normalizar_codigo_setor', 'text'),
        ('public', 'ea2s_safe_numeric', 'text'),
        ('resultados', 'processar_setores_intersectados', 'bigint, bigint, bigint'),
        ('resultados', 'calcular_indicadores_socioeconomicos_mvp', 'bigint, bigint, bigint')
) AS esperado(schema_name, function_name, argumentos)
LEFT JOIN pg_namespace
    ON pg_namespace.nspname = esperado.schema_name
LEFT JOIN pg_proc
    ON pg_proc.pronamespace = pg_namespace.oid
    AND pg_proc.proname = esperado.function_name
    AND pg_get_function_identity_arguments(pg_proc.oid) = esperado.argumentos
ORDER BY esperado.schema_name, esperado.function_name;

-- 6. Funcoes existentes nos schemas operacionais
SELECT
    pg_namespace.nspname AS schema_name,
    pg_proc.proname AS function_name,
    pg_get_function_identity_arguments(pg_proc.oid) AS argumentos
FROM pg_proc
INNER JOIN pg_namespace
    ON pg_namespace.oid = pg_proc.pronamespace
WHERE pg_namespace.nspname IN ('public', 'resultados')
  AND pg_proc.proname IN (
      'ea2s_normalizar_codigo_setor',
      'ea2s_safe_numeric',
      'processar_setores_intersectados',
      'calcular_indicadores_socioeconomicos_mvp'
  )
ORDER BY schema_name, function_name, argumentos;
