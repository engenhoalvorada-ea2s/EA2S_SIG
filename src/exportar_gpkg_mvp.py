import argparse
import os
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path
from typing import NamedTuple

import psycopg2
from dotenv import load_dotenv


REQUIRED_ENV_VARS = (
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
)

TEMAS_AMBIENTAIS = (
    "geologia",
    "geomorfologia",
    "hidrogeologia",
    "pedologia",
    "vegetacao",
)

UNIDADES_AMBIENTAIS = (
    ("area_interesse", "area_interesse"),
    ("buffer_1000m", "buffer_1000m"),
    ("microbacia", "microbacias"),
)

CHAVES_GEOMETRIA = {"geom", "geometry", "the_geom", "wkb_geometry"}

COLUNAS_BASE_AMBIENTAIS = {
    "execucao_id",
    "projeto_id",
    "area_interesse_id",
    "unidade_analise",
    "unidade_analise_codigo",
    "unidade_analise_nome",
    "cd_micro",
    "nm_micro",
    "tema",
    "camada_origem",
    "fonte_schema",
    "fonte_tabela",
    "fonte_camada",
    "feicao_origem_id",
    "campo_principal",
    "valor_principal",
    "area_m2",
    "area_ha",
    "area_unidade_analise_m2",
    "percentual_unidade_analise",
    "data_cadastro",
    "atributos_origem_json",
    "geom",
}

PALAVRAS_RESERVADAS = {
    "all",
    "and",
    "as",
    "by",
    "case",
    "check",
    "column",
    "create",
    "delete",
    "distinct",
    "drop",
    "else",
    "end",
    "false",
    "from",
    "group",
    "insert",
    "join",
    "limit",
    "not",
    "null",
    "on",
    "or",
    "order",
    "select",
    "table",
    "then",
    "true",
    "update",
    "user",
    "where",
}


class ExportarGpkgMvpError(RuntimeError):
    """Erro esperado de validacao da exportacao GeoPackage."""


class LayerExport(NamedTuple):
    name: str
    sql: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Exporta camadas espaciais do MVP EA2S SIG para GeoPackage."
    )
    parser.add_argument("--execucao-id", type=int, required=True)
    parser.add_argument("--projeto-id", type=int, required=True)
    parser.add_argument("--area-interesse-id", type=int, required=True)
    parser.add_argument(
        "--projeto-sig-dir",
        required=True,
        help="Pasta SIG existente do projeto que recebera resultados_mvp/execucao_<id>/gpkg.",
    )
    parser.add_argument("--srid", type=int, default=31982)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Sobrescreve o GeoPackage existente, se houver.",
    )
    parser.add_argument(
        "--incluir-hidrografia",
        action="store_true",
        help="Inclui camadas lineares de hidrografia ANA no GeoPackage.",
    )
    parser.add_argument(
        "--incluir-auditoria",
        action="store_true",
        help="Inclui a camada auditoria_fb_intersecoes_todas com todas as intersecoes fisico-bioticas.",
    )
    return parser.parse_args()


def resolver_pasta_gpkg(args: argparse.Namespace) -> Path:
    projeto_sig_dir = Path(args.projeto_sig_dir).expanduser().resolve()
    if not projeto_sig_dir.exists():
        raise ExportarGpkgMvpError(
            "Pasta SIG do projeto nao encontrada. Confira --projeto-sig-dir: "
            f"{projeto_sig_dir}"
        )
    if not projeto_sig_dir.is_dir():
        raise ExportarGpkgMvpError(
            "O caminho informado em --projeto-sig-dir nao e uma pasta: "
            f"{projeto_sig_dir}"
        )

    pasta_gpkg = (
        projeto_sig_dir
        / "resultados_mvp"
        / f"execucao_{args.execucao_id}"
        / "gpkg"
    )
    pasta_gpkg.mkdir(parents=True, exist_ok=True)
    return pasta_gpkg


def carregar_env() -> dict[str, str]:
    load_dotenv()
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        missing_vars = ", ".join(missing)
        raise ExportarGpkgMvpError(
            f"Variaveis obrigatorias ausentes no .env: {missing_vars}. "
            "Copie .env.example para .env e preencha os valores."
        )
    return {name: os.environ[name] for name in REQUIRED_ENV_VARS}


