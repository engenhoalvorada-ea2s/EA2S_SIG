-- ============================================================================
-- EA2S SIG - Configuracao de camadas de analise
-- ============================================================================
-- Proposta local para cadastro de camadas oficiais/analiticas disponiveis para
-- diagnostico. Este script cria apenas objetos no schema config.
--
-- Nao importa arquivos espaciais.
-- Nao altera schemas oficiais de dados.
-- Nao altera tabelas de resultados.
-- Nao usa DROP TABLE.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS config;

-- ============================================================================
-- 1. Tabela de camadas de analise
-- ============================================================================

CREATE TABLE IF NOT EXISTS config.camadas_analise (
    id bigserial PRIMARY KEY,
    nome_logico text UNIQUE NOT NULL,
    titulo text NOT NULL,
    grupo text NOT NULL,
    tema text NOT NULL,
    subtema text,
    descricao text,
    schema_name text NOT NULL,
    table_name text NOT NULL,
    geom_column text DEFAULT 'geom',
    pk_column text,
    tipo_geometria text,
    srid integer,
    fonte text,
    orgao_produtor text,
    ano_referencia integer,
    data_referencia date,
    versao_fonte text,
    url_origem text,
    citacao_fonte text,
    campo_valor_principal text,
    campos_descritivos jsonb DEFAULT '[]'::jsonb,
    campos_codigo jsonb DEFAULT '[]'::jsonb,
    campos_ignorar jsonb DEFAULT '[]'::jsonb,
    metrica_padrao text,
    tipo_processamento text,
    usar_area_interesse boolean DEFAULT true,
    usar_buffer boolean DEFAULT true,
    usar_microbacia boolean DEFAULT false,
    usar_setor boolean DEFAULT false,
    usar_municipio boolean DEFAULT false,
    disponivel_dashboard boolean DEFAULT true,
    disponivel_gpkg boolean DEFAULT true,
    disponivel_relatorio boolean DEFAULT true,
    ativo boolean DEFAULT true,
    ordem_exibicao integer DEFAULT 100,
    observacao text,
    criado_em timestamp DEFAULT now(),
    atualizado_em timestamp DEFAULT now()
);

ALTER TABLE config.camadas_analise
    ADD COLUMN IF NOT EXISTS nome_logico text,
    ADD COLUMN IF NOT EXISTS titulo text,
    ADD COLUMN IF NOT EXISTS grupo text,
    ADD COLUMN IF NOT EXISTS tema text,
    ADD COLUMN IF NOT EXISTS subtema text,
    ADD COLUMN IF NOT EXISTS descricao text,
    ADD COLUMN IF NOT EXISTS schema_name text,
    ADD COLUMN IF NOT EXISTS table_name text,
    ADD COLUMN IF NOT EXISTS geom_column text DEFAULT 'geom',
    ADD COLUMN IF NOT EXISTS pk_column text,
    ADD COLUMN IF NOT EXISTS tipo_geometria text,
    ADD COLUMN IF NOT EXISTS srid integer,
    ADD COLUMN IF NOT EXISTS fonte text,
    ADD COLUMN IF NOT EXISTS orgao_produtor text,
    ADD COLUMN IF NOT EXISTS ano_referencia integer,
    ADD COLUMN IF NOT EXISTS data_referencia date,
    ADD COLUMN IF NOT EXISTS versao_fonte text,
    ADD COLUMN IF NOT EXISTS url_origem text,
    ADD COLUMN IF NOT EXISTS citacao_fonte text,
    ADD COLUMN IF NOT EXISTS campo_valor_principal text,
    ADD COLUMN IF NOT EXISTS campos_descritivos jsonb DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS campos_codigo jsonb DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS campos_ignorar jsonb DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS metrica_padrao text,
    ADD COLUMN IF NOT EXISTS tipo_processamento text,
    ADD COLUMN IF NOT EXISTS usar_area_interesse boolean DEFAULT true,
    ADD COLUMN IF NOT EXISTS usar_buffer boolean DEFAULT true,
    ADD COLUMN IF NOT EXISTS usar_microbacia boolean DEFAULT false,
    ADD COLUMN IF NOT EXISTS usar_setor boolean DEFAULT false,
    ADD COLUMN IF NOT EXISTS usar_municipio boolean DEFAULT false,
    ADD COLUMN IF NOT EXISTS disponivel_dashboard boolean DEFAULT true,
    ADD COLUMN IF NOT EXISTS disponivel_gpkg boolean DEFAULT true,
    ADD COLUMN IF NOT EXISTS disponivel_relatorio boolean DEFAULT true,
    ADD COLUMN IF NOT EXISTS ativo boolean DEFAULT true,
    ADD COLUMN IF NOT EXISTS ordem_exibicao integer DEFAULT 100,
    ADD COLUMN IF NOT EXISTS observacao text,
    ADD COLUMN IF NOT EXISTS criado_em timestamp DEFAULT now(),
    ADD COLUMN IF NOT EXISTS atualizado_em timestamp DEFAULT now();

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'camadas_analise_nome_logico_uk'
    ) THEN
        ALTER TABLE config.camadas_analise
            ADD CONSTRAINT camadas_analise_nome_logico_uk UNIQUE (nome_logico);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'camadas_analise_metrica_chk'
    ) THEN
        ALTER TABLE config.camadas_analise
            ADD CONSTRAINT camadas_analise_metrica_chk CHECK (
                metrica_padrao IS NULL OR metrica_padrao IN (
                    'area', 'comprimento', 'contagem', 'proximidade', 'atributo'
                )
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'camadas_analise_tipo_processamento_chk'
    ) THEN
        ALTER TABLE config.camadas_analise
            ADD CONSTRAINT camadas_analise_tipo_processamento_chk CHECK (
                tipo_processamento IS NULL OR tipo_processamento IN (
                    'poligono_area', 'linha_comprimento', 'ponto_contagem',
                    'atributo', 'raster', 'outro'
                )
            );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_camadas_analise_nome_logico
    ON config.camadas_analise(nome_logico);

