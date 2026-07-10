-- EA2S SIG - Fluxo de projeto e area de interesse
--
-- Objetivo:
-- Preparar campos de apoio para o fluxo funcional do WebGIS Streamlit,
-- permitindo registrar a pasta SIG do projeto e atualizar metadados de projeto.
--
-- Seguranca:
-- - Nao usa DROP.
-- - Nao apaga dados.
-- - Nao altera schemas oficiais de dados geograficos.
-- - Altera apenas a tabela operacional projetos.projeto.

ALTER TABLE projetos.projeto
ADD COLUMN IF NOT EXISTS pasta_sig text;

COMMENT ON COLUMN projetos.projeto.pasta_sig IS
    'Pasta local ou de rede onde serao salvos os produtos exportados do projeto, como planilhas, graficos, GeoPackage e relatorios.';

ALTER TABLE projetos.projeto
ADD COLUMN IF NOT EXISTS data_atualizacao timestamp DEFAULT now();

COMMENT ON COLUMN projetos.projeto.data_atualizacao IS
    'Data de atualizacao do cadastro do projeto pelo fluxo operacional do WebGIS.';

-- Conferencias manuais sugeridas apos aplicacao autorizada:
-- SELECT column_name, data_type
-- FROM information_schema.columns
-- WHERE table_schema = 'projetos'
--   AND table_name = 'projeto'
--   AND column_name IN ('pasta_sig', 'data_atualizacao')
-- ORDER BY column_name;