def abrir_conexao_leitura(env: dict[str, str]):
    return psycopg2.connect(
        host=env["DB_HOST"],
        port=env["DB_PORT"],
        dbname=env["DB_NAME"],
        user=env["DB_USER"],
        password=env["DB_PASSWORD"],
    )


def montar_pg_connection(env: dict[str, str]) -> str:
    return (
        "PG:"
        f"host={env['DB_HOST']} "
        f"port={env['DB_PORT']} "
        f"dbname={env['DB_NAME']} "
        f"user={env['DB_USER']} "
        f"password={env['DB_PASSWORD']}"
    )


def mascarar_senha(texto: str, env: dict[str, str]) -> str:
    senha = env.get("DB_PASSWORD", "")
    if senha:
        return texto.replace(senha, "********")
    return texto


def validar_ogr2ogr() -> str:
    caminho = shutil.which("ogr2ogr")
    if not caminho:
        raise ExportarGpkgMvpError(
            "ogr2ogr nao foi encontrado no PATH. Instale/configure GDAL/OGR "
            "ou execute este exportador pelo ambiente do QGIS/OSGeo4W."
        )
    return caminho


def geom_multipolygon_sql(alias: str, geom_col: str, srid: int, transformar: bool = False) -> str:
    geom_expr = f"{alias}.{geom_col}"
    if transformar:
        geom_expr = f"ST_Transform({geom_expr}, {srid})"
    return f"""ST_Multi(
                ST_CollectionExtract(
                    ST_MakeValid({geom_expr}),
                    3
                )
            )::geometry(MultiPolygon, {srid})"""


def sanitizar_nome_coluna(nome: str, usados: set[str]) -> str:
    texto = unicodedata.normalize("NFKD", str(nome or "atributo"))
    texto = texto.encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^A-Za-z0-9_]+", "_", texto).strip("_").lower()
    texto = re.sub(r"_+", "_", texto)
    if not texto:
        texto = "atributo"
    if texto[0].isdigit():
        texto = f"attr_{texto}"
    if texto in PALAVRAS_RESERVADAS or texto in COLUNAS_BASE_AMBIENTAIS:
        texto = f"orig_{texto}"
    texto = texto[:55].rstrip("_") or "atributo"

    base = texto
    contador = 2
    while texto in usados:
        sufixo = f"_{contador}"
        texto = f"{base[:55 - len(sufixo)]}{sufixo}"
        contador += 1
    usados.add(texto)
    return texto


def escapar_literal_sql(valor: str) -> str:
    return str(valor).replace("'", "''")


def buscar_chaves_atributos_origem(
    env: dict[str, str],
    args: argparse.Namespace,
) -> dict[tuple[str, str], list[tuple[str, str]]]:
    sql = """
        SELECT DISTINCT
            ifb.unidade_analise,
            ifb.tema,
            chave.key AS atributo
        FROM resultados.intersecao_fisico_biotica AS ifb
        CROSS JOIN LATERAL jsonb_object_keys(ifb.atributos_origem) AS chave(key)
        WHERE ifb.execucao_id = %s
          AND ifb.projeto_id = %s
          AND ifb.area_interesse_id = %s
          AND ifb.unidade_analise = ANY(%s)
          AND ifb.tema = ANY(%s)
          AND ifb.atributos_origem IS NOT NULL
        ORDER BY
            ifb.unidade_analise,
            ifb.tema,
            chave.key;
    """
    unidades = [item[0] for item in UNIDADES_AMBIENTAIS]
    try:
        with abrir_conexao_leitura(env) as conn:
            conn.set_session(readonly=True, autocommit=True)
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        args.execucao_id,
                        args.projeto_id,
                        args.area_interesse_id,
                        unidades,
                        list(TEMAS_AMBIENTAIS),
                    ),
                )
                rows = cur.fetchall()
    except Exception as exc:
        raise ExportarGpkgMvpError(
            "Nao foi possivel ler as chaves de atributos_origem. "
            "Confirme se o SQL 05 atualizado foi aplicado e se uma nova execucao "
            "do MVP gravou atributos_origem em resultados.intersecao_fisico_biotica. "
            f"Detalhe: {exc}"
        ) from exc

    atributos: dict[tuple[str, str], list[tuple[str, str]]] = {}
    usados_por_layer: dict[tuple[str, str], set[str]] = {}
    for unidade_analise, tema, atributo in rows:
        if atributo in CHAVES_GEOMETRIA:
            continue
        chave = (unidade_analise, tema)
        usados = usados_por_layer.setdefault(chave, set(COLUNAS_BASE_AMBIENTAIS))
        alias = sanitizar_nome_coluna(atributo, usados)
        atributos.setdefault(chave, []).append((atributo, alias))

    return atributos


