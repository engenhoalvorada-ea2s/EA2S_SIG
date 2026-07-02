"""Interface Streamlit inicial do MVP EA2S SIG.

Esta primeira versao e uma camada de leitura, selecao e montagem de comandos.
Ela nao cria, altera ou apaga dados no banco e nao executa scripts automaticamente.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import json

import pandas as pd
import plotly.express as px
import streamlit as st

try:
    import folium
    from streamlit_folium import st_folium
except ImportError:  # pragma: no cover - exibido na interface quando faltar dependencia
    folium = None
    st_folium = None

from db import get_connection


APP_TITLE = "EA2S SIG - Agente de Geoprocessamento"
PAGE_OPTIONS = (
    "Início",
    "Projetos e áreas",
    "Configurar diagnóstico",
    "Executar processamento",
    "Resultados",
    "Mapa",
    "Resumo estatístico",
)

ANALISES_AMBIENTAIS = (
    "geologia",
    "geomorfologia",
    "hidrogeologia",
    "pedologia",
    "vegetacao",
    "hidrografia_ana",
)

ANALISES_ROTULOS = {
    "geologia": "Geologia",
    "geomorfologia": "Geomorfologia",
    "hidrogeologia": "Hidrogeologia",
    "pedologia": "Pedologia",
    "vegetacao": "Vegetação",
    "hidrografia_ana": "Hidrografia ANA",
    "socioeconomia": "Setores censitários e indicadores socioeconômicos",
}

UNIDADES_ESPACIAIS = (
    "area_interesse",
    "buffer",
    "microbacias",
    "setores_censitarios",
)

UNIDADES_ROTULOS = {
    "area_interesse": "Área de interesse",
    "buffer": "Buffer",
    "microbacias": "Microbacias",
    "setores_censitarios": "Setores censitários",
}


@dataclass(frozen=True)
class QueryResult:
    ok: bool
    data: pd.DataFrame
    erro: str | None = None


def configurar_pagina() -> None:
    st.set_page_config(
        page_title="EA2S SIG",
        layout="wide",
    )


def parametros_padrao() -> dict[str, Any]:
    return {
        "geologia": True,
        "geomorfologia": True,
        "hidrogeologia": True,
        "pedologia": True,
        "vegetacao": True,
        "hidrografia_ana": False,
        "socioeconomia": True,
        "area_interesse": True,
        "buffer": True,
        "microbacias": True,
        "setores_censitarios": True,
        "usar_buffer": True,
        "distancia_buffer_m": 1000,
    }


def inicializar_estado() -> None:
    defaults: dict[str, Any] = {
        "projeto_id": None,
        "area_interesse_id": None,
        "execucao_id": "",
        "projeto_sig_dir": "",
        "usuario_execucao": "Paulo",
        "parametros_diagnostico": parametros_padrao(),
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def fetch_dataframe(sql: str, params: tuple[Any, ...] = ()) -> QueryResult:
    try:
        with get_connection() as conn:
            conn.set_session(readonly=True, autocommit=True)
            data = pd.read_sql_query(sql, conn, params=params)
        return QueryResult(ok=True, data=data)
    except Exception as exc:  # pragma: no cover - exibido na interface
        return QueryResult(ok=False, data=pd.DataFrame(), erro=str(exc))


def fetch_scalar(sql: str, params: tuple[Any, ...] = ()) -> Any:
    result = fetch_dataframe(sql, params)
    if not result.ok or result.data.empty:
        return None
    return result.data.iloc[0, 0]


def testar_conexao() -> dict[str, Any]:
    status = {
        "ok": False,
        "database": None,
        "usuario": None,
        "total_projetos": None,
        "erro": None,
    }
    result = fetch_dataframe(
        """
        SELECT
            current_database() AS database,
            current_user AS usuario,
            (
                SELECT count(*)
                FROM projetos.projeto
            ) AS total_projetos;
        """
    )
    if result.ok and not result.data.empty:
        row = result.data.iloc[0]
        status.update(
            {
                "ok": True,
                "database": row.get("database"),
                "usuario": row.get("usuario"),
                "total_projetos": row.get("total_projetos"),
            }
        )
    else:
        status["erro"] = result.erro or "Não foi possível consultar o banco."
    return status


def tabela_tem_coluna(schema: str, tabela: str, coluna: str) -> bool:
    valor = fetch_scalar(
        """
        SELECT 1
        FROM information_schema.columns AS c
        WHERE c.table_schema = %s
          AND c.table_name = %s
          AND c.column_name = %s;
        """,
        (schema, tabela, coluna),
    )
    return valor is not None


def colunas_existentes(schema: str, tabela: str, candidatas: tuple[str, ...]) -> set[str]:
    result = fetch_dataframe(
        """
        SELECT c.column_name
        FROM information_schema.columns AS c
        WHERE c.table_schema = %s
          AND c.table_name = %s
          AND c.column_name = ANY(%s)
        ORDER BY c.ordinal_position;
        """,
        (schema, tabela, list(candidatas)),
    )
    if not result.ok:
        return set()
    return set(result.data["column_name"].tolist())


def montar_select_colunas(
    alias: str,
    candidatas: tuple[str, ...],
    existentes: set[str],
) -> str:
    partes = []
    for coluna in candidatas:
        if coluna in existentes:
            partes.append(f"{alias}.{coluna}")
        else:
            partes.append(f"NULL::text AS {coluna}")
    return ",\n            ".join(partes)


def carregar_projetos() -> QueryResult:
    candidatas = ("id", "codigo", "codigo_projeto", "nome", "cliente", "municipio", "uf")
    existentes = colunas_existentes("projetos", "projeto", candidatas)
    select_cols = montar_select_colunas("p", candidatas, existentes)
    return fetch_dataframe(
        f"""
        SELECT
            {select_cols}
        FROM projetos.projeto AS p
        ORDER BY p.id;
        """
    )


def carregar_areas(projeto_id: int) -> QueryResult:
    candidatas = ("id", "projeto_id", "nome", "tipo", "area_ha", "srid_origem")
    existentes = colunas_existentes("projetos", "area_interesse", candidatas)
    select_cols = montar_select_colunas("ai", candidatas, existentes)
    return fetch_dataframe(
        f"""
        SELECT
            {select_cols}
        FROM projetos.area_interesse AS ai
        WHERE ai.projeto_id = %s
        ORDER BY ai.id;
        """,
        (projeto_id,),
    )


def carregar_ultimas_execucoes(limit: int = 10) -> QueryResult:
    return fetch_dataframe(
        """
        SELECT
            e.id,
            e.projeto_id,
            e.nome,
            e.tipo_execucao,
            e.status,
            e.iniciado_em,
            e.finalizado_em,
            e.usuario
        FROM resultados.execucao AS e
        ORDER BY e.iniciado_em DESC NULLS LAST, e.id DESC
        LIMIT %s;
        """,
        (limit,),
    )


def carregar_execucoes_contexto(
    projeto_id: int | None,
    area_interesse_id: int | None,
    limit: int = 20,
) -> QueryResult:
    tem_parametros = tabela_tem_coluna("resultados", "execucao", "parametros")
    area_expr = "e.parametros ->> 'area_interesse_id'" if tem_parametros else "NULL::text"
    filtros = []
    params: list[Any] = []

    if projeto_id:
        filtros.append("e.projeto_id = %s")
        params.append(projeto_id)
    if area_interesse_id and tem_parametros:
        filtros.append("e.parametros ->> 'area_interesse_id' = %s")
        params.append(str(area_interesse_id))

    where_sql = "WHERE " + " AND ".join(filtros) if filtros else ""
    params.append(limit)

    return fetch_dataframe(
        f"""
        SELECT
            e.id,
            e.projeto_id,
            {area_expr} AS area_interesse_id,
            e.nome,
            e.tipo_execucao,
            e.status,
            e.iniciado_em,
            e.finalizado_em,
            e.usuario
        FROM resultados.execucao AS e
        {where_sql}
        ORDER BY e.iniciado_em DESC NULLS LAST, e.id DESC
        LIMIT %s;
        """,
        tuple(params),
    )


def view_existe(view_name: str) -> bool:
    return fetch_scalar("SELECT to_regclass(%s);", (view_name,)) is not None


def carregar_resultado_view(
    view_name: str,
    execucao_id: int,
    projeto_id: int,
    area_interesse_id: int,
) -> QueryResult:
    views_permitidas = {
        "resultados.vw_relatorio_sintese_executiva",
        "resultados.vw_relatorio_socio_total_setores",
        "resultados.vw_fisico_biotico_sintese_unidade_tema",
        "resultados.vw_hidrografia_resumo",
    }
    if view_name not in views_permitidas:
        return QueryResult(False, pd.DataFrame(), "View não permitida.")
    return fetch_dataframe(
        f"""
        SELECT *
        FROM {view_name}
        WHERE execucao_id = %s
          AND projeto_id = %s
          AND area_interesse_id = %s;
        """,
        (execucao_id, projeto_id, area_interesse_id),
    )


def label_registro(row: pd.Series, prefixo: str) -> str:
    partes = [f"{prefixo} {row.get('id')}"]
    for campo in ("codigo_projeto", "codigo", "nome", "cliente", "municipio", "uf"):
        valor = row.get(campo)
        if pd.notna(valor) and str(valor).strip():
            partes.append(str(valor))
    return " - ".join(partes)


def label_execucao(row: pd.Series) -> str:
    iniciado = row.get("iniciado_em")
    if pd.notna(iniciado):
        iniciado_txt = pd.to_datetime(iniciado).strftime("%Y-%m-%d")
    else:
        iniciado_txt = "sem data"
    status = row.get("status") if pd.notna(row.get("status")) else "sem status"
    usuario = row.get("usuario") if pd.notna(row.get("usuario")) else "sem usuario"
    return f"{row.get('id')} - {status} - {iniciado_txt} - {usuario}"


def parametros() -> dict[str, Any]:
    return st.session_state["parametros_diagnostico"]


def hidrografia_marcada() -> bool:
    return bool(parametros().get("hidrografia_ana"))


def formatar_powershell(partes: list[str]) -> str:
    return " ".join(quote_windows(arg) for arg in partes)


def quote_windows(valor: str) -> str:
    if not valor:
        return '""'
    if any(char.isspace() for char in valor) or "\\" in valor or ":" in valor:
        return f'"{valor}"'
    return valor


def comando_mvp() -> str | None:
    projeto_id = st.session_state.get("projeto_id")
    area_id = st.session_state.get("area_interesse_id")
    if not projeto_id or not area_id:
        return None

    comando = [
        "python",
        "src\\executar_mvp.py",
        "--projeto-id",
        str(projeto_id),
        "--area-interesse-id",
        str(area_id),
        "--usuario",
        str(st.session_state.get("usuario_execucao") or "Paulo"),
    ]
    if hidrografia_marcada():
        comando.append("--incluir-hidrografia")
    return formatar_powershell(comando)


def comando_validar_configuracao() -> str | None:
    comando = comando_mvp()
    if comando:
        return f"{comando} --dry-run"
    return None


def comando_com_execucao(script: str, incluir_overwrite: bool = False) -> tuple[str | None, str | None]:
    execucao_id = str(st.session_state.get("execucao_id") or "").strip()
    projeto_id = st.session_state.get("projeto_id")
    area_id = st.session_state.get("area_interesse_id")
    projeto_sig_dir = str(st.session_state.get("projeto_sig_dir") or "").strip()

    if not execucao_id:
        return None, "Informe a Execução ID para exportações."
    if not projeto_id or not area_id:
        return None, "Selecione projeto e área de interesse."
    if not projeto_sig_dir:
        return None, "Informe a Pasta SIG do projeto para exportações."

    comando = [
        "python",
        script,
        "--execucao-id",
        execucao_id,
        "--projeto-id",
        str(projeto_id),
        "--area-interesse-id",
        str(area_id),
        "--projeto-sig-dir",
        projeto_sig_dir,
    ]
    if incluir_overwrite:
        comando.append("--overwrite")
    return formatar_powershell(comando), None


def comando_exportar_planilhas() -> tuple[str | None, str | None]:
    return comando_com_execucao("src\\exportar_resultados_mvp.py")


def comando_gerar_graficos() -> tuple[str | None, str | None]:
    return comando_com_execucao("src\\gerar_graficos_mvp.py")


def comando_exportar_gpkg() -> tuple[str | None, str | None]:
    comando, erro = comando_com_execucao("src\\exportar_gpkg_mvp.py", incluir_overwrite=True)
    if comando and hidrografia_marcada():
        comando = f"{comando} --incluir-hidrografia"
    return comando, erro


def exibir_resultado_query(titulo: str, result: QueryResult, vazio: str | None = None) -> None:
    st.subheader(titulo)
    if not result.ok:
        st.warning(result.erro or f"View indisponível: {titulo}")
        return
    if result.data.empty:
        st.info(vazio or "Nenhum registro encontrado.")
        return
    st.dataframe(result.data, use_container_width=True)


def normalizar_geojson(valor: Any) -> dict[str, Any] | None:
    if valor is None:
        return None
    if isinstance(valor, dict):
        return valor
    if isinstance(valor, str):
        try:
            return json.loads(valor)
        except json.JSONDecodeError:
            return None
    return None


def executar_geojson_select(
    conn: Any,
    sql: str,
    params: tuple[Any, ...],
) -> dict[str, Any] | None:
    try:
        data = pd.read_sql_query(sql, conn, params=params)
    except Exception:
        return None
    if data.empty or "geojson" not in data.columns:
        return None
    return normalizar_geojson(data.iloc[0]["geojson"])


def carregar_geojson_area_interesse(
    conn: Any,
    projeto_id: int,
    area_interesse_id: int,
) -> dict[str, Any] | None:
    return executar_geojson_select(
        conn,
        """
        WITH base AS (
            SELECT
                ai.id,
                ai.projeto_id,
                ai.nome,
                to_jsonb(ai) ->> 'tipo' AS tipo,
                to_jsonb(ai) ->> 'area_ha' AS area_ha,
                ST_SimplifyPreserveTopology(
                    ST_Transform(ai.geom, 4326),
                    0.00001
                ) AS geom_4326
            FROM projetos.area_interesse AS ai
            WHERE ai.projeto_id = %s
              AND ai.id = %s
              AND ai.geom IS NOT NULL
        )
        SELECT json_build_object(
            'type', 'FeatureCollection',
            'features', COALESCE(
                json_agg(
                    json_build_object(
                        'type', 'Feature',
                        'geometry', ST_AsGeoJSON(b.geom_4326)::json,
                        'properties', json_build_object(
                            'id', b.id,
                            'projeto_id', b.projeto_id,
                            'nome', b.nome,
                            'tipo', b.tipo,
                            'area_ha', b.area_ha
                        )
                    )
                ),
                '[]'::json
            )
        ) AS geojson
        FROM base AS b;
        """,
        (projeto_id, area_interesse_id),
    )


def carregar_geojson_buffer(
    conn: Any,
    projeto_id: int,
    area_interesse_id: int,
    distancia_buffer_m: int = 1000,
) -> dict[str, Any] | None:
    return executar_geojson_select(
        conn,
        """
        WITH base AS (
            SELECT
                ai.id AS area_interesse_id,
                ai.projeto_id,
                ST_SimplifyPreserveTopology(
                    ST_Transform(
                        ST_Buffer(ST_Transform(ai.geom, 31982), %s),
                        4326
                    ),
                    0.00001
                ) AS geom_4326
            FROM projetos.area_interesse AS ai
            WHERE ai.projeto_id = %s
              AND ai.id = %s
              AND ai.geom IS NOT NULL
        )
        SELECT json_build_object(
            'type', 'FeatureCollection',
            'features', COALESCE(
                json_agg(
                    json_build_object(
                        'type', 'Feature',
                        'geometry', ST_AsGeoJSON(b.geom_4326)::json,
                        'properties', json_build_object(
                            'projeto_id', b.projeto_id,
                            'area_interesse_id', b.area_interesse_id,
                            'distancia_buffer_m', %s
                        )
                    )
                ),
                '[]'::json
            )
        ) AS geojson
        FROM base AS b;
        """,
        (distancia_buffer_m, projeto_id, area_interesse_id, distancia_buffer_m),
    )


def carregar_geojson_microbacias(
    conn: Any,
    projeto_id: int,
    area_interesse_id: int,
) -> dict[str, Any] | None:
    return executar_geojson_select(
        conn,
        """
        WITH area_interesse AS (
            SELECT ST_Transform(ai.geom, 31982) AS geom_31982
            FROM projetos.area_interesse AS ai
            WHERE ai.projeto_id = %s
              AND ai.id = %s
              AND ai.geom IS NOT NULL
        ),
        base AS (
            SELECT
                mb.cd_micro,
                mb.nm_micro,
                mb.nm_rio_pri,
                ST_SimplifyPreserveTopology(
                    ST_Transform(ST_MakeValid(mb.geom), 4326),
                    0.00001
                ) AS geom_4326
            FROM hidrografia.microbacias_sigeo_sirhesc_aguassc AS mb
            INNER JOIN area_interesse AS ai
                ON mb.geom && ST_Transform(ai.geom_31982, 29192)
               AND ST_Intersects(
                    ST_Transform(ST_MakeValid(mb.geom), 31982),
                    ai.geom_31982
               )
            WHERE mb.geom IS NOT NULL
        )
        SELECT json_build_object(
            'type', 'FeatureCollection',
            'features', COALESCE(
                json_agg(
                    json_build_object(
                        'type', 'Feature',
                        'geometry', ST_AsGeoJSON(b.geom_4326)::json,
                        'properties', json_build_object(
                            'cd_micro', b.cd_micro,
                            'nm_micro', b.nm_micro,
                            'nm_rio_pri', b.nm_rio_pri
                        )
                    )
                ),
                '[]'::json
            )
        ) AS geojson
        FROM base AS b;
        """,
        (projeto_id, area_interesse_id),
    )


def carregar_geojson_setores(
    conn: Any,
    execucao_id: int,
    projeto_id: int,
    area_interesse_id: int,
) -> dict[str, Any] | None:
    return executar_geojson_select(
        conn,
        """
        WITH base AS (
            SELECT
                si.cd_setor,
                si.area_intersecao_m2,
                si.area_intersecao_ha,
                si.percentual_area_interesse,
                si.percentual_setor_intersectado,
                ST_SimplifyPreserveTopology(
                    ST_Transform(si.geom, 4326),
                    0.00001
                ) AS geom_4326
            FROM resultados.setores_intersectados AS si
            WHERE si.execucao_id = %s
              AND si.projeto_id = %s
              AND si.area_interesse_id = %s
              AND si.geom IS NOT NULL
        )
        SELECT json_build_object(
            'type', 'FeatureCollection',
            'features', COALESCE(
                json_agg(
                    json_build_object(
                        'type', 'Feature',
                        'geometry', ST_AsGeoJSON(b.geom_4326)::json,
                        'properties', json_build_object(
                            'cd_setor', b.cd_setor,
                            'area_intersecao_m2', b.area_intersecao_m2,
                            'area_intersecao_ha', b.area_intersecao_ha,
                            'percentual_area_interesse', b.percentual_area_interesse,
                            'percentual_setor_intersectado', b.percentual_setor_intersectado
                        )
                    )
                ),
                '[]'::json
            )
        ) AS geojson
        FROM base AS b;
        """,
        (execucao_id, projeto_id, area_interesse_id),
    )


def carregar_geojson_hidrografia(
    conn: Any,
    execucao_id: int,
    projeto_id: int,
    area_interesse_id: int,
) -> dict[str, Any] | None:
    return executar_geojson_select(
        conn,
        """
        WITH base AS (
            SELECT
                ih.idcda,
                ih.cocursodag,
                ih.nuordemcda,
                ih.nunivotcda,
                ih.comprimento_m,
                ih.unidade_analise,
                ST_SimplifyPreserveTopology(
                    ST_Transform(ih.geom, 4326),
                    0.00001
                ) AS geom_4326
            FROM resultados.intersecao_hidrografia AS ih
            WHERE ih.execucao_id = %s
              AND ih.projeto_id = %s
              AND ih.area_interesse_id = %s
              AND ih.unidade_analise = 'buffer_1000m'
              AND ih.geom IS NOT NULL
        )
        SELECT json_build_object(
            'type', 'FeatureCollection',
            'features', COALESCE(
                json_agg(
                    json_build_object(
                        'type', 'Feature',
                        'geometry', ST_AsGeoJSON(b.geom_4326)::json,
                        'properties', json_build_object(
                            'idcda', b.idcda,
                            'cocursodag', b.cocursodag,
                            'nuordemcda', b.nuordemcda,
                            'nunivotcda', b.nunivotcda,
                            'comprimento_m', b.comprimento_m,
                            'unidade_analise', b.unidade_analise
                        )
                    )
                ),
                '[]'::json
            )
        ) AS geojson
        FROM base AS b;
        """,
        (execucao_id, projeto_id, area_interesse_id),
    )


def geojson_tem_features(geojson: dict[str, Any] | None) -> bool:
    return bool(geojson and geojson.get("features"))


def estilo_area_interesse(_: Any) -> dict[str, Any]:
    return {"color": "#d73027", "weight": 4, "fillColor": "#d73027", "fillOpacity": 0.08}


def estilo_buffer(_: Any) -> dict[str, Any]:
    return {"color": "#fdae61", "weight": 2, "fillColor": "#fdae61", "fillOpacity": 0.05}


def estilo_microbacias(_: Any) -> dict[str, Any]:
    return {"color": "#4575b4", "weight": 2, "fillColor": "#4575b4", "fillOpacity": 0.04}


def estilo_setores(_: Any) -> dict[str, Any]:
    return {"color": "#313695", "weight": 1, "fillColor": "#313695", "fillOpacity": 0.03}


def estilo_hidrografia(_: Any) -> dict[str, Any]:
    return {"color": "#2b83ba", "weight": 3, "opacity": 0.85}


def adicionar_geojson(
    mapa: Any,
    geojson: dict[str, Any] | None,
    nome: str,
    style_function: Any,
) -> Any | None:
    if folium is None or not geojson_tem_features(geojson):
        return None
    camada = folium.GeoJson(
        geojson,
        name=nome,
        style_function=style_function,
    )
    camada.add_to(mapa)
    return camada

LIMITES_ANALISE_RESUMO = {
    "Área de interesse": "area_interesse",
    "Buffer de 1000 m": "buffer_1000m",
    "Microbacias interceptadas": "microbacia",
    "Setores censitários intersectados": "setores_censitarios",
}

FISICO_VIEW_POR_LIMITE = {
    "area_interesse": "resultados.vw_relatorio_fisico_biotico_area_interesse",
    "buffer_1000m": "resultados.vw_relatorio_fisico_biotico_buffer_1000m",
    "microbacia": "resultados.vw_relatorio_fisico_biotico_microbacias",
}

TEMAS_FISICO_BIOTICOS = (
    "geologia",
    "geomorfologia",
    "hidrogeologia",
    "pedologia",
    "vegetacao",
)


def executar_select_df(
    conn: Any,
    sql: str,
    params: tuple[Any, ...] | list[Any] | None = None,
) -> pd.DataFrame:
    try:
        return pd.read_sql_query(sql, conn, params=tuple(params or ()))
    except Exception as exc:  # pragma: no cover - exibido na interface
        st.warning(f"Não foi possível consultar dados: {exc}")
        return pd.DataFrame()


def view_existe_conn(conn: Any, view_name: str) -> bool:
    data = executar_select_df(
        conn,
        "SELECT to_regclass(%s) AS objeto;",
        (view_name,),
    )
    if data.empty:
        return False
    return pd.notna(data.iloc[0].get("objeto"))


def numero(valor: Any) -> float | None:
    if valor is None or pd.isna(valor):
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def formatar_numero(valor: Any, casas: int = 2) -> str:
    valor_num = numero(valor)
    if valor_num is None:
        return "-"
    return f"{valor_num:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_inteiro(valor: Any) -> str:
    valor_num = numero(valor)
    if valor_num is None:
        return "-"
    return f"{valor_num:,.0f}".replace(",", ".")


def percentual_seguro(numerador: Any, denominador: Any) -> float | None:
    num = numero(numerador)
    den = numero(denominador)
    if num is None or den in (None, 0):
        return None
    return (num / den) * 100.0


def preparar_numericos(data: pd.DataFrame, colunas: tuple[str, ...]) -> pd.DataFrame:
    resultado = data.copy()
    for coluna in colunas:
        if coluna in resultado.columns:
            resultado[coluna] = pd.to_numeric(resultado[coluna], errors="coerce")
    return resultado


def carregar_microbacias_resumo(
    conn: Any,
    execucao_id: int,
    projeto_id: int,
    area_interesse_id: int,
) -> pd.DataFrame:
    view_name = "resultados.vw_relatorio_fisico_biotico_microbacias"
    if not view_existe_conn(conn, view_name):
        return pd.DataFrame()
    return executar_select_df(
        conn,
        f"""
        SELECT DISTINCT
            fb.cd_micro::text AS cd_micro,
            fb.nm_micro::text AS nm_micro
        FROM {view_name} AS fb
        WHERE fb.execucao_id = %s
          AND fb.projeto_id = %s
          AND fb.area_interesse_id = %s
        ORDER BY fb.nm_micro, fb.cd_micro;
        """,
        (execucao_id, projeto_id, area_interesse_id),
    )


def carregar_fisico_biotico_resumo(
    conn: Any,
    limite_analise: str,
    execucao_id: int,
    projeto_id: int,
    area_interesse_id: int,
    cd_micro: str | None = None,
) -> pd.DataFrame:
    if limite_analise == "setores_censitarios":
        return pd.DataFrame()

    view_name = FISICO_VIEW_POR_LIMITE[limite_analise]
    if not view_existe_conn(conn, view_name):
        st.info(f"View indisponível: {view_name}")
        return pd.DataFrame()

    if limite_analise == "microbacia":
        filtro_micro = "AND fb.cd_micro::text = %s" if cd_micro else ""
        params: list[Any] = [execucao_id, projeto_id, area_interesse_id]
        if cd_micro:
            params.append(cd_micro)
        return executar_select_df(
            conn,
            f"""
            SELECT
                'Microbacias interceptadas'::text AS limite_analise,
                fb.cd_micro::text AS microbacia_codigo,
                fb.nm_micro::text AS microbacia,
                fb.tema,
                fb.valor_principal,
                fb.area_ha,
                fb.percentual_unidade_analise
            FROM {view_name} AS fb
            WHERE fb.execucao_id = %s
              AND fb.projeto_id = %s
              AND fb.area_interesse_id = %s
              {filtro_micro}
            ORDER BY fb.nm_micro, fb.tema, fb.area_ha DESC NULLS LAST;
            """,
            tuple(params),
        )

    limite_rotulo = "Área de interesse" if limite_analise == "area_interesse" else "Buffer de 1000 m"
    return executar_select_df(
        conn,
        f"""
        SELECT
            %s::text AS limite_analise,
            NULL::text AS microbacia_codigo,
            NULL::text AS microbacia,
            fb.tema,
            fb.valor_principal,
            fb.area_ha,
            fb.percentual_unidade_analise
        FROM {view_name} AS fb
        WHERE fb.execucao_id = %s
          AND fb.projeto_id = %s
          AND fb.area_interesse_id = %s
        ORDER BY fb.tema, fb.area_ha DESC NULLS LAST;
        """,
        (limite_rotulo, execucao_id, projeto_id, area_interesse_id),
    )


def montar_resumo_fisico_biotico(classes: pd.DataFrame) -> pd.DataFrame:
    if classes.empty:
        return pd.DataFrame(
            columns=(
                "tema",
                "total_classes",
                "area_total_ha",
                "classe_dominante",
                "area_classe_dominante_ha",
                "percentual_dominante",
            )
        )
    data = preparar_numericos(classes, ("area_ha", "percentual_unidade_analise"))
    linhas = []
    for tema, grupo in data.groupby("tema", dropna=False):
        grupo_ordenado = grupo.sort_values("area_ha", ascending=False, na_position="last")
        dominante = grupo_ordenado.iloc[0]
        linhas.append(
            {
                "tema": tema,
                "total_classes": int(grupo["valor_principal"].nunique(dropna=True)),
                "area_total_ha": grupo["area_ha"].sum(skipna=True),
                "classe_dominante": dominante.get("valor_principal"),
                "area_classe_dominante_ha": dominante.get("area_ha"),
                "percentual_dominante": dominante.get("percentual_unidade_analise"),
            }
        )
    return pd.DataFrame(linhas).sort_values("tema")


def carregar_socio_total_setores(
    conn: Any,
    execucao_id: int,
    projeto_id: int,
    area_interesse_id: int,
) -> pd.DataFrame:
    view_name = "resultados.vw_relatorio_socio_total_setores"
    if not view_existe_conn(conn, view_name):
        st.info(f"View indisponível: {view_name}")
        return pd.DataFrame()
    return executar_select_df(
        conn,
        f"""
        SELECT
            st.execucao_id,
            st.projeto_id,
            st.area_interesse_id,
            st.numero_setores_intersectados,
            st.setores_com_dados_completos,
            st.setores_com_dados_parciais,
            st.populacao_total_setores,
            st.total_domicilios_setores,
            st.domicilios_particulares_permanentes_ocupados_setores,
            st.renda_media_responsavel_ponderada_responsaveis,
            st.renda_media_responsavel_media_setores,
            st.renda_mediana_responsavel_media_setores
        FROM {view_name} AS st
        WHERE st.execucao_id = %s
          AND st.projeto_id = %s
          AND st.area_interesse_id = %s;
        """,
        (execucao_id, projeto_id, area_interesse_id),
    )


def carregar_socio_contexto_setores(
    conn: Any,
    execucao_id: int,
    projeto_id: int,
    area_interesse_id: int,
) -> pd.DataFrame:
    view_name = "resultados.vw_relatorio_socio_contexto_setores"
    if not view_existe_conn(conn, view_name):
        return pd.DataFrame()
    return executar_select_df(
        conn,
        f"""
        SELECT
            sc.cd_setor,
            sc.percentual_area_interesse,
            sc.populacao_total_setor,
            sc.total_domicilios_setor,
            sc.domicilios_particulares_permanentes_ocupados_setor,
            sc.renda_media_responsavel_setor,
            sc.renda_mediana_responsavel_setor,
            sc.status_dados_setor
        FROM {view_name} AS sc
        WHERE sc.execucao_id = %s
          AND sc.projeto_id = %s
          AND sc.area_interesse_id = %s
        ORDER BY sc.percentual_area_interesse DESC NULLS LAST;
        """,
        (execucao_id, projeto_id, area_interesse_id),
    )


def verificar_fonte_demografica(conn: Any) -> pd.DataFrame:
    return executar_select_df(
        conn,
        """
        SELECT
            c.table_schema,
            c.table_name,
            c.column_name
        FROM information_schema.columns AS c
        WHERE c.table_schema = 'resultados'
          AND (
                lower(c.column_name) LIKE '%idade%'
             OR lower(c.column_name) LIKE '%faixa%'
             OR lower(c.column_name) LIKE '%sexo%'
             OR lower(c.column_name) LIKE '%homem%'
             OR lower(c.column_name) LIKE '%homens%'
             OR lower(c.column_name) LIKE '%mulher%'
             OR lower(c.column_name) LIKE '%mulheres%'
             OR lower(c.column_name) LIKE '%grupo_etario%'
          )
        ORDER BY c.table_schema, c.table_name, c.column_name;
        """,
    )


def carregar_hidrografia_resumo(
    conn: Any,
    limite_analise: str,
    execucao_id: int,
    projeto_id: int,
    area_interesse_id: int,
    cd_micro: str | None = None,
) -> pd.DataFrame:
    if limite_analise == "setores_censitarios":
        return pd.DataFrame()

    view_name = "resultados.vw_hidrografia_resumo"
    if not view_existe_conn(conn, view_name):
        st.info("Não há dados de hidrografia para esta execução.")
        return pd.DataFrame()

    unidade_analise = {
        "area_interesse": "area_interesse",
        "buffer_1000m": "buffer_1000m",
        "microbacia": "microbacia",
    }[limite_analise]
    filtro_micro = "AND h.cd_micro::text = %s" if limite_analise == "microbacia" and cd_micro else ""
    params: list[Any] = [execucao_id, projeto_id, area_interesse_id, unidade_analise]
    if filtro_micro:
        params.append(str(cd_micro))

    return executar_select_df(
        conn,
        f"""
        SELECT
            h.unidade_analise,
            h.cd_micro,
            h.nm_micro,
            h.nm_rio_pri,
            h.nuordemcda,
            h.nunivotcda,
            h.quantidade_trechos,
            h.comprimento_total_m,
            h.comprimento_total_km
        FROM {view_name} AS h
        WHERE h.execucao_id = %s
          AND h.projeto_id = %s
          AND h.area_interesse_id = %s
          AND h.unidade_analise = %s
          {filtro_micro}
        ORDER BY h.nm_micro, h.nuordemcda, h.nunivotcda;
        """,
        tuple(params),
    )

def pagina_inicio() -> None:
    st.title(APP_TITLE)
    st.write(
        "Interface inicial para selecionar projetos, configurar diagnóstico, "
        "montar comandos de processamento e visualizar resultados do MVP."
    )

    status = testar_conexao()
    col1, col2, col3 = st.columns(3)
    col1.metric("Conexão", "OK" if status["ok"] else "Indisponível")
    col2.metric("Banco", status.get("database") or "-")
    col3.metric("Projetos", status.get("total_projetos") or 0)

    if status["ok"]:
        st.caption(f"Usuário do banco: {status.get('usuario') or '-'}")
    else:
        st.error(status.get("erro") or "Falha ao testar conexão.")

    exibir_resultado_query("Últimas execuções", carregar_ultimas_execucoes())


def pagina_projetos_areas() -> None:
    st.title("Projetos e áreas")
    st.caption("Esta versão apenas lista registros existentes. Cadastro via formulário fica para etapa futura.")

    projetos = carregar_projetos()
    if not projetos.ok:
        st.error(projetos.erro)
        return
    if projetos.data.empty:
        st.info("Nenhum projeto cadastrado encontrado.")
        return

    labels = [label_registro(row, "Projeto") for _, row in projetos.data.iterrows()]
    projeto_label = st.selectbox("Projeto", labels)
    projeto_idx = labels.index(projeto_label)
    projeto_row = projetos.data.iloc[projeto_idx]
    st.session_state["projeto_id"] = int(projeto_row["id"])

    st.dataframe(projetos.data.iloc[[projeto_idx]], use_container_width=True)

    areas = carregar_areas(int(st.session_state["projeto_id"]))
    if not areas.ok:
        st.error(areas.erro)
        return
    if areas.data.empty:
        st.info("Nenhuma área de interesse vinculada a este projeto.")
        st.session_state["area_interesse_id"] = None
        return

    area_labels = [label_registro(row, "Área") for _, row in areas.data.iterrows()]
    area_label = st.selectbox("Área de interesse", area_labels)
    area_idx = area_labels.index(area_label)
    area_row = areas.data.iloc[area_idx]
    st.session_state["area_interesse_id"] = int(area_row["id"])

    campos_area = ["id", "nome", "tipo", "area_ha", "srid_origem"]
    st.dataframe(areas.data.loc[[area_idx], campos_area], use_container_width=True)


def pagina_configurar() -> None:
    st.title("Configurar diagnóstico")
    st.info(
        "Nesta versão, o MVP padrão processa os temas físico-bióticos e "
        "socioeconômicos já implementados. A hidrografia ANA é opcional e "
        "adiciona o parâmetro --incluir-hidrografia."
    )

    atual = parametros().copy()
    with st.form("form_configurar_diagnostico"):
        st.subheader("Análises ambientais")
        for analise in ANALISES_AMBIENTAIS:
            atual[analise] = st.checkbox(
                ANALISES_ROTULOS[analise],
                value=bool(atual.get(analise, False)),
            )

        st.subheader("Análises socioeconômicas")
        atual["socioeconomia"] = st.checkbox(
            ANALISES_ROTULOS["socioeconomia"],
            value=bool(atual.get("socioeconomia", True)),
        )

        st.subheader("Unidades espaciais")
        for unidade in UNIDADES_ESPACIAIS:
            atual[unidade] = st.checkbox(
                UNIDADES_ROTULOS[unidade],
                value=bool(atual.get(unidade, True)),
            )

        st.subheader("Buffer")
        atual["usar_buffer"] = st.checkbox(
            "Usar buffer",
            value=bool(atual.get("usar_buffer", True)),
        )
        atual["distancia_buffer_m"] = st.number_input(
            "Distância do buffer (m)",
            min_value=0,
            value=int(atual.get("distancia_buffer_m", 1000)),
            step=100,
        )

        submitted = st.form_submit_button("Salvar configuração")

    if submitted:
        st.session_state["parametros_diagnostico"] = atual
        st.success("Configuração salva na sessão da interface.")

    st.subheader("Configuração atual")
    st.json(st.session_state["parametros_diagnostico"])


def selecionar_execucao_contexto(label: str) -> str:
    projeto_id = st.session_state.get("projeto_id")
    area_id = st.session_state.get("area_interesse_id")
    execucoes = carregar_execucoes_contexto(projeto_id, area_id)
    selecionada = ""

    if execucoes.ok and not execucoes.data.empty:
        labels = ["Informar manualmente"] + [label_execucao(row) for _, row in execucoes.data.iterrows()]
        escolha = st.selectbox(label, labels)
        if escolha != "Informar manualmente":
            idx = labels.index(escolha) - 1
            selecionada = str(execucoes.data.iloc[idx]["id"])
    elif not execucoes.ok:
        st.warning(execucoes.erro or "Não foi possível listar execuções.")

    valor_atual = selecionada or str(st.session_state.get("execucao_id") or "")
    valor = st.text_input("Execução ID manual", value=valor_atual)
    st.session_state["execucao_id"] = valor.strip()
    return st.session_state["execucao_id"]


def pagina_executar() -> None:
    st.title("Executar processamento")
    st.warning(
        "Nesta primeira versão, a interface monta comandos para revisão. "
        "Ela não executa scripts automaticamente."
    )

    col1, col2 = st.columns(2)
    with col1:
        projeto_id = st.number_input(
            "Projeto ID",
            min_value=1,
            value=int(st.session_state.get("projeto_id") or 1),
        )
        area_id = st.number_input(
            "Área de interesse ID",
            min_value=1,
            value=int(st.session_state.get("area_interesse_id") or 1),
        )
        st.session_state["projeto_id"] = int(projeto_id)
        st.session_state["area_interesse_id"] = int(area_id)
        st.session_state["usuario_execucao"] = st.text_input(
            "Usuário",
            value=str(st.session_state.get("usuario_execucao") or "Paulo"),
        )
    with col2:
        selecionar_execucao_contexto("Execução ID para exportações")
        st.session_state["projeto_sig_dir"] = st.text_input(
            "Pasta SIG do projeto",
            value=str(st.session_state.get("projeto_sig_dir") or ""),
        ).strip()

    st.subheader("Parâmetros selecionados")
    st.json(
        {
            "projeto_id": st.session_state.get("projeto_id"),
            "area_interesse_id": st.session_state.get("area_interesse_id"),
            "execucao_id": st.session_state.get("execucao_id"),
            "usuario": st.session_state.get("usuario_execucao"),
            "projeto_sig_dir": st.session_state.get("projeto_sig_dir"),
            "parametros_diagnostico": st.session_state.get("parametros_diagnostico"),
        }
    )

    comandos = {
        "Validar configuração": (comando_validar_configuracao(), None),
        "Rodar MVP": (comando_mvp(), None),
        "Exportar planilhas": comando_exportar_planilhas(),
        "Gerar gráficos": comando_gerar_graficos(),
        "Exportar GPKG": comando_exportar_gpkg(),
    }

    for titulo, (comando, erro) in comandos.items():
        if st.button(titulo):
            if erro:
                st.warning(erro)
            elif comando:
                st.code(comando, language="powershell")
                if titulo == "Exportar GPKG":
                    st.info("A exportação GPKG depende do ogr2ogr e do ambiente QGIS/GDAL configurado no PowerShell.")
            else:
                st.warning("Selecione projeto e área de interesse.")


def pagina_resultados() -> None:
    st.title("Resultados")
    col1, col2 = st.columns(2)
    with col1:
        projeto_id = st.number_input(
            "Projeto ID",
            min_value=1,
            value=int(st.session_state.get("projeto_id") or 1),
        )
    with col2:
        area_id = st.number_input(
            "Área de interesse ID",
            min_value=1,
            value=int(st.session_state.get("area_interesse_id") or 1),
        )
    st.session_state["projeto_id"] = int(projeto_id)
    st.session_state["area_interesse_id"] = int(area_id)

    execucao_id = selecionar_execucao_contexto("Execução para consultar resultados")
    if not str(execucao_id).strip():
        st.info("Informe ou selecione uma execução para consultar resultados.")
        return
    try:
        execucao_id_int = int(str(execucao_id).strip())
    except ValueError:
        st.warning("Informe um execucao_id numérico.")
        return

    consultas = (
        ("Síntese executiva", "resultados.vw_relatorio_sintese_executiva", None),
        ("Socioeconômico", "resultados.vw_relatorio_socio_total_setores", None),
        ("Físico-biótico", "resultados.vw_fisico_biotico_sintese_unidade_tema", None),
        (
            "Hidrografia",
            "resultados.vw_hidrografia_resumo",
            "Não há registros de hidrografia para esta execução.",
        ),
    )

    for titulo, view_name, vazio in consultas:
        if view_existe(view_name):
            exibir_resultado_query(
                titulo,
                carregar_resultado_view(view_name, execucao_id_int, int(projeto_id), int(area_id)),
                vazio=vazio,
            )
        else:
            st.warning(f"View indisponível: {view_name}")


def pagina_mapa() -> None:
    st.title("Mapa")
    st.caption(
        "Visualização rápida em Folium. As geometrias são transformadas para EPSG:4326 "
        "apenas para exibição; o processamento oficial permanece no PostGIS."
    )

    if folium is None or st_folium is None:
        st.warning("Instale as dependências: python -m pip install folium streamlit-folium")
        return

    parametros_mapa = st.session_state.get("parametros_diagnostico", {})
    distancia_padrao = int(parametros_mapa.get("distancia_buffer_m") or 1000)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        projeto_id = st.number_input(
            "Projeto ID",
            min_value=1,
            value=int(st.session_state.get("projeto_id") or 1),
            key="mapa_projeto_id",
        )
    with col2:
        area_interesse_id = st.number_input(
            "Área de interesse ID",
            min_value=1,
            value=int(st.session_state.get("area_interesse_id") or 1),
            key="mapa_area_interesse_id",
        )
    with col3:
        execucao_id_txt = st.text_input(
            "Execução ID",
            value=str(st.session_state.get("execucao_id") or ""),
            key="mapa_execucao_id",
        ).strip()
    with col4:
        distancia_buffer_m = st.number_input(
            "Buffer (m)",
            min_value=0,
            value=distancia_padrao,
            step=100,
            key="mapa_distancia_buffer_m",
        )

    st.session_state["projeto_id"] = int(projeto_id)
    st.session_state["area_interesse_id"] = int(area_interesse_id)
    st.session_state["execucao_id"] = execucao_id_txt
    st.session_state["projeto_sig_dir"] = st.text_input(
        "Pasta SIG do projeto",
        value=str(st.session_state.get("projeto_sig_dir") or ""),
        key="mapa_projeto_sig_dir",
    ).strip()

    st.subheader("Camadas")
    c1, c2, c3, c4, c5 = st.columns(5)
    mostrar_area = c1.checkbox("Área de interesse", value=True)
    mostrar_buffer = c2.checkbox("Buffer", value=bool(parametros_mapa.get("usar_buffer", True)))
    mostrar_microbacias = c3.checkbox("Microbacias", value=True)
    mostrar_setores = c4.checkbox("Setores censitários", value=True)
    mostrar_hidrografia = c5.checkbox("Hidrografia", value=bool(parametros_mapa.get("hidrografia_ana", False)))

    execucao_id_int: int | None = None
    if execucao_id_txt:
        try:
            execucao_id_int = int(execucao_id_txt)
        except ValueError:
            st.warning("Informe um execucao_id numérico para carregar setores e hidrografia.")

    mapa = folium.Map(location=[-27.6, -48.5], zoom_start=12, tiles="OpenStreetMap")
    camada_area = None

    try:
        with get_connection() as conn:
            conn.set_session(readonly=True, autocommit=True)

            if mostrar_area:
                area_geojson = carregar_geojson_area_interesse(conn, int(projeto_id), int(area_interesse_id))
                camada_area = adicionar_geojson(
                    mapa,
                    area_geojson,
                    "Área de interesse",
                    estilo_area_interesse,
                )
                if camada_area is None:
                    st.warning("Área de interesse não encontrada.")

            if mostrar_buffer:
                buffer_geojson = carregar_geojson_buffer(
                    conn,
                    int(projeto_id),
                    int(area_interesse_id),
                    int(distancia_buffer_m),
                )
                camada_buffer = adicionar_geojson(
                    mapa,
                    buffer_geojson,
                    f"Buffer {int(distancia_buffer_m)} m",
                    estilo_buffer,
                )
                if camada_buffer is None:
                    st.warning("Buffer não encontrado para a área de interesse.")

            if mostrar_microbacias:
                microbacias_geojson = carregar_geojson_microbacias(conn, int(projeto_id), int(area_interesse_id))
                camada_microbacias = adicionar_geojson(
                    mapa,
                    microbacias_geojson,
                    "Microbacias interceptadas",
                    estilo_microbacias,
                )
                if camada_microbacias is None:
                    st.warning("Nenhuma microbacia encontrada.")

            if mostrar_setores:
                if execucao_id_int is None:
                    st.info("Informe uma execução para carregar setores censitários.")
                else:
                    setores_geojson = carregar_geojson_setores(
                        conn,
                        execucao_id_int,
                        int(projeto_id),
                        int(area_interesse_id),
                    )
                    camada_setores = adicionar_geojson(
                        mapa,
                        setores_geojson,
                        "Setores censitários",
                        estilo_setores,
                    )
                    if camada_setores is None:
                        st.warning("Nenhum setor censitário encontrado para esta execução.")
                    else:
                        st.caption(
                            "Setores censitários usam a geometria disponível em "
                            "resultados.setores_intersectados."
                        )

            if mostrar_hidrografia:
                if execucao_id_int is None:
                    st.info("Informe uma execução para carregar hidrografia.")
                else:
                    hidrografia_geojson = carregar_geojson_hidrografia(
                        conn,
                        execucao_id_int,
                        int(projeto_id),
                        int(area_interesse_id),
                    )
                    camada_hidrografia = adicionar_geojson(
                        mapa,
                        hidrografia_geojson,
                        "Hidrografia ANA",
                        estilo_hidrografia,
                    )
                    if camada_hidrografia is None:
                        st.warning("Nenhum registro de hidrografia encontrado para esta execução.")
    except Exception as exc:  # pragma: no cover - exibido na interface
        st.error(f"Não foi possível carregar as camadas do mapa: {exc}")
        return

    if camada_area is not None:
        try:
            mapa.fit_bounds(camada_area.get_bounds())
        except Exception:
            pass

    folium.LayerControl().add_to(mapa)
    st_folium(mapa, width=None, height=650)

def exibir_fisico_biotico_resumo(classes_fb: pd.DataFrame, limite_analise: str) -> None:
    st.subheader("Físico-biótico")
    if limite_analise == "setores_censitarios":
        st.info("Resumo físico-biótico por setor censitário ainda não disponível nesta versão.")
        return
    if classes_fb.empty:
        st.info("Nenhum dado físico-biótico encontrado para os filtros selecionados.")
        return

    classes_fb = preparar_numericos(classes_fb, ("area_ha", "percentual_unidade_analise"))
    classes_fb["valor_principal"] = classes_fb["valor_principal"].fillna("Sem classificação informada")
    resumo = montar_resumo_fisico_biotico(classes_fb)

    col1, col2, col3 = st.columns(3)
    col1.metric("Temas", formatar_inteiro(resumo["tema"].nunique()))
    col2.metric("Classes", formatar_inteiro(resumo["total_classes"].sum()))
    col3.metric("Maior dominante", f"{formatar_numero(resumo['percentual_dominante'].max(), 2)}%")

    st.dataframe(resumo, use_container_width=True)
    st.dataframe(
        classes_fb[
            [
                "limite_analise",
                "microbacia",
                "tema",
                "valor_principal",
                "area_ha",
                "percentual_unidade_analise",
            ]
        ],
        use_container_width=True,
    )

    fig_classes = px.bar(
        resumo.sort_values("total_classes"),
        x="total_classes",
        y="tema",
        orientation="h",
        title="Classes por tema",
    )
    st.plotly_chart(fig_classes, use_container_width=True)

    fig_dominante = px.bar(
        resumo.sort_values("percentual_dominante"),
        x="percentual_dominante",
        y="tema",
        orientation="h",
        title="Percentual dominante por tema",
    )
    st.plotly_chart(fig_dominante, use_container_width=True)

    fig_area = px.bar(
        resumo.sort_values("area_total_ha"),
        x="area_total_ha",
        y="tema",
        orientation="h",
        title="Área total por tema (ha)",
    )
    st.plotly_chart(fig_area, use_container_width=True)


def exibir_socioeconomico_resumo(total_socio: pd.DataFrame, contexto_socio: pd.DataFrame) -> None:
    st.subheader("Socioeconômico")
    st.info("Os dados socioeconômicos são apresentados para os setores censitários intersectados pela área de interesse.")
    if total_socio.empty:
        st.info("Nenhum dado socioeconômico encontrado para os filtros selecionados.")
        return

    total_socio = preparar_numericos(
        total_socio,
        (
            "numero_setores_intersectados",
            "setores_com_dados_completos",
            "setores_com_dados_parciais",
            "populacao_total_setores",
            "total_domicilios_setores",
            "domicilios_particulares_permanentes_ocupados_setores",
            "renda_media_responsavel_ponderada_responsaveis",
        ),
    )
    linha = total_socio.iloc[0]
    perc_ocupados = percentual_seguro(
        linha.get("domicilios_particulares_permanentes_ocupados_setores"),
        linha.get("total_domicilios_setores"),
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("População total", formatar_inteiro(linha.get("populacao_total_setores")))
    col2.metric("Domicílios totais", formatar_inteiro(linha.get("total_domicilios_setores")))
    col3.metric("Domicílios ocupados", f"{formatar_numero(perc_ocupados, 2)}%")
    col4.metric("Renda média ponderada", formatar_numero(linha.get("renda_media_responsavel_ponderada_responsaveis"), 2))

    col5, col6, col7 = st.columns(3)
    col5.metric("Setores", formatar_inteiro(linha.get("numero_setores_intersectados")))
    col6.metric("Dados completos", formatar_inteiro(linha.get("setores_com_dados_completos")))
    col7.metric("Dados parciais", formatar_inteiro(linha.get("setores_com_dados_parciais")))

    st.dataframe(total_socio, use_container_width=True)
    if not contexto_socio.empty:
        st.dataframe(contexto_socio, use_container_width=True)
        if "status_dados_setor" in contexto_socio.columns:
            status = contexto_socio["status_dados_setor"].value_counts(dropna=False).reset_index()
            status.columns = ["status_dados_setor", "quantidade"]
            fig_status = px.bar(
                status,
                x="status_dados_setor",
                y="quantidade",
                title="Setores por status de dados",
            )
            st.plotly_chart(fig_status, use_container_width=True)

    st.markdown("#### Pirâmide etária")
    st.info("Dados de pirâmide etária ainda não disponíveis para esta execução.")

    st.markdown("#### Estrutura por sexo")
    st.info("Dados de estrutura por sexo ainda não disponíveis para esta execução.")


def exibir_hidrografia_resumo(hidrografia: pd.DataFrame, limite_analise: str) -> None:
    st.subheader("Hidrografia")
    if limite_analise == "setores_censitarios":
        st.info("Hidrografia por setor censitário ainda não disponível nesta versão.")
        return
    if hidrografia.empty:
        st.info("Não há dados de hidrografia para esta execução.")
        return

    hidrografia = preparar_numericos(
        hidrografia,
        ("quantidade_trechos", "comprimento_total_m", "comprimento_total_km"),
    )
    quantidade_trechos = hidrografia["quantidade_trechos"].sum(skipna=True)
    comprimento_total_km = hidrografia["comprimento_total_km"].sum(skipna=True)

    col1, col2 = st.columns(2)
    col1.metric("Trechos", formatar_inteiro(quantidade_trechos))
    col2.metric("Comprimento total km", formatar_numero(comprimento_total_km, 3))

    st.dataframe(hidrografia, use_container_width=True)

    por_micro = (
        hidrografia.groupby(["cd_micro", "nm_micro"], dropna=False, as_index=False)["comprimento_total_km"]
        .sum()
        .sort_values("comprimento_total_km", ascending=False)
    )
    if not por_micro.empty:
        por_micro["microbacia"] = por_micro["nm_micro"].fillna(por_micro["cd_micro"].fillna("Sem microbacia"))
        fig_micro = px.bar(
            por_micro,
            x="comprimento_total_km",
            y="microbacia",
            orientation="h",
            title="Comprimento total por microbacia (km)",
        )
        st.plotly_chart(fig_micro, use_container_width=True)

    por_ordem = (
        hidrografia.groupby("nuordemcda", dropna=False, as_index=False)
        .agg(
            comprimento_total_km=("comprimento_total_km", "sum"),
            quantidade_trechos=("quantidade_trechos", "sum"),
        )
        .sort_values("nuordemcda")
    )
    if not por_ordem.empty:
        fig_comprimento = px.bar(
            por_ordem,
            x="nuordemcda",
            y="comprimento_total_km",
            title="Comprimento por ordem do curso d'água (km)",
        )
        st.plotly_chart(fig_comprimento, use_container_width=True)
        fig_quantidade = px.bar(
            por_ordem,
            x="nuordemcda",
            y="quantidade_trechos",
            title="Quantidade de trechos por ordem do curso d'água",
        )
        st.plotly_chart(fig_quantidade, use_container_width=True)


def pagina_resumo_estatistico() -> None:
    st.title("Resumo estatístico")

    st.subheader("Filtros")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        projeto_id = st.number_input(
            "Projeto ID",
            min_value=1,
            value=int(st.session_state.get("projeto_id") or 1),
            key="resumo_projeto_id",
        )
    with col2:
        area_interesse_id = st.number_input(
            "Área de interesse ID",
            min_value=1,
            value=int(st.session_state.get("area_interesse_id") or 1),
            key="resumo_area_interesse_id",
        )
    with col3:
        execucao_id_txt = st.text_input(
            "Execução ID",
            value=str(st.session_state.get("execucao_id") or ""),
            key="resumo_execucao_id",
        ).strip()
    with col4:
        limite_label = st.selectbox(
            "Limite de análise",
            list(LIMITES_ANALISE_RESUMO.keys()),
            key="resumo_limite_analise",
        )

    st.session_state["projeto_id"] = int(projeto_id)
    st.session_state["area_interesse_id"] = int(area_interesse_id)
    st.session_state["execucao_id"] = execucao_id_txt

    if not execucao_id_txt:
        st.info("Informe uma execução para consultar o resumo estatístico.")
        return
    try:
        execucao_id = int(execucao_id_txt)
    except ValueError:
        st.warning("Informe um execucao_id numérico.")
        return

    limite_analise = LIMITES_ANALISE_RESUMO[limite_label]
    cd_micro_selecionada: str | None = None
    classes_fb = pd.DataFrame()
    total_socio = pd.DataFrame()
    contexto_socio = pd.DataFrame()
    hidrografia = pd.DataFrame()

    try:
        with get_connection() as conn:
            conn.set_session(readonly=True, autocommit=True)

            if limite_analise == "microbacia":
                microbacias = carregar_microbacias_resumo(
                    conn,
                    execucao_id,
                    int(projeto_id),
                    int(area_interesse_id),
                )
                if microbacias.empty:
                    st.info("Nenhuma microbacia encontrada para esta execução.")
                else:
                    opcoes_micro = ["Todas as microbacias"]
                    for _, row in microbacias.iterrows():
                        nome_micro = row.get("nm_micro") if pd.notna(row.get("nm_micro")) else "Sem nome"
                        opcoes_micro.append(f"{row.get('cd_micro')} - {nome_micro}")
                    escolha_micro = st.selectbox("Microbacia", opcoes_micro, key="resumo_microbacia")
                    if escolha_micro != "Todas as microbacias":
                        cd_micro_selecionada = escolha_micro.split(" - ", 1)[0]

            if limite_analise == "setores_censitarios":
                st.info("O limite por setor censitário usa somente o bloco socioeconômico nesta versão.")
            else:
                classes_fb = carregar_fisico_biotico_resumo(
                    conn,
                    limite_analise,
                    execucao_id,
                    int(projeto_id),
                    int(area_interesse_id),
                    cd_micro_selecionada,
                )

            total_socio = carregar_socio_total_setores(
                conn,
                execucao_id,
                int(projeto_id),
                int(area_interesse_id),
            )
            contexto_socio = carregar_socio_contexto_setores(
                conn,
                execucao_id,
                int(projeto_id),
                int(area_interesse_id),
            )
            fontes_demograficas = verificar_fonte_demografica(conn)
            if not fontes_demograficas.empty:
                st.caption(
                    "Foram encontradas colunas com termos demográficos em views do schema resultados, "
                    "mas ainda não há mapeamento validado para pirâmide etária ou estrutura por sexo."
                )

            hidrografia = carregar_hidrografia_resumo(
                conn,
                limite_analise,
                execucao_id,
                int(projeto_id),
                int(area_interesse_id),
                cd_micro_selecionada,
            )
    except Exception as exc:  # pragma: no cover - exibido na interface
        st.error(f"Não foi possível carregar o resumo estatístico: {exc}")
        return

    exibir_fisico_biotico_resumo(classes_fb, limite_analise)
    exibir_socioeconomico_resumo(total_socio, contexto_socio)
    exibir_hidrografia_resumo(hidrografia, limite_analise)

def main() -> None:
    configurar_pagina()
    inicializar_estado()

    st.sidebar.title("EA2S SIG")
    pagina = st.sidebar.radio("Navegação", PAGE_OPTIONS)
    st.sidebar.caption("Interface inicial de leitura e montagem de comandos.")

    if pagina == "Início":
        pagina_inicio()
    elif pagina == "Projetos e áreas":
        pagina_projetos_areas()
    elif pagina == "Configurar diagnóstico":
        pagina_configurar()
    elif pagina == "Executar processamento":
        pagina_executar()
    elif pagina == "Resultados":
        pagina_resultados()
    elif pagina == "Mapa":
        pagina_mapa()
    elif pagina == "Resumo estatístico":
        pagina_resumo_estatistico()


if __name__ == "__main__":
    main()
