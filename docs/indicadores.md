# Indicadores

Os indicadores atuais sao provisorios e precisam de revisao tecnica antes de uso em diagnosticos conclusivos. Esta documentacao deve ser atualizada conforme o dicionario de indicadores e os scripts SQL forem consolidados.

## Populacao

- Populacao residente.
- Densidade populacional.
- Distribuicao por faixa etaria, quando disponivel.

## Domicilios

- Total de domicilios.
- Domicilios particulares permanentes.
- Media de moradores por domicilio.

## Infraestrutura

- Abastecimento de agua.
- Energia eletrica.
- Condicoes gerais de atendimento por infraestrutura urbana.

## Esgotamento sanitario

- Domicilios ligados a rede geral.
- Domicilios com fossa septica.
- Domicilios com outras formas de esgotamento.

## Residuos solidos

- Coleta direta.
- Coleta indireta.
- Outras formas de destino dos residuos.

## Renda

- Renda domiciliar.
- Faixas de rendimento.
- Indicadores de vulnerabilidade associados a renda, quando disponiveis.

## Indicadores derivados futuros

- Indices compostos de vulnerabilidade.
- Indicadores normalizados por area ou populacao.
- Cruzamentos entre exposicao ambiental e vulnerabilidade social.
- Indicadores derivados de intersecoes fisico-bioticas.
## Validacao no DBeaver

Todos os indicadores cadastrados em `config.indicadores_mvp` foram validados no DBeaver quanto a existencia de tabela e coluna. A consulta de validacao retornou `ok` para `campo_codigo_setor` e `campo_valor` em todos os indicadores listados. Portanto, a pendencia de confirmar colunas reais de indicadores nas tabelas urbanas foi resolvida.

Chaves setoriais confirmadas:

- `urbano.setores_censo_2022_malha_br`: `cd_setor`
- `urbano.agregados_por_setores_caracteristicas_domicilio1_br`: `CD_setor`
- `urbano.agregados_por_setores_caracteristicas_domicilio2_br`: `setor`
- `urbano.agregados_por_setores_renda_responsavel_br`: `CD_SETOR`

## Indicadores inativos por regra metodologica

Os indicadores abaixo devem permanecer inativos por enquanto, pois variancia nao deve ser tratada como soma ponderada simples no MVP:

- `renda_variancia_moradores_dppo`
- `renda_variancia_rendimento_responsavel`