def montar_colunas_atributos_origem(colunas: list[tuple[str, str]]) -> str:
    partes = []
    for atributo, alias in colunas:
        partes.append(
            f"ifb.atributos_origem ->> '{escapar_literal_sql(atributo)}' AS {alias}"
        )
    if not partes:
        return ""
    return ",\n            " + ",\n            ".join(partes)


def geom_multiline_sql(alias: str, geom_col: str, srid: int) -> str:
    return f"""ST_Multi(
                ST_CollectionExtract(
                    ST_MakeValid({alias}.{geom_col}),
                    2
                )
            )::geometry(MultiLineString, {srid})"""


def sql_hidrografia(
    execucao_id: int,
    projeto_id: int,
    area_interesse_id: int,
    srid: int,
    unidade_analise: str,
) -> str:
    views_por_unidade = {
        "area_interesse": "resultados.vw_hidrografia_area_interesse",
        "buffer_1000m": "resultados.vw_hidrografia_buffer_1000m",
        "microbacia": "resultados.vw_hidrografia_microbacias",
    }
    view_name = views_por_unidade[unidade_analise]
    return f"""
        SELECT
            h.execucao_id,
            h.projeto_id,
            h.area_interesse_id,
            h.unidade_analise,
            h.cd_micro,
            h.nm_micro,
            h.nm_rio_pri,
            h.fid_ana,
            h.wtc_pk,
            h.idcda,
            h.cocursodag,
            h.cocdadesag,
            h.nunivotcda,
            h.nuordemcda,
            h.dedominial,
            h.dsversao,
            h.codigo_trecho,
            h.codigo_curso,
            h.nome_curso,
            h.comprimento_m,
            h.comprimento_km,
            h.nucompcda_original,
            h.atributos_origem_json,
            {geom_multiline_sql("h", "geom", srid)} AS geom
        FROM {view_name} AS h
        WHERE h.execucao_id = {execucao_id}
          AND h.projeto_id = {projeto_id}
          AND h.area_interesse_id = {area_interesse_id}
          AND h.geom IS NOT NULL
          AND NOT ST_IsEmpty(h.geom)
    """


def sql_buffer_1000m(projeto_id: int, area_interesse_id: int, srid: int) -> str:
    return f"""
        WITH area_interesse AS (
            SELECT
                ai.projeto_id,
                ai.id AS area_interesse_id,
                ai.nome AS nome_area_interesse,
                {geom_multipolygon_sql("ai", "geom", srid, transformar=True)} AS geom_31982
            FROM projetos.area_interesse AS ai
            WHERE ai.projeto_id = {projeto_id}
              AND ai.id = {area_interesse_id}
        ),
        buffer_1000m AS (
            SELECT
                ai.projeto_id,
                ai.area_interesse_id,
                ai.nome_area_interesse,
                1000::numeric AS distancia_buffer_m,
                ST_Multi(
                    ST_CollectionExtract(
                        ST_MakeValid(ST_Buffer(ai.geom_31982, 1000)),
                        3
                    )
                )::geometry(MultiPolygon, {srid}) AS geom
            FROM area_interesse AS ai
        )
        SELECT
            b.projeto_id,
            b.area_interesse_id,
            b.nome_area_interesse,
            b.distancia_buffer_m,
            round(ST_Area(b.geom)::numeric, 4) AS area_buffer_m2,
            round((ST_Area(b.geom) / 10000.0)::numeric, 6) AS area_buffer_ha,
            b.geom
        FROM buffer_1000m AS b
        WHERE NOT ST_IsEmpty(b.geom)
    """


