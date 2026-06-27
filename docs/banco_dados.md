# Banco de dados

Banco esperado: `ea2s_sig`, em PostgreSQL/PostGIS.

SRID operacional: EPSG:31982, SIRGAS 2000 / UTM 22S.

## Schemas esperados

### `projetos`

Armazena projetos, areas de interesse e parametros de processamento associados a cada diagnostico territorial.

### `config`

Armazena configuracoes do MVP, incluindo indicadores habilitados em `config.indicadores_mvp`.

### `metadados`

Armazena dicionarios e descricoes tecnicas, incluindo `metadados.dicionario_indicadores`.

### `resultados`

Armazena tabelas e funcoes de processamento, como setores intersectados, detalhes e resumos de indicadores.

### `logs`

Armazena registros de processamento, preferencialmente em `logs.processamento`.

### `urbano`

Schema oficial para dados urbanos importados. Nao alterar dados oficiais diretamente.

### `social`

Schema esperado para dados sociais ou socioeconomicos, quando organizado separadamente. Confirmar nomenclatura real no banco antes de criar scripts dependentes.

### `hidrogeologia`

Schema esperado para dados hidrogeologicos, quando disponivel. Confirmar nomenclatura real no banco antes de criar scripts dependentes.

### `geologia`

Schema oficial para dados geologicos importados. Nao alterar dados oficiais diretamente.

### `geomorfologia`

Schema oficial para dados geomorfologicos importados. Nao alterar dados oficiais diretamente.

### `pedologia`

Schema oficial para dados pedologicos importados. Nao alterar dados oficiais diretamente.

### `vegetacao`

Schema oficial para dados de vegetacao importados. Nao alterar dados oficiais diretamente.

## Outros schemas citados

Tambem foram citados `hidrografia` e `topografia` como schemas oficiais ja usados no projeto. Eles devem ser preservados e tratados como fontes de dados, nao como destino de alteracoes do MVP.
