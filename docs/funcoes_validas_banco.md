# Funcoes validas no banco

Data da sincronizacao local: 2026-06-22

Nenhum SQL foi executado durante esta atualizacao. As informacoes abaixo foram registradas a partir das definicoes reais informadas como extraidas do banco com `pg_get_functiondef` e validadas no DBeaver.

## resultados.processar_setores_intersectados

Assinatura real confirmada:

```sql
resultados.processar_setores_intersectados(
    p_projeto_id bigint,
    p_area_interesse_id bigint,
    p_execucao_id bigint DEFAULT NULL
)
RETURNS TABLE (
    resultado_execucao_id bigint,
    setores_processados integer,
    area_total_intersectada_m2 numeric
)
```

Finalidade: processar a intersecao entre `projetos.area_interesse` e a malha `urbano.setores_censo_2022_malha_br`, gravando resultados em `resultados.setores_intersectados`.

Status: validada no DBeaver.

Observacoes:

- Usa `ai.id AS area_interesse_id`.
- Usa `urbano.setores_censo_2022_malha_br.cd_setor` e `geom`.
- Calcula areas em EPSG:31982.
- Faz `DELETE` controlado por `execucao_id`, `projeto_id` e `area_interesse_id` antes de inserir resultados da execucao.
- Registra logs em `logs.processamento`.
- Mantem tratamento de erro com registro em log e relancamento da excecao.

## resultados.calcular_indicadores_socioeconomicos_mvp

Assinatura real confirmada:

```sql
resultados.calcular_indicadores_socioeconomicos_mvp(
    p_execucao_id bigint,
    p_projeto_id bigint,
    p_area_interesse_id bigint
)
RETURNS TABLE (
    total_indicadores_processados integer,
    total_registros_detalhe integer
)
```

Finalidade: calcular indicadores socioeconomicos a partir de `config.indicadores_mvp`, das tabelas urbanas de origem e dos setores intersectados.

Status: validada no DBeaver.

Observacoes metodologicas:

- A ordem dos parametros e diferente da funcao de setores: `p_execucao_id`, depois `p_projeto_id`, depois `p_area_interesse_id`.
- A versao real validada usa `JOIN` com a tabela de dados de origem, nao `LEFT JOIN`.
- A funcao filtra valores nulos ou nao numericos com `AND public.ea2s_safe_numeric(d.%I::text) IS NOT NULL`.
- Faz `DELETE` controlado por `execucao_id`, `projeto_id` e `area_interesse_id` nas tabelas de detalhe e resumo antes de recalcular.
- Registra logs em `logs.processamento`.
- Usar `LEFT JOIN` para preservar setores sem dado socioeconomico pode ser avaliado como melhoria futura, mas nao faz parte da versao funcional validada no banco.