def sql_microbacias_interceptadas(
    execucao_id: int,
    projeto_id: int,
    area_interesse_id: int,
    srid: int,
) -> str:
    return f"""
        WITH area_interesse AS (
            SELECT
                ai.id AS area_interesse_id,
                ai.projeto_id,
                {geom_multipolygon_sql("ai", "geom", srid, transformar=True)} AS geom_31982
            FROM projetos.area_interesse AS ai
            WHERE ai.projeto_id = {projeto_id}
              AND ai.id = {area_interesse_id}
        ),
        microbacias AS (
            SELECT
                mb.cd_micro,
                mb.nm_micro,
                mb.nm_rio_pri,
                mb.cd_bacia,
                mb.cd_ibge_mu,
                mb.sg_tipo,
                mb.vl_qmin7,
                mb.nm_qmin7,
                mb.vl_qrest,
                mb.vl_qsubt,
                mb.shape_area,
                mb.shape_len,
                {geom_multipolygon_sql("mb", "geom", srid, transformar=True)} AS geom_31982
            FROM hidrografia.microbacias_sigeo_sirhesc_aguassc AS mb
            INNER JOIN area_interesse AS ai
                ON mb.geom && ST_Transform(ai.geom_31982, 29192)
               AND ST_Intersects(ST_MakeValid(ST_Transform(mb.geom, {srid})), ai.geom_31982)
        )
        SELECT
            {execucao_id}::bigint AS execucao_id,
            {projeto_id}::bigint AS projeto_id,
            {area_interesse_id}::bigint AS area_interesse_id,
            mb.cd_micro,
            mb.nm_micro,
            mb.nm_rio_pri,
            mb.cd_bacia,
            mb.cd_ibge_mu,
            mb.sg_tipo,
            mb.vl_qmin7,
            mb.nm_qmin7,
            mb.vl_qrest,
            mb.vl_qsubt,
            mb.shape_area,
            mb.shape_len,
            round((ST_Area(ST_Intersection(mb.geom_31982, ai.geom_31982)) / 10000.0)::numeric, 6) AS area_intersecao_ha,
            mb.geom_31982 AS geom
        FROM microbacias AS mb
        CROSS JOIN area_interesse AS ai
        WHERE NOT ST_IsEmpty(mb.geom_31982)
    """


def sql_setores_censitarios_com_socioeconomia(
    execucao_id: int,
    projeto_id: int,
    area_interesse_id: int,
    srid: int,
) -> str:
    return f"""
        SELECT
            c.execucao_id,
            c.projeto_id,
            c.area_interesse_id,
            c.cd_setor,
            c.area_intersecao_ha,
            c.percentual_area_interesse,
            round((si.area_setor_total_m2 / 10000.0)::numeric, 6) AS area_setor_ha,
            c.populacao_total_setor,
            c.total_domicilios_setor,
            c.domicilios_particulares_ocupados_setor,
            c.domicilios_particulares_permanentes_ocupados_setor,
            c.moradores_domicilios_particulares_permanentes_ocupados_setor,
            c.media_moradores_por_domicilio_setor,
            c.responsaveis_dppo_setor,
            c.renda_media_responsavel_setor,
            c.renda_mediana_responsavel_setor,
            c.agua_rede_geral_setor,
            c.lixo_coletado_domicilio_setor,
            c.esgoto_fossa_septica_nao_ligada_rede_setor,
            c.possui_dados_basicos,
            c.possui_dados_dppo,
            c.possui_dados_renda,
            c.possui_dados_saneamento,
            c.status_dados_setor,
            {geom_multipolygon_sql("sc", "geom", srid, transformar=True)} AS geom
        FROM resultados.vw_relatorio_socio_contexto_setores AS c
        INNER JOIN resultados.setores_intersectados AS si
            ON si.execucao_id = c.execucao_id
           AND si.projeto_id = c.projeto_id
           AND si.area_interesse_id = c.area_interesse_id
           AND si.cd_setor = c.cd_setor
        INNER JOIN urbano.setores_censo_2022_malha_br AS sc
            ON public.ea2s_normalizar_codigo_setor(sc.cd_setor::text) = c.cd_setor
        WHERE c.execucao_id = {execucao_id}
          AND c.projeto_id = {projeto_id}
          AND c.area_interesse_id = {area_interesse_id}
          AND sc.geom IS NOT NULL
          AND NOT ST_IsEmpty(ST_Transform(sc.geom, {srid}))
    """


def sql_setores_area_intersectada(
    execucao_id: int,
    projeto_id: int,
    area_interesse_id: int,
    srid: int,
) -> str:
    return f"""
        SELECT
            si.execucao_id,
            si.projeto_id,
            si.area_interesse_id,
            si.cd_setor,
            si.area_intersecao_m2,
            si.area_intersecao_ha,
            si.area_setor_total_m2,
            round((si.area_setor_total_m2 / 10000.0)::numeric, 6) AS area_setor_ha,
            si.percentual_setor_intersectado,
            si.percentual_area_interesse,
            si.data_cadastro,
            {geom_multipolygon_sql("si", "geom", srid)} AS geom
        FROM resultados.setores_intersectados AS si
        WHERE si.execucao_id = {execucao_id}
          AND si.projeto_id = {projeto_id}
          AND si.area_interesse_id = {area_interesse_id}
          AND si.geom IS NOT NULL
          AND NOT ST_IsEmpty(si.geom)
    """


def sql_fisico_biotico_por_unidade_tema(
    execucao_id: int,
    projeto_id: int,
    area_interesse_id: int,
    srid: int,
    unidade_analise: str,
    tema: str,
    atributos_origem: list[tuple[str, str]],
) -> str:
    campos_microbacia = ""
    if unidade_analise == "microbacia":
        campos_microbacia = """
            ifb.unidade_analise_codigo AS cd_micro,
            ifb.unidade_analise_nome AS nm_micro,"""
    campos_atributos = montar_colunas_atributos_origem(atributos_origem)

    return f"""
        SELECT
            ifb.execucao_id,
            ifb.projeto_id,
            ifb.area_interesse_id,
            ifb.unidade_analise,
            ifb.unidade_analise_codigo,
            ifb.unidade_analise_nome,{campos_microbacia}
            ifb.tema,
            ifb.camada_origem,
            ifb.fonte_schema,
            ifb.fonte_tabela,
            ifb.fonte_camada,
            ifb.feicao_origem_id,
            ifb.campo_principal,
            COALESCE(NULLIF(btrim(ifb.valor_principal), ''), 'Sem classificacao informada') AS valor_principal,
            ifb.area_intersecao_m2 AS area_m2,
            ifb.area_intersecao_ha AS area_ha,
            ifb.area_unidade_analise_m2,
            ifb.percentual_unidade_analise,
            ifb.data_cadastro,
            ifb.atributos_origem::text AS atributos_origem_json{campos_atributos},
            {geom_multipolygon_sql("ifb", "geom", srid)} AS geom
        FROM resultados.intersecao_fisico_biotica AS ifb
        WHERE ifb.execucao_id = {execucao_id}
          AND ifb.projeto_id = {projeto_id}
          AND ifb.area_interesse_id = {area_interesse_id}
          AND ifb.unidade_analise = '{unidade_analise}'
          AND ifb.tema = '{tema}'
          AND ifb.geom IS NOT NULL
          AND NOT ST_IsEmpty(ifb.geom)
    """