CREATE INDEX IF NOT EXISTS idx_camadas_analise_grupo
    ON config.camadas_analise(grupo);

CREATE INDEX IF NOT EXISTS idx_camadas_analise_tema
    ON config.camadas_analise(tema);

CREATE INDEX IF NOT EXISTS idx_camadas_analise_ativo
    ON config.camadas_analise(ativo);

CREATE INDEX IF NOT EXISTS idx_camadas_analise_schema_table
    ON config.camadas_analise(schema_name, table_name);

-- ============================================================================
-- 2. Perfis de diagnostico
-- ============================================================================

CREATE TABLE IF NOT EXISTS config.perfis_diagnostico (
    id bigserial PRIMARY KEY,
    nome_logico text UNIQUE NOT NULL,
    titulo text NOT NULL,
    descricao text,
    ativo boolean DEFAULT true,
    ordem_exibicao integer DEFAULT 100,
    criado_em timestamp DEFAULT now(),
    atualizado_em timestamp DEFAULT now()
);

ALTER TABLE config.perfis_diagnostico
    ADD COLUMN IF NOT EXISTS nome_logico text,
    ADD COLUMN IF NOT EXISTS titulo text,
    ADD COLUMN IF NOT EXISTS descricao text,
    ADD COLUMN IF NOT EXISTS ativo boolean DEFAULT true,
    ADD COLUMN IF NOT EXISTS ordem_exibicao integer DEFAULT 100,
    ADD COLUMN IF NOT EXISTS criado_em timestamp DEFAULT now(),
    ADD COLUMN IF NOT EXISTS atualizado_em timestamp DEFAULT now();

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'perfis_diagnostico_nome_logico_uk'
    ) THEN
        ALTER TABLE config.perfis_diagnostico
            ADD CONSTRAINT perfis_diagnostico_nome_logico_uk UNIQUE (nome_logico);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS config.perfil_camadas_analise (
    id bigserial PRIMARY KEY,
    perfil_id bigint NOT NULL,
    camada_id bigint NOT NULL,
    obrigatoria boolean DEFAULT false,
    ordem_exibicao integer DEFAULT 100,
    ativo boolean DEFAULT true
);

