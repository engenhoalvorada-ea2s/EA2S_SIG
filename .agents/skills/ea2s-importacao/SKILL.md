# Skill: ea2s-importacao

Use esta skill quando a tarefa envolver inventario, validacao, correcao geometrica, importacao oficial ou cadastro de bases geograficas.

## Objetivo

Manter o fluxo de entrada de dados rastreavel, revisavel e seguro antes de qualquer base virar camada oficial do EA2S SIG.

## Fluxo principal

1. Inventariar arquivo recebido.
2. Calcular hash e detectar duplicidade.
3. Perfilar atributos e geometria.
4. Sugerir grupo, tema, schema e nome tecnico.
5. Validar/corrigir localmente quando necessario.
6. Importar oficialmente de forma controlada.
7. Cadastrar em `config.camadas_analise`.
8. Disponibilizar para plano de diagnostico.

Staging existe como recurso avancado e nao como fluxo principal padrao.

## Inventario

O inventario deve registrar:

- arquivo original;
- hash do arquivo;
- layer, quando existir;
- tipo de geometria;
- CRS/SRID;
- numero de feicoes;
- colunas e tipos;
- nulos e amostras;
- sugestao de tema/schema/tabela;
- pendencias tecnicas.

## Duplicidade

- Nao registrar duplicado silenciosamente.
- Se o hash ja existir, avisar o usuario.
- Permitir duplicado apenas com acao explicita.
- Nao apagar inventarios anteriores sem pedido.

## Correcao e importacao

- Preservar arquivo original.
- Criar copias corrigidas ou produtos derivados em local claro.
- Nao promover para schema oficial sem revisao.
- Nao alterar schemas oficiais sem autorizacao.
- Ao importar oficialmente, registrar origem e metadados.

## Nomes tecnicos

Evitar nomes genericos como:

- `area_interesse`
- `camada`
- `upload`
- `teste`

Preferir nomes com tema, fonte e ano, por exemplo:

- `parcelamento_solo_pmf_2023`
- `pgv_pmf_2023`
- `curso_dagua_ana_2022`

## Exploracao grafica

O grafico exploratorio serve apenas para analise visual inicial dos atributos da base inventariada. Ele nao substitui processamento espacial oficial no PostGIS.