def sql_auditoria_fisico_biotica(
    execucao_id: int,
    projeto_id: int,
    area_interesse_id: int,
    srid: int,
) -> str:
    return f"""
        SELECT
            ifb.id,
            ifb.execucao_id,
            ifb.projeto_id,
            ifb.area_interesse_id,
            ifb.unidade_analise,
            ifb.unidade_analise_codigo,
            ifb.unidade_analise_nome,
            ifb.tema,
            ifb.camada_origem,
            ifb.fonte_schema,
            ifb.fonte_tabela,
            ifb.fonte_camada,
            ifb.feicao_origem_id,
            ifb.campo_principal,
            COALESCE(NULLIF(btrim(ifb.valor_principal), ''), 'Sem classificacao informada') AS valor_principal,
            ifb.area_intersecao_m2 AS area_m2,
            ifb.area_intersecao_ha AS area_ha,
            ifb.area_unidade_analise_m2,
            ifb.percentual_unidade_analise,
            ifb.data_cadastro,
            ifb.atributos_origem::text AS atributos_origem_json,
            {geom_multipolygon_sql("ifb", "geom", srid)} AS geom
        FROM resultados.intersecao_fisico_biotica AS ifb
        WHERE ifb.execucao_id = {execucao_id}
          AND ifb.projeto_id = {projeto_id}
          AND ifb.area_interesse_id = {area_interesse_id}
          AND ifb.geom IS NOT NULL
          AND NOT ST_IsEmpty(ifb.geom)
    """


def montar_layers(
    args: argparse.Namespace,
    atributos_por_unidade_tema: dict[tuple[str, str], list[tuple[str, str]]],
) -> tuple[LayerExport, ...]:
    layers: list[LayerExport] = [
        LayerExport(
            "buffer_1000m",
            sql_buffer_1000m(args.projeto_id, args.area_interesse_id, args.srid),
        ),
        LayerExport(
            "microbacias_interceptadas",
            sql_microbacias_interceptadas(
                args.execucao_id,
                args.projeto_id,
                args.area_interesse_id,
                args.srid,
            ),
        ),
        LayerExport(
            "setores_censitarios_intersectados",
            sql_setores_censitarios_com_socioeconomia(
                args.execucao_id,
                args.projeto_id,
                args.area_interesse_id,
                args.srid,
            ),
        ),
        LayerExport(
            "setores_censitarios_area_intersectada",
            sql_setores_area_intersectada(
                args.execucao_id,
                args.projeto_id,
                args.area_interesse_id,
                args.srid,
            ),
        ),
    ]

    if args.incluir_hidrografia:
        layers.extend(
            [
                LayerExport(
                    "hidrografia_area_interesse",
                    sql_hidrografia(
                        args.execucao_id,
                        args.projeto_id,
                        args.area_interesse_id,
                        args.srid,
                        "area_interesse",
                    ),
                ),
                LayerExport(
                    "hidrografia_buffer_1000m",
                    sql_hidrografia(
                        args.execucao_id,
                        args.projeto_id,
                        args.area_interesse_id,
                        args.srid,
                        "buffer_1000m",
                    ),
                ),
                LayerExport(
                    "hidrografia_microbacias",
                    sql_hidrografia(
                        args.execucao_id,
                        args.projeto_id,
                        args.area_interesse_id,
                        args.srid,
                        "microbacia",
                    ),
                ),
            ]
        )

    for unidade_analise, prefixo_layer in UNIDADES_AMBIENTAIS:
        for tema in TEMAS_AMBIENTAIS:
            atributos_origem = atributos_por_unidade_tema.get((unidade_analise, tema), [])
            if not atributos_origem:
                print(
                    "Aviso: nenhuma chave em atributos_origem encontrada para "
                    f"{unidade_analise}/{tema}. A camada tera apenas atributos base "
                    "e atributos_origem_json."
                )
            layers.append(
                LayerExport(
                    f"{prefixo_layer}_{tema}",
                    sql_fisico_biotico_por_unidade_tema(
                        args.execucao_id,
                        args.projeto_id,
                        args.area_interesse_id,
                        args.srid,
                        unidade_analise,
                        tema,
                        atributos_origem,
                    ),
                )
            )

    if args.incluir_auditoria:
        layers.append(
            LayerExport(
                "auditoria_fb_intersecoes_todas",
                sql_auditoria_fisico_biotica(
                    args.execucao_id,
                    args.projeto_id,
                    args.area_interesse_id,
                    args.srid,
                ),
            )
        )

    return tuple(layers)