ALTER TABLE config.perfil_camadas_analise
    ADD COLUMN IF NOT EXISTS perfil_id bigint,
    ADD COLUMN IF NOT EXISTS camada_id bigint,
    ADD COLUMN IF NOT EXISTS obrigatoria boolean DEFAULT false,
    ADD COLUMN IF NOT EXISTS ordem_exibicao integer DEFAULT 100,
    ADD COLUMN IF NOT EXISTS ativo boolean DEFAULT true;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'perfil_camadas_analise_perfil_fk'
    ) THEN
        ALTER TABLE config.perfil_camadas_analise
            ADD CONSTRAINT perfil_camadas_analise_perfil_fk
            FOREIGN KEY (perfil_id) REFERENCES config.perfis_diagnostico(id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'perfil_camadas_analise_camada_fk'
    ) THEN
        ALTER TABLE config.perfil_camadas_analise
            ADD CONSTRAINT perfil_camadas_analise_camada_fk
            FOREIGN KEY (camada_id) REFERENCES config.camadas_analise(id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'perfil_camadas_analise_perfil_camada_uk'
    ) THEN
        ALTER TABLE config.perfil_camadas_analise
            ADD CONSTRAINT perfil_camadas_analise_perfil_camada_uk
            UNIQUE (perfil_id, camada_id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_perfil_camadas_analise_perfil
    ON config.perfil_camadas_analise(perfil_id);

CREATE INDEX IF NOT EXISTS idx_perfil_camadas_analise_camada
    ON config.perfil_camadas_analise(camada_id);

-- ============================================================================
-- 3. Cadastro inicial de camadas ja usadas no MVP
-- ============================================================================

INSERT INTO config.camadas_analise (
    nome_logico, titulo, grupo, tema, subtema, descricao,
    schema_name, table_name, geom_column, pk_column, tipo_geometria, srid,
    fonte, orgao_produtor, ano_referencia, versao_fonte,
    campo_valor_principal, campos_descritivos, campos_codigo, campos_ignorar,
    metrica_padrao, tipo_processamento,
    usar_area_interesse, usar_buffer, usar_microbacia, usar_setor, usar_municipio,
    disponivel_dashboard, disponivel_gpkg, disponivel_relatorio, ativo,
    ordem_exibicao, observacao, atualizado_em
)
VALUES
(
    'geologia', 'Geologia', 'meio_fisico', 'geologia', NULL,
    'Unidades geologicas da base BDIA usadas nas intersecoes fisico-bioticas do MVP.',
    'geologia', 'geologia_br_bdia_2025', 'geom', 'id', 'MULTIPOLYGON', 4674,
    'BDIA', 'IBGE', 2025, '2025',
    'nm_unidade',
    '["letra_simb", "nm_lito1", "nm_lito2", "nm_lito3", "nm_lito4", "nm_tempo_g", "nm_provinc", "nm_sub_pro"]'::jsonb,
    '["id", "letra_simb"]'::jsonb,
    '["geom", "geometry"]'::jsonb,
    'area', 'poligono_area',
    true, true, true, false, false,
    true, true, true, true,
    10, 'Cadastro inicial alinhado ao sql/05_intersecoes_fisico_biotico.sql.', now()
),
(
    'geomorfologia', 'Geomorfologia', 'meio_fisico', 'geomorfologia', NULL,
    'Unidades geomorfologicas da base BDIA usadas nas intersecoes fisico-bioticas do MVP.',
    'geomorfologia', 'geomorfo_br_bdia_2025', 'geom', 'id', 'MULTIPOLYGON', 4674,
    'BDIA', 'IBGE', 2025, '2025',
    'legenda',
    '["nm_dominio", "nm_regiao", "nm_unidade", "categoria", "natureza", "forma", "dens_dren", "aprof_inci", "niv_alt", "compartime"]'::jsonb,
    '["id"]'::jsonb,
    '["geom", "geometry"]'::jsonb,
    'area', 'poligono_area',
    true, true, true, false, false,
    true, true, true, true,
    20, 'Cadastro inicial alinhado ao sql/05_intersecoes_fisico_biotico.sql.', now()
),
(
    'hidrogeologia', 'Hidrogeologia', 'meio_fisico', 'hidrogeologia', NULL,
    'Unidades hidrogeologicas da base BDIA usadas nas intersecoes fisico-bioticas do MVP.',
    'hidrogeologia', 'hidrogeologico_sul_bdia_2025', 'geom', 'id', 'MULTIPOLYGON', 4674,
    'BDIA', 'IBGE', 2025, '2025',
    'nome_unida',
    '["cd_legenda", "litologia", "provincia", "dominio", "vz_cl", "vze_cl", "vz_int_cl", "vze_int_cl", "domínio_da"]'::jsonb,
    '["id", "cd_legenda"]'::jsonb,
    '["geom", "geometry"]'::jsonb,
    'area', 'poligono_area',
    true, true, true, false, false,
    true, true, true, true,
    30, 'Cadastro inicial alinhado ao sql/05_intersecoes_fisico_biotico.sql.', now()
),
(
    'pedologia', 'Pedologia', 'meio_fisico', 'pedologia', NULL,
    'Ordem de solos usada nas intersecoes fisico-bioticas do MVP.',
    'pedologia', 'pedo_ordem_ibge_br', 'geom', 'id', 'MULTIPOLYGON', 4674,
    'IBGE', 'IBGE', NULL, NULL,
    'legenda',
    '["area_km"]'::jsonb,
    '["id"]'::jsonb,
    '["geom", "geometry"]'::jsonb,
    'area', 'poligono_area',
    true, true, true, false, false,
    true, true, true, true,
    40, 'Cadastro inicial alinhado ao sql/05_intersecoes_fisico_biotico.sql.', now()
),
(
    'vegetacao', 'Vegetacao', 'meio_biotico', 'vegetacao', NULL,
    'Vegetacao da base BDIA usada nas intersecoes fisico-bioticas do MVP.',
    'vegetacao', 'vegetacao_br_bdia_2025', 'geom', 'id', 'MULTIPOLYGON', 4674,
    'BDIA', 'IBGE', 2025, '2025',
    'legenda',
    '["cd_fito", "cd_leg_2", "clas_domi", "nm_uveg", "nm_uantr", "nm_contat", "nm_pretet", "legenda_1", "legenda_2"]'::jsonb,
    '["id", "cd_fito", "cd_leg_2"]'::jsonb,
    '["geom", "geometry"]'::jsonb,
    'area', 'poligono_area',
    true, true, true, false, false,
    true, true, true, true,
    50, 'Cadastro inicial alinhado ao sql/05_intersecoes_fisico_biotico.sql.', now()
),
(
    'hidrografia_ana', 'Hidrografia ANA', 'meio_fisico', 'hidrografia', NULL,
    'Cursos d''agua da ANA tratados no MVP como camada linear separada das intersecoes fisico-bioticas poligonais.',
    'hidrografia', 'bh6_curso_dagua_ANA_2022', 'geom', 'id', 'MULTILINESTRING', 4674,
    'ANA', 'ANA', 2022, '2022',
    'cocursodag',
    '["idcda", "cocursodag", "cocdadesag", "nunivotcda", "nuordemcda", "dedominial", "dsversao"]'::jsonb,
    '["idcda", "cocursodag", "cocdadesag"]'::jsonb,
    '["geom", "geometry"]'::jsonb,
    'comprimento', 'linha_comprimento',
    true, true, true, false, false,
    true, true, true, true,
    60, 'Nome real da tabela no SQL deve usar aspas duplas: hidrografia."bh6_curso_dagua_ANA_2022".', now()
)
ON CONFLICT (nome_logico) DO UPDATE SET
    titulo = EXCLUDED.titulo,
    grupo = EXCLUDED.grupo,
    tema = EXCLUDED.tema,
    subtema = EXCLUDED.subtema,
    descricao = EXCLUDED.descricao,
    schema_name = EXCLUDED.schema_name,
    table_name = EXCLUDED.table_name,
    geom_column = EXCLUDED.geom_column,
    pk_column = EXCLUDED.pk_column,
    tipo_geometria = EXCLUDED.tipo_geometria,
    srid = EXCLUDED.srid,
    fonte = EXCLUDED.fonte,
    orgao_produtor = EXCLUDED.orgao_produtor,
    ano_referencia = EXCLUDED.ano_referencia,
    versao_fonte = EXCLUDED.versao_fonte,
    campo_valor_principal = EXCLUDED.campo_valor_principal,
    campos_descritivos = EXCLUDED.campos_descritivos,
    campos_codigo = EXCLUDED.campos_codigo,
    campos_ignorar = EXCLUDED.campos_ignorar,
    metrica_padrao = EXCLUDED.metrica_padrao,
    tipo_processamento = EXCLUDED.tipo_processamento,
    usar_area_interesse = EXCLUDED.usar_area_interesse,
    usar_buffer = EXCLUDED.usar_buffer,
    usar_microbacia = EXCLUDED.usar_microbacia,
    usar_setor = EXCLUDED.usar_setor,
    usar_municipio = EXCLUDED.usar_municipio,
    disponivel_dashboard = EXCLUDED.disponivel_dashboard,
    disponivel_gpkg = EXCLUDED.disponivel_gpkg,
    disponivel_relatorio = EXCLUDED.disponivel_relatorio,
    ativo = EXCLUDED.ativo,
    ordem_exibicao = EXCLUDED.ordem_exibicao,
    observacao = EXCLUDED.observacao,
    atualizado_em = now();

INSERT INTO config.perfis_diagnostico (
    nome_logico,
    titulo,
    descricao,
    ativo,
    ordem_exibicao,
    atualizado_em
)
VALUES (
    'diagnostico_ambiental_basico',
    'Diagnóstico ambiental básico',
    'Perfil inicial com as camadas fisico-bioticas e hidrografia ANA ja implementadas no MVP.',
    true,
    10,
    now()
)
ON CONFLICT (nome_logico) DO UPDATE SET
    titulo = EXCLUDED.titulo,
    descricao = EXCLUDED.descricao,
    ativo = EXCLUDED.ativo,
    ordem_exibicao = EXCLUDED.ordem_exibicao,
    atualizado_em = now();

INSERT INTO config.perfil_camadas_analise (
    perfil_id,
    camada_id,
    obrigatoria,
    ordem_exibicao,
    ativo
)
SELECT
    p.id AS perfil_id,
    c.id AS camada_id,
    false AS obrigatoria,
    c.ordem_exibicao,
    true AS ativo
FROM config.perfis_diagnostico AS p
CROSS JOIN config.camadas_analise AS c
WHERE p.nome_logico = 'diagnostico_ambiental_basico'
  AND c.nome_logico IN (
      'geologia', 'geomorfologia', 'hidrogeologia',
      'pedologia', 'vegetacao', 'hidrografia_ana'
  )
ON CONFLICT (perfil_id, camada_id) DO UPDATE SET
    obrigatoria = EXCLUDED.obrigatoria,
    ordem_exibicao = EXCLUDED.ordem_exibicao,
    ativo = EXCLUDED.ativo;

-- ============================================================================
-- 4. Views auxiliares
-- ============================================================================

CREATE OR REPLACE VIEW config.vw_camadas_analise_ativas AS
SELECT
    c.id,
    c.nome_logico,
    c.titulo,
    c.grupo,
    c.tema,
    c.subtema,
    c.schema_name,
    c.table_name,
    c.geom_column,
    c.tipo_geometria,
    c.srid,
    c.fonte,
    c.ano_referencia,
    c.campo_valor_principal,
    c.campos_descritivos,
    c.metrica_padrao,
    c.tipo_processamento,
    c.usar_area_interesse,
    c.usar_buffer,
    c.usar_microbacia,
    c.usar_setor,
    c.disponivel_dashboard,
    c.disponivel_gpkg,
    c.disponivel_relatorio,
    c.ativo,
    c.ordem_exibicao,
    c.observacao
FROM config.camadas_analise AS c
WHERE c.ativo = true
ORDER BY
    c.grupo,
    c.ordem_exibicao,
    c.tema,
    c.titulo;

CREATE OR REPLACE VIEW config.vw_perfis_diagnostico_camadas AS
SELECT
    p.id AS perfil_id,
    p.nome_logico AS perfil_nome_logico,
    p.titulo AS perfil_titulo,
    p.descricao AS perfil_descricao,
    pc.obrigatoria,
    pc.ordem_exibicao AS ordem_no_perfil,
    pc.ativo AS camada_ativa_no_perfil,
    c.id AS camada_id,
    c.nome_logico AS camada_nome_logico,
    c.titulo AS camada_titulo,
    c.grupo,
    c.tema,
    c.subtema,
    c.metrica_padrao,
    c.tipo_processamento,
    concat_ws(
        ', ',
        CASE WHEN c.usar_area_interesse THEN 'area_interesse' END,
        CASE WHEN c.usar_buffer THEN 'buffer' END,
        CASE WHEN c.usar_microbacia THEN 'microbacia' END,
        CASE WHEN c.usar_setor THEN 'setor' END,
        CASE WHEN c.usar_municipio THEN 'municipio' END
    ) AS unidades_analise_permitidas,
    c.schema_name,
    c.table_name,
    c.geom_column,
    c.campo_valor_principal,
    c.ativo AS camada_ativa
FROM config.perfis_diagnostico AS p
INNER JOIN config.perfil_camadas_analise AS pc
    ON pc.perfil_id = p.id
INNER JOIN config.camadas_analise AS c
    ON c.id = pc.camada_id
ORDER BY
    p.ordem_exibicao,
    p.titulo,
    pc.ordem_exibicao,
    c.grupo,
    c.tema,
    c.titulo;

-- ============================================================================
-- 5. Consultas de conferencia manual apos aplicacao autorizada
-- ============================================================================
/*
SELECT
    nome_logico,
    titulo,
    grupo,
    tema,
    schema_name,
    table_name,
    metrica_padrao,
    tipo_processamento,
    ativo
FROM config.vw_camadas_analise_ativas;

SELECT
    perfil_nome_logico,
    camada_nome_logico,
    camada_titulo,
    unidades_analise_permitidas
FROM config.vw_perfis_diagnostico_camadas
WHERE perfil_nome_logico = 'diagnostico_ambiental_basico';
*/