def montar_comando_ogr2ogr(
    ogr2ogr_path: str,
    gpkg_path: Path,
    pg_connection: str,
    layer: LayerExport,
    srid: int,
) -> list[str]:
    comando = [ogr2ogr_path, "-f", "GPKG"]
    if gpkg_path.exists():
        comando.append("-update")
    comando.extend(
        [
            str(gpkg_path),
            pg_connection,
            "-sql",
            layer.sql,
            "-nln",
            layer.name,
            "-nlt",
            "PROMOTE_TO_MULTI",
            "-dim",
            "XY",
            "-a_srs",
            f"EPSG:{srid}",
            "-lco",
            "ENCODING=UTF-8",
        ]
    )
    return comando


def exportar_layer(
    ogr2ogr_path: str,
    gpkg_path: Path,
    pg_connection: str,
    layer: LayerExport,
    srid: int,
    env: dict[str, str],
) -> tuple[bool, str | None]:
    comando = montar_comando_ogr2ogr(ogr2ogr_path, gpkg_path, pg_connection, layer, srid)
    processo = subprocess.run(
        comando,
        check=False,
        capture_output=True,
        text=True,
    )
    if processo.returncode == 0:
        print(f"Camada exportada: {layer.name}")
        return True, None

    erro = processo.stderr.strip() or processo.stdout.strip() or "erro nao informado pelo ogr2ogr"
    erro = mascarar_senha(erro, env)
    print(f"Erro ao exportar camada {layer.name}: {erro}")
    return False, erro


def preparar_gpkg(args: argparse.Namespace, pasta_gpkg: Path) -> Path:
    gpkg_path = pasta_gpkg / f"ea2s_sig_execucao_{args.execucao_id}.gpkg"
    if gpkg_path.exists():
        if not args.overwrite:
            raise ExportarGpkgMvpError(
                "GeoPackage ja existe. Use --overwrite para recriar o arquivo: "
                f"{gpkg_path}"
            )
        gpkg_path.unlink()
    return gpkg_path


def exportar_gpkg(args: argparse.Namespace) -> tuple[Path, list[str], list[tuple[str, str]]]:
    pasta_gpkg = resolver_pasta_gpkg(args)
    gpkg_path = preparar_gpkg(args, pasta_gpkg)
    ogr2ogr_path = validar_ogr2ogr()
    env = carregar_env()
    pg_connection = montar_pg_connection(env)
    atributos_por_unidade_tema = buscar_chaves_atributos_origem(env, args)

    camadas_exportadas: list[str] = []
    camadas_com_erro: list[tuple[str, str]] = []

    for layer in montar_layers(args, atributos_por_unidade_tema):
        print(f"Exportando camada {layer.name}...")
        sucesso, erro = exportar_layer(
            ogr2ogr_path,
            gpkg_path,
            pg_connection,
            layer,
            args.srid,
            env,
        )
        if sucesso:
            camadas_exportadas.append(layer.name)
        else:
            camadas_com_erro.append((layer.name, erro or "erro nao informado"))

    if not camadas_exportadas:
        raise ExportarGpkgMvpError(
            "Nenhuma camada foi exportada. Revise os erros informados pelo ogr2ogr."
        )

    return gpkg_path, camadas_exportadas, camadas_com_erro


def imprimir_resumo(
    gpkg_path: Path,
    camadas_exportadas: list[str],
    camadas_com_erro: list[tuple[str, str]],
) -> None:
    print("\nGeoPackage gerado em:")
    print(gpkg_path)
    print("\nCamadas exportadas com sucesso:")
    for camada in camadas_exportadas:
        print(f"- {camada}")

    if camadas_com_erro:
        print("\nCamadas com erro:")
        for camada, erro in camadas_com_erro:
            print(f"- {camada}: {erro}")
        print("\nExportacao concluida com avisos.")
    else:
        print("\nExportacao concluida sem erros de camada.")


def main() -> None:
    args = parse_args()
    try:
        gpkg_path, camadas_exportadas, camadas_com_erro = exportar_gpkg(args)
        imprimir_resumo(gpkg_path, camadas_exportadas, camadas_com_erro)
    except ExportarGpkgMvpError as exc:
        raise SystemExit(f"Erro de validacao: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"Erro ao exportar GeoPackage do MVP: {exc}") from exc


if __name__ == "__main__":
    main()
