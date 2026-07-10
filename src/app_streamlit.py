"""Interface Streamlit inicial do MVP EA2S SIG.

Este arquivo contem a interface Streamlit do WebGIS EA2S SIG.
Ele organiza o fluxo de projeto, composicao de diagnostico, dashboard,
mapas, exportacoes e administracao da aplicacao.

O processamento pesado continua no PostGIS e nos scripts Python auxiliares.
A interface apenas consulta dados, monta comandos e, em fluxos confirmados,
grava cadastros operacionais de projeto e area de interesse.
"""

from __future__ import annotations

# Bibliotecas padrao do Python usadas para datas, caminhos, arquivos temporarios
# e manipulacao simples de texto.
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import hashlib
import json
import os
import re
import tempfile
import unicodedata
import zipfile

# Bibliotecas para dados tabulares e geoespaciais.
import geopandas as gpd
import pandas as pd

# Bibliotecas para graficos interativos usados no dashboard e na administracao.
import plotly.express as px
import plotly.graph_objects as go

# Biblioteca principal da interface web.
import streamlit as st

# Bibliotecas para mapas web. Folium usa Leaflet e trabalha melhor com EPSG:4326
# na visualizacao, enquanto os calculos oficiais continuam no SRID operacional.
try:
    import folium
    from streamlit_folium import st_folium
except ImportError:  # pragma: no cover - exibido na interface quando faltar dependencia
    folium = None
    st_folium = None

# Binary permite enviar geometria em WKB para o PostGIS no cadastro da area.
from psycopg2 import Binary

# Modulo interno que centraliza a conexao com o banco configurado no .env.
from db import get_connection
from importacao_staging import (
    copiar_arquivo_original_para_persistente,
    gerar_nome_tabela_staging,
    importar_inventario_para_staging,
    localizar_arquivo_original,
)
from importacao_oficial import (
    diagnosticar_inventario_para_importacao_oficial,
    gerar_nome_tabela_oficial,
    importar_inventario_para_schema_oficial,
    testar_correcao_inventario,
)

# Titulo exibido na pagina inicial e no navegador.
APP_TITLE = "EA2S SIG | WebGIS Socioambiental"

# Modo atual da aplicacao. Hoje a interface e interna; futuramente pode haver
# separacao entre modo publico somente leitura e modo interno administrativo.
MODO_APP = "interno"

# Modos previstos para evolucao:
# modo_publico: somente leitura, mapas e indicadores liberados, sem upload e sem exportacao sensivel.
# modo_interno: uso EA2S, upload, processamento, exportacoes e administracao.
PAGE_OPTIONS = (
    "Início",
    "Compor diagnóstico",
    "Dashboard",
    "Exportações",
    "Banco de dados geográficos",
    "Administração",
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


# Pequena estrutura para padronizar respostas de consulta: sucesso, DataFrame e erro.
@dataclass(frozen=True)
class QueryResult:
    ok: bool
    data: pd.DataFrame
    erro: str | None = None


def configurar_pagina() -> None:
    """Configura o Streamlit para usar layout amplo em todo o WebGIS."""
    st.set_page_config(
        page_title="EA2S SIG",
        layout="wide",
    )


def parametros_padrao() -> dict[str, Any]:
    """Define as camadas e limites marcados quando uma nova sessao inicia."""
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
    """Cria valores padrao no st.session_state sem apagar escolhas do usuario."""
    # O session_state guarda informacoes entre interacoes da mesma sessao.
    # Assim, outras paginas conseguem reutilizar projeto, area, execucao e camadas.
    defaults: dict[str, Any] = {
        "projeto_id": None,
        "area_interesse_id": None,
        "execucao_id": "",
        "projeto_sig_dir": "",
        "usuario_execucao": "Paulo",
        "camadas_selecionadas": [
            "geologia",
            "geomorfologia",
            "hidrogeologia",
            "pedologia",
            "vegetacao",
        ],
        "parametros_diagnostico": parametros_padrao(),
    }
    for key, value in defaults.items():
        # setdefault evita sobrescrever uma escolha ja feita pelo usuario.
        st.session_state.setdefault(key, value)


def fetch_dataframe(sql: str, params: tuple[Any, ...] = ()) -> QueryResult:
    """Executa uma consulta SELECT e devolve o resultado como DataFrame."""
    # Usada pelas paginas para buscar dados ja existentes/processados no banco.
    # A sessao e aberta como somente leitura para reduzir risco de alteracao acidental.
    try:
        with get_connection() as conn:
            conn.set_session(readonly=True, autocommit=True)
            data = pd.read_sql_query(sql, conn, params=params)
        return QueryResult(ok=True, data=data)
    except Exception as exc:  # pragma: no cover - exibido na interface
        return QueryResult(ok=False, data=pd.DataFrame(), erro=str(exc))


def fetch_scalar(sql: str, params: tuple[Any, ...] = ()) -> Any:
    """Executa uma consulta que deve retornar apenas um valor."""
    result = fetch_dataframe(sql, params)
    if not result.ok or result.data.empty:
        return None
    return result.data.iloc[0, 0]


def testar_conexao() -> dict[str, Any]:
    """Verifica se o banco responde e resume informacoes basicas para Administracao."""
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
    """Confere se uma coluna existe antes de montar consultas dependentes dela."""
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
    """Retorna somente as colunas candidatas que existem na tabela real."""
    # Isso deixa a interface tolerante a pequenas diferencas entre ambientes de banco.
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
    """Monta SELECT usando NULL quando uma coluna opcional nao existe."""
    partes = []
    for coluna in candidatas:
        if coluna in existentes:
            partes.append(f"{alias}.{coluna}")
        else:
            partes.append(f"NULL::text AS {coluna}")
    return ",\n            ".join(partes)


def carregar_projetos() -> QueryResult:
    """Lista projetos cadastrados. Apenas leitura."""
    candidatas = (
        "id",
        "codigo",
        "codigo_projeto",
        "nome",
        "cliente",
        "municipio",
        "uf",
        "atividade",
        "tipo_estudo",
        "responsavel",
        "pasta_sig",
        "status",
        "descricao",
        "data_cadastro",
        "data_atualizacao",
    )
    existentes = colunas_existentes("projetos", "projeto", candidatas)
    select_cols = montar_select_colunas("p", candidatas, existentes)
    data_cadastro = "p.data_cadastro" if "data_cadastro" in existentes else "NULL::timestamp"
    data_atualizacao = "p.data_atualizacao" if "data_atualizacao" in existentes else "NULL::timestamp"
    return fetch_dataframe(
        f"""
        SELECT
            {select_cols}
        FROM projetos.projeto AS p
        ORDER BY COALESCE({data_atualizacao}, {data_cadastro}) DESC NULLS LAST, p.id DESC;
        """
    )


def carregar_areas(projeto_id: int) -> QueryResult:
    """Lista areas de interesse vinculadas a um projeto. Apenas leitura."""
    candidatas = (
        "id",
        "projeto_id",
        "nome",
        "tipo",
        "fonte",
        "observacao",
        "srid_origem",
        "area_m2",
        "area_ha",
        "data_cadastro",
        "data_atualizacao",
    )
    existentes = colunas_existentes("projetos", "area_interesse", candidatas)
    select_cols = montar_select_colunas("ai", candidatas, existentes)
    data_cadastro = "ai.data_cadastro" if "data_cadastro" in existentes else "NULL::timestamp"
    data_atualizacao = "ai.data_atualizacao" if "data_atualizacao" in existentes else "NULL::timestamp"
    return fetch_dataframe(
        f"""
        SELECT
            {select_cols}
        FROM projetos.area_interesse AS ai
        WHERE ai.projeto_id = %s
        ORDER BY COALESCE({data_atualizacao}, {data_cadastro}) DESC NULLS LAST, ai.id DESC;
        """,
        (projeto_id,),
    )

def carregar_ultimas_execucoes(limit: int = 10) -> QueryResult:
    """Busca execucoes recentes para a pagina Administracao. Apenas leitura."""
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
    """Verifica se uma view existe antes de tentar consulta-la."""
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


def make_key(*partes: Any) -> str:
    """
    Monta uma chave unica e estavel para elementos Streamlit.

    O Streamlit exige uma key unica para elementos repetidos, como graficos Plotly.
    A funcao normaliza acentos, remove caracteres problematicos e junta o contexto
    com `__`, evitando colisao quando o mesmo grafico aparece em abas diferentes.
    """
    partes_limpas: list[str] = []
    for parte in partes:
        texto = str(parte if parte is not None else "vazio").strip().lower()
        texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
        texto = re.sub(r"\s+", "_", texto)
        texto = re.sub(r"[^a-z0-9_\-]+", "", texto)
        texto = re.sub(r"_+", "_", texto).strip("_")
        partes_limpas.append(texto or "vazio")
    return "__".join(partes_limpas)


def exibir_plotly(fig: Any, key: str) -> None:
    """Exibe grafico Plotly no Streamlit usando uma chave unica."""
    st.plotly_chart(fig, use_container_width=True, key=key)


def comando_mvp() -> str | None:
    """Monta o comando do orquestrador MVP sem executa-lo automaticamente."""
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
    """Monta comando de validacao da configuracao, apenas para copiar e revisar."""
    comando = comando_mvp()
    if comando:
        return f"{comando} --dry-run"
    return None


def comando_com_execucao(script: str, incluir_overwrite: bool = False) -> tuple[str | None, str | None]:
    """Monta comandos de exportacao/grafico/GPKG com ids escolhidos na interface."""
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
    """Mostra uma tabela de resultado na interface, tratando erro e vazio."""
    st.subheader(titulo)
    if not result.ok:
        st.warning(result.erro or f"View indisponível: {titulo}")
        return
    if result.data.empty:
        st.info(vazio or "Nenhum registro encontrado.")
        return
    st.dataframe(result.data, use_container_width=True)


def normalizar_geojson(valor: Any) -> dict[str, Any] | None:
    """Converte retorno do PostGIS para objeto GeoJSON que o Folium entende."""
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
    """Executa SELECT espacial que ja retorna GeoJSON pronto para mapa."""
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
    """Busca a area de interesse do projeto e devolve GeoJSON para exibicao."""
    # A consulta simplifica a geometria somente para visualizacao no mapa web.
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
    """Monta GeoJSON do buffer operacional usado como limite de analise."""
    # O buffer e calculado no SRID operacional e transformado para 4326 ao exibir.
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
    """Carrega microbacias que intersectam a area de interesse para o mapa."""
    # A intersecao usa bounding box e geometrias validas para manter a consulta robusta.
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
    """Busca os setores censitarios intersectados ja processados para o mapa."""
    # A geometria exibida e a intersecao gravada em resultados.setores_intersectados.
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
    """Carrega trechos de hidrografia ANA processados para visualizacao."""
    # Esta camada e opcional e so aparece quando a execucao tiver hidrografia gravada.
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
    """Confere se o GeoJSON possui feicoes antes de adicionar ao mapa."""
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
    """Adiciona uma camada GeoJSON ao mapa Folium quando ha geometria valida."""
    # O Folium/Leaflet espera coordenadas em EPSG:4326 para visualizacao web.
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

METRICAS_CAMADAS = ("area", "comprimento", "contagem", "proximidade", "atributo")
TIPOS_PROCESSAMENTO_CAMADAS = (
    "poligono_area",
    "linha_comprimento",
    "ponto_contagem",
    "proximidade",
    "atributo",
)
TIPOS_GEOMETRIA_CAMADAS = (
    "MULTIPOLYGON",
    "POLYGON",
    "MULTILINESTRING",
    "LINESTRING",
    "MULTIPOINT",
    "POINT",
)


def lista_csv(valor: str) -> list[str]:
    return [item.strip() for item in valor.split(",") if item.strip()]


def carregar_camadas_analise_ativas() -> QueryResult:
    """Carrega camadas configuradas para compor diagnosticos. Apenas leitura."""
    return fetch_dataframe(
        """
        SELECT *
        FROM config.vw_camadas_analise_ativas
        ORDER BY grupo, ordem_exibicao, tema, titulo;
        """
    )


def salvar_camada_analise(dados: dict[str, Any]) -> tuple[bool, str]:
    """Grava cadastro operacional de camada de analise mediante acao do usuario."""
    # Esta escrita ocorre somente em schema operacional de configuracao, nao nos schemas oficiais.
    sql = """
        INSERT INTO config.camadas_analise (
            nome_logico,
            titulo,
            grupo,
            tema,
            subtema,
            schema_name,
            table_name,
            geom_column,
            pk_column,
            tipo_geometria,
            srid,
            fonte,
            orgao_produtor,
            ano_referencia,
            campo_valor_principal,
            campos_descritivos,
            metrica_padrao,
            tipo_processamento,
            usar_area_interesse,
            usar_buffer_1000m,
            usar_microbacia,
            usar_setor_censitario,
            exibir_dashboard,
            exportar_gpkg,
            incluir_relatorio,
            ativo,
            observacao
        ) VALUES (
            %(nome_logico)s,
            %(titulo)s,
            %(grupo)s,
            %(tema)s,
            %(subtema)s,
            %(schema_name)s,
            %(table_name)s,
            %(geom_column)s,
            %(pk_column)s,
            %(tipo_geometria)s,
            %(srid)s,
            %(fonte)s,
            %(orgao_produtor)s,
            %(ano_referencia)s,
            %(campo_valor_principal)s,
            %(campos_descritivos)s::jsonb,
            %(metrica_padrao)s,
            %(tipo_processamento)s,
            %(usar_area_interesse)s,
            %(usar_buffer_1000m)s,
            %(usar_microbacia)s,
            %(usar_setor_censitario)s,
            %(exibir_dashboard)s,
            %(exportar_gpkg)s,
            %(incluir_relatorio)s,
            %(ativo)s,
            %(observacao)s
        )
        ON CONFLICT (nome_logico) DO UPDATE SET
            titulo = EXCLUDED.titulo,
            grupo = EXCLUDED.grupo,
            tema = EXCLUDED.tema,
            subtema = EXCLUDED.subtema,
            schema_name = EXCLUDED.schema_name,
            table_name = EXCLUDED.table_name,
            geom_column = EXCLUDED.geom_column,
            pk_column = EXCLUDED.pk_column,
            tipo_geometria = EXCLUDED.tipo_geometria,
            srid = EXCLUDED.srid,
            fonte = EXCLUDED.fonte,
            orgao_produtor = EXCLUDED.orgao_produtor,
            ano_referencia = EXCLUDED.ano_referencia,
            campo_valor_principal = EXCLUDED.campo_valor_principal,
            campos_descritivos = EXCLUDED.campos_descritivos,
            metrica_padrao = EXCLUDED.metrica_padrao,
            tipo_processamento = EXCLUDED.tipo_processamento,
            usar_area_interesse = EXCLUDED.usar_area_interesse,
            usar_buffer_1000m = EXCLUDED.usar_buffer_1000m,
            usar_microbacia = EXCLUDED.usar_microbacia,
            usar_setor_censitario = EXCLUDED.usar_setor_censitario,
            exibir_dashboard = EXCLUDED.exibir_dashboard,
            exportar_gpkg = EXCLUDED.exportar_gpkg,
            incluir_relatorio = EXCLUDED.incluir_relatorio,
            ativo = EXCLUDED.ativo,
            observacao = EXCLUDED.observacao,
            atualizado_em = now();
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, dados)
            conn.commit()
        return True, "Camada salva em config.camadas_analise."
    except Exception as exc:  # pragma: no cover - exibido na interface
        return False, str(exc)


def dataframe_camadas_filtrado(
    data: pd.DataFrame,
    grupo: str,
    tema: str,
    metrica: str,
    status: str,
) -> pd.DataFrame:
    filtrado = data.copy()
    if grupo != "Todos" and "grupo" in filtrado.columns:
        filtrado = filtrado[filtrado["grupo"] == grupo]
    if tema != "Todos" and "tema" in filtrado.columns:
        filtrado = filtrado[filtrado["tema"] == tema]
    if metrica != "Todas" and "metrica_padrao" in filtrado.columns:
        filtrado = filtrado[filtrado["metrica_padrao"] == metrica]
    if status != "Todas" and "ativo" in filtrado.columns:
        filtrado = filtrado[filtrado["ativo"] == (status == "Ativas")]
    return filtrado


def camadas_ambientais_padrao() -> list[str]:
    return [camada for camada in ANALISES_AMBIENTAIS if camada != "hidrografia_ana"]


def sincronizar_parametros_camadas(
    camadas_selecionadas: list[str],
    socioeconomia: bool,
    usar_area_interesse: bool,
    usar_buffer: bool,
    usar_microbacias: bool,
    usar_setores: bool,
    distancia_buffer_m: int,
) -> dict[str, Any]:
    atual = parametros_padrao()
    for camada in ANALISES_AMBIENTAIS:
        atual[camada] = camada in camadas_selecionadas

    limites = []
    if usar_area_interesse:
        limites.append("area_interesse")
    if usar_buffer:
        limites.append("buffer_1000m")
    if usar_microbacias:
        limites.append("microbacia")
    if usar_setores:
        limites.append("setores_censitarios")

    atual.update(
        {
            "camadas_selecionadas": camadas_selecionadas,
            "limites_selecionados": limites,
            "socioeconomia": socioeconomia,
            "area_interesse": usar_area_interesse,
            "buffer": usar_buffer,
            "microbacias": usar_microbacias,
            "setores_censitarios": usar_setores,
            "usar_buffer": usar_buffer,
            "distancia_buffer_m": distancia_buffer_m,
        }
    )
    return atual


def gerar_slug(texto: str) -> str:
    normalizado = texto.lower().strip()
    normalizado = re.sub(r"[^a-z0-9]+", "-", normalizado)
    normalizado = re.sub(r"-+", "-", normalizado).strip("-")
    return normalizado or "projeto"


def sugerir_codigo_projeto(total_projetos: int | None = None) -> str:
    ano = datetime.now().year
    sequencial = int(total_projetos or 0) + 1
    return f"EA2S-{ano}-{sequencial:03d}"


def sugerir_pasta_sig(nome_projeto: str) -> str:
    raiz = os.getenv("EA2S_PROJECTS_ROOT") or r"C:\Users\Usuario\OneDrive\EA2S\Projetos"
    ano = datetime.now().year
    return str(Path(raiz) / str(ano) / gerar_slug(nome_projeto or "novo-projeto") / "SIG")


def carregar_projetos_inicio() -> QueryResult:
    candidatas = (
        "id",
        "codigo",
        "codigo_projeto",
        "nome",
        "cliente",
        "municipio",
        "uf",
        "atividade",
        "tipo_estudo",
        "responsavel",
        "pasta_sig",
        "status",
        "descricao",
        "data_cadastro",
        "data_atualizacao",
    )
    existentes = colunas_existentes("projetos", "projeto", candidatas)
    select_cols = montar_select_colunas("p", candidatas, existentes)
    data_cadastro = "p.data_cadastro" if "data_cadastro" in existentes else "NULL::timestamp"
    data_atualizacao = "p.data_atualizacao" if "data_atualizacao" in existentes else "NULL::timestamp"
    return fetch_dataframe(
        f"""
        SELECT
            {select_cols}
        FROM projetos.projeto AS p
        ORDER BY COALESCE({data_atualizacao}, {data_cadastro}) DESC NULLS LAST, p.id DESC;
        """
    )


def carregar_areas_interesse_inicio(projeto_id: int) -> QueryResult:
    candidatas = (
        "id",
        "projeto_id",
        "nome",
        "tipo",
        "fonte",
        "observacao",
        "srid_origem",
        "area_m2",
        "area_ha",
        "data_cadastro",
        "data_atualizacao",
    )
    existentes = colunas_existentes("projetos", "area_interesse", candidatas)
    select_cols = montar_select_colunas("ai", candidatas, existentes)
    data_cadastro = "ai.data_cadastro" if "data_cadastro" in existentes else "NULL::timestamp"
    data_atualizacao = "ai.data_atualizacao" if "data_atualizacao" in existentes else "NULL::timestamp"
    return fetch_dataframe(
        f"""
        SELECT
            {select_cols}
        FROM projetos.area_interesse AS ai
        WHERE ai.projeto_id = %s
        ORDER BY COALESCE({data_atualizacao}, {data_cadastro}) DESC NULLS LAST, ai.id DESC;
        """,
        (projeto_id,),
    )


def valor_linha(row: pd.Series | None, campo: str, default: str = "") -> str:
    if row is None or campo not in row:
        return default
    valor = row.get(campo)
    if pd.isna(valor):
        return default
    return str(valor)


def valor_codigo_projeto(row: pd.Series | None, default: str = "") -> str:
    codigo = valor_linha(row, "codigo")
    if codigo:
        return codigo
    return valor_linha(row, "codigo_projeto", default)


def label_projeto_inicio(row: pd.Series) -> str:
    codigo = valor_codigo_projeto(row)
    partes = [f"Projeto {row.get('id')}"]
    if codigo.strip():
        partes.append(codigo.strip())
    nome = valor_linha(row, "nome")
    if nome.strip():
        partes.append(nome.strip())
    municipio = valor_linha(row, "municipio")
    uf = valor_linha(row, "uf")
    local = "/".join(valor.strip() for valor in (municipio, uf) if valor.strip())
    if local:
        partes.append(local)
    return " | ".join(partes)


def label_area_interesse_inicio(row: pd.Series) -> str:
    """Monta texto legivel para cada area existente no seletor."""
    partes = [f"Área {row.get('id')}"]
    nome = valor_linha(row, "nome")
    if nome.strip():
        partes.append(nome.strip())
    area_ha = row.get("area_ha") if "area_ha" in row else None
    if pd.notna(area_ha):
        try:
            partes.append(f"{float(area_ha):.4f} ha")
        except (TypeError, ValueError):
            pass
    tipo = valor_linha(row, "tipo")
    if tipo.strip():
        partes.append(tipo.strip())
    return " | ".join(partes)


def salvar_upload_temporario(uploaded_file: Any) -> Path:
    """Salva o arquivo enviado pelo navegador em uma pasta temporaria."""
    # O GeoPandas precisa de um caminho de arquivo para ler GPKG, GeoJSON ou SHP zipado.
    sufixo = Path(uploaded_file.name).suffix.lower()
    destino = Path(tempfile.mkdtemp(prefix="ea2s_area_")) / f"area_interesse{sufixo}"
    destino.write_bytes(uploaded_file.getbuffer())
    return destino


def validar_zip_shapefile(caminho: Path) -> None:
    """Confere se o ZIP contem os arquivos minimos de um shapefile."""
    with zipfile.ZipFile(caminho) as zf:
        nomes = {Path(nome).suffix.lower() for nome in zf.namelist()}
    obrigatorios = {".shp", ".dbf", ".shx"}
    faltantes = sorted(obrigatorios - nomes)
    if faltantes:
        raise ValueError(f"ZIP de shapefile incompleto. Faltando: {', '.join(faltantes)}")


def listar_layers_gpkg(caminho: Path) -> list[str]:
    """Lista camadas internas de um GeoPackage para o usuario escolher."""
    try:
        if hasattr(gpd, "list_layers"):
            layers = gpd.list_layers(caminho)
            if "name" in layers:
                return [str(nome) for nome in layers["name"].tolist()]
    except Exception:
        pass
    try:
        import fiona
        return list(fiona.listlayers(caminho))
    except Exception:
        return []


def ler_area_interesse_upload(caminho: Path, layer: str | None = None) -> gpd.GeoDataFrame:
    """Le o arquivo espacial enviado e devolve um GeoDataFrame."""
    # Suporta GPKG, GeoJSON e shapefile zipado sem alterar dados oficiais.
    sufixo = caminho.suffix.lower()
    if sufixo == ".zip":
        validar_zip_shapefile(caminho)
        return gpd.read_file(f"zip://{caminho}")
    if sufixo == ".gpkg":
        if layer:
            return gpd.read_file(caminho, layer=layer)
        return gpd.read_file(caminho)
    if sufixo in {".geojson", ".json"}:
        return gpd.read_file(caminho)
    raise ValueError("Formato nao suportado. Use GPKG, GeoJSON, SHP ou SHP zipado.")


def _make_valid_geoseries(serie: gpd.GeoSeries) -> gpd.GeoSeries:
    """Tenta corrigir geometrias invalidas antes de gravar no banco."""
    try:
        return serie.make_valid()
    except Exception:
        return serie.buffer(0)


def validar_area_interesse_gdf(gdf: gpd.GeoDataFrame, epsg_original: int = 31982) -> dict[str, Any]:
    """Valida a area de interesse e prepara geometria em EPSG:31982."""
    # EPSG:31982 e usado para calculo de area em metros; EPSG:4326 fica para mapas web.
    # A area de interesse deve ser Polygon ou MultiPolygon.
    if gdf.empty:
        raise ValueError("O arquivo nao possui feicoes.")
    if gdf.geometry.isna().all():
        raise ValueError("O arquivo nao possui geometria valida.")

    gdf = gdf.copy()
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=epsg_original, allow_override=True)
    srid_origem = int(gdf.crs.to_epsg() or epsg_original)

    tipos = sorted({str(tipo) for tipo in gdf.geometry.geom_type.dropna().unique()})
    tipos_validos = {"Polygon", "MultiPolygon"}
    if any(tipo not in tipos_validos for tipo in tipos):
        raise ValueError("A area de interesse deve conter somente Polygon ou MultiPolygon.")

    gdf.geometry = _make_valid_geoseries(gdf.geometry)
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()].copy()
    if gdf.empty:
        raise ValueError("A geometria resultante esta vazia.")

    gdf_31982 = gdf.to_crs(epsg=31982)
    geom = gdf_31982.geometry.union_all() if hasattr(gdf_31982.geometry, "union_all") else gdf_31982.unary_union
    geom_gdf = gpd.GeoDataFrame(geometry=[geom], crs="EPSG:31982")
    geom_gdf.geometry = _make_valid_geoseries(geom_gdf.geometry)
    geom = geom_gdf.geometry.iloc[0]
    if geom.is_empty:
        raise ValueError("A geometria consolidada esta vazia.")
    if geom.geom_type == "Polygon":
        from shapely.geometry import MultiPolygon
        geom = MultiPolygon([geom])
    if geom.geom_type != "MultiPolygon":
        raise ValueError("A geometria consolidada nao resultou em MultiPolygon.")

    bbox = tuple(round(float(valor), 3) for valor in geom.bounds)
    area_m2 = float(geom.area)
    return {
        "crs_original": str(gdf.crs),
        "srid_origem": srid_origem,
        "tipo_geometria": ", ".join(tipos),
        "numero_feicoes": int(len(gdf)),
        "varias_feicoes": int(len(gdf)) > 1,
        "colunas": [str(coluna) for coluna in gdf.columns if coluna != gdf.geometry.name],
        "bbox": bbox,
        "area_m2": area_m2,
        "area_ha": area_m2 / 10000.0,
        "geom_31982": geom,
    }


def obter_colunas_tabela(conn: Any, schema: str, tabela: str) -> set[str]:
    """Consulta as colunas reais de uma tabela usando conexao ja aberta."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.column_name
            FROM information_schema.columns AS c
            WHERE c.table_schema = %s
              AND c.table_name = %s;
            """,
            (schema, tabela),
        )
        return {row[0] for row in cur.fetchall()}


def _executar_insert_dinamico(conn: Any, schema_tabela: str, dados: dict[str, Any], colunas_existentes_tbl: set[str]) -> int:
    """Insere somente colunas existentes e retorna o id criado."""
    # Usado para evitar erro quando algum ambiente ainda nao possui campo opcional.
    colunas = [coluna for coluna in dados if coluna in colunas_existentes_tbl and dados[coluna] is not None]
    if not colunas:
        raise ValueError("Nenhuma coluna compativel encontrada para inserir projeto.")
    placeholders = ", ".join(["%s"] * len(colunas))
    sql = f"INSERT INTO {schema_tabela} ({', '.join(colunas)}) VALUES ({placeholders}) RETURNING id;"
    with conn.cursor() as cur:
        cur.execute(sql, tuple(dados[coluna] for coluna in colunas))
        return int(cur.fetchone()[0])


def _executar_update_dinamico(conn: Any, schema_tabela: str, registro_id: int, dados: dict[str, Any], colunas_existentes_tbl: set[str]) -> None:
    """Atualiza somente colunas existentes de um registro operacional."""
    colunas = [coluna for coluna in dados if coluna in colunas_existentes_tbl]
    if "data_atualizacao" in colunas_existentes_tbl:
        dados = {**dados, "data_atualizacao": datetime.now()}
        colunas = [coluna for coluna in dados if coluna in colunas_existentes_tbl]
    if not colunas:
        return
    set_sql = ", ".join(f"{coluna} = %s" for coluna in colunas)
    sql = f"UPDATE {schema_tabela} SET {set_sql} WHERE id = %s;"
    with conn.cursor() as cur:
        cur.execute(sql, tuple(dados[coluna] for coluna in colunas) + (registro_id,))


def inserir_area_interesse(conn: Any, projeto_id: int, dados_area: dict[str, Any], validacao: dict[str, Any]) -> tuple[int, float | None]:
    """Grava nova area em projetos.area_interesse usando geometria validada."""
    # Esta e uma escrita controlada no schema operacional projetos, nunca nos schemas oficiais.
    colunas_existentes_tbl = obter_colunas_tabela(conn, "projetos", "area_interesse")
    if "geom" not in colunas_existentes_tbl:
        raise ValueError("A tabela projetos.area_interesse nao possui coluna geom.")

    valores = {
        "projeto_id": projeto_id,
        "nome": dados_area["nome"],
        "tipo": dados_area["tipo"],
        "fonte": dados_area["fonte"],
        "observacao": dados_area.get("observacao"),
        "srid_origem": validacao["srid_origem"],
    }
    colunas = [coluna for coluna in valores if coluna in colunas_existentes_tbl]
    expressoes = ["%s"] * len(colunas)
    params: list[Any] = [valores[coluna] for coluna in colunas]

    if "area_m2" in colunas_existentes_tbl:
        colunas.append("area_m2")
        expressoes.append("ST_Area(geom)")
    if "area_ha" in colunas_existentes_tbl:
        colunas.append("area_ha")
        expressoes.append("ST_Area(geom) / 10000.0")
    colunas.append("geom")
    expressoes.append("geom")

    geom_wkb = Binary(validacao["geom_31982"].wkb)
    sql = f"""
        WITH g AS (
            SELECT
                ST_Multi(
                    ST_CollectionExtract(
                        ST_MakeValid(
                            ST_SetSRID(ST_GeomFromWKB(%s), 31982)
                        ),
                        3
                    )
                ) AS geom
        )
        INSERT INTO projetos.area_interesse ({', '.join(colunas)})
        SELECT {', '.join(expressoes)}
        FROM g
        RETURNING id{', area_ha' if 'area_ha' in colunas_existentes_tbl else ''};
    """
    with conn.cursor() as cur:
        cur.execute(sql, (geom_wkb, *params))
        row = cur.fetchone()
    return int(row[0]), float(row[1]) if len(row) > 1 and row[1] is not None else None


def atualizar_projeto_existente(
    projeto_id: int,
    dados_projeto: dict[str, Any],
    criar_pasta: bool,
) -> None:
    """Atualiza campos permitidos de projeto existente apos confirmacao do usuario."""
    pasta_sig = dados_projeto.get("pasta_sig")
    if criar_pasta and pasta_sig:
        Path(pasta_sig).mkdir(parents=True, exist_ok=True)

    campos_permitidos = {
        "cliente",
        "municipio",
        "uf",
        "atividade",
        "tipo_estudo",
        "responsavel",
        "pasta_sig",
        "descricao",
        "status",
    }
    dados_update = {
        campo: valor
        for campo, valor in dados_projeto.items()
        if campo in campos_permitidos and valor not in (None, "")
    }
    with get_connection() as conn:
        try:
            colunas_projeto = obter_colunas_tabela(conn, "projetos", "projeto")
            _executar_update_dinamico(conn, "projetos.projeto", int(projeto_id), dados_update, colunas_projeto)
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def salvar_nova_area_interesse(
    projeto_id: int,
    dados_area: dict[str, Any],
    validacao: dict[str, Any],
) -> tuple[int, float | None]:
    """Salva nova area em um projeto ja cadastrado, dentro de transacao."""
    with get_connection() as conn:
        try:
            area_id, area_ha = inserir_area_interesse(conn, int(projeto_id), dados_area, validacao)
            conn.commit()
            return area_id, area_ha
        except Exception:
            conn.rollback()
            raise


def salvar_projeto_area_interesse(
    projeto_id: int | None,
    dados_projeto: dict[str, Any],
    dados_area: dict[str, Any],
    validacao: dict[str, Any],
    criar_pasta: bool,
) -> tuple[int, int, float | None]:
    """Cria novo projeto e sua primeira area de interesse dentro de transacao."""
    pasta_sig = dados_projeto.get("pasta_sig")
    if criar_pasta and pasta_sig:
        Path(pasta_sig).mkdir(parents=True, exist_ok=True)

    if projeto_id is not None:
        raise ValueError("Use salvar_nova_area_interesse para projetos existentes.")

    with get_connection() as conn:
        try:
            colunas_projeto = obter_colunas_tabela(conn, "projetos", "projeto")
            projeto_id_final = _executar_insert_dinamico(conn, "projetos.projeto", dados_projeto, colunas_projeto)
            area_id, area_ha = inserir_area_interesse(conn, projeto_id_final, dados_area, validacao)
            conn.commit()
            return projeto_id_final, area_id, area_ha
        except Exception:
            conn.rollback()
            raise


def renderizar_metadados_area_upload(uploaded_file: Any, epsg_original: int) -> None:
    """Valida o upload e mostra metadados antes de qualquer gravacao."""
    try:
        caminho = salvar_upload_temporario(uploaded_file)
        layer = None
        if caminho.suffix.lower() == ".gpkg":
            layers = listar_layers_gpkg(caminho)
            if layers:
                layer = st.selectbox("Layer do GPKG", layers, key=f"inicio_layer_gpkg_{uploaded_file.name}")
            else:
                st.warning("Não foi possível listar layers do GPKG. Será tentada a primeira layer disponível.")
        gdf = ler_area_interesse_upload(caminho, layer=layer)
        validacao = validar_area_interesse_gdf(gdf, epsg_original=int(epsg_original))
        # Guarda a validacao no session_state para o botao de salvar usar depois.
        st.session_state["area_interesse_upload_validada"] = validacao
        st.session_state["area_interesse_upload_nome"] = uploaded_file.name
        st.success("Área de interesse validada para gravação.")
        st.json(
            {
                "arquivo": uploaded_file.name,
                "tipo_arquivo": Path(uploaded_file.name).suffix.lower(),
                "crs_original": validacao["crs_original"],
                "tipo_geometria": validacao["tipo_geometria"],
                "numero_feicoes": validacao["numero_feicoes"],
                "colunas": validacao["colunas"],
                "bbox": validacao["bbox"],
                "area_ha": round(validacao["area_ha"], 6),
                "varias_feicoes_dissolvidas": validacao["varias_feicoes"],
            }
        )
        if validacao["varias_feicoes"]:
            st.warning("O arquivo possui várias feições; elas serão dissolvidas em uma única geometria MultiPolygon.")
    except Exception as exc:
        st.session_state["area_interesse_upload_validada"] = None
        st.session_state["area_interesse_upload_nome"] = None
        st.error(f"Não foi possível validar a área de interesse: {exc}")

def renderizar_fluxo_iniciar_projeto() -> None:
    """Renderiza o fluxo de selecionar/cadastrar projeto e area de interesse."""
    # Seletores que mudam o contexto ficam fora do st.form para permitir que o
    # Streamlit recarregue dados reais do projeto/area antes de o usuario salvar.
    # As acoes que gravam ou consolidam escolha ficam dentro do form.
    projetos = carregar_projetos_inicio()
    projetos_df = projetos.data if projetos.ok else pd.DataFrame()
    total_projetos = len(projetos_df) if projetos.ok else 0

    opcoes = ["Cadastrar novo projeto"]
    opcao_projeto_para_id: dict[str, int | None] = {"Cadastrar novo projeto": None}
    if projetos.ok and not projetos_df.empty:
        for _, row in projetos_df.iterrows():
            label = label_projeto_inicio(row)
            opcao_projeto_para_id[label] = int(row["id"])
            opcoes.append(label)
    elif not projetos.ok:
        st.warning(projetos.erro or "Não foi possível listar projetos existentes.")

    st.markdown("### 1. Projeto")
    escolha_projeto = st.selectbox("Projeto", opcoes, key="inicio_escolha_projeto")
    projeto_id_selecionado = opcao_projeto_para_id.get(escolha_projeto)
    projeto_existente = projeto_id_selecionado is not None
    projeto_row = None

    if projeto_existente and not projetos_df.empty:
        linhas = projetos_df[projetos_df["id"].astype("int64") == int(projeto_id_selecionado)]
        if not linhas.empty:
            projeto_row = linhas.iloc[0]
            # O session_state compartilha projeto, area e pasta SIG com as demais paginas.
            st.session_state["projeto_id"] = int(projeto_id_selecionado)
            st.session_state["projeto_nome"] = valor_linha(projeto_row, "nome")
            st.session_state["projeto_sig_dir"] = valor_linha(projeto_row, "pasta_sig")
            st.info("Modo: projeto existente. Os dados foram carregados do banco.")
    else:
        st.info("Modo: novo projeto.")

    key_sufixo = f"projeto_{projeto_id_selecionado}" if projeto_existente else "novo_projeto"
    nome_default = valor_linha(projeto_row, "nome")
    codigo_default = valor_codigo_projeto(projeto_row)
    if not projeto_existente and not codigo_default:
        codigo_default = sugerir_codigo_projeto(total_projetos)

    editar_projeto = False
    if projeto_existente:
        editar_projeto = st.checkbox("Editar dados do projeto existente", value=False, key=f"inicio_editar_{key_sufixo}")

    areas_df = pd.DataFrame()
    modo_area = "Inserir nova área de interesse"
    if projeto_existente and projeto_id_selecionado is not None:
        areas = carregar_areas_interesse_inicio(int(projeto_id_selecionado))
        if areas.ok:
            areas_df = areas.data
        else:
            st.warning(areas.erro or "Não foi possível listar áreas de interesse do projeto.")
        opcoes_area_modo = ["Inserir nova área de interesse"]
        if not areas_df.empty:
            opcoes_area_modo.insert(0, "Usar área de interesse existente")
        modo_area = st.radio("Área de interesse", opcoes_area_modo, horizontal=True, key=f"inicio_modo_area_{key_sufixo}")

    validacao_atual = st.session_state.get("area_interesse_upload_validada")
    nome_upload_validado = st.session_state.get("area_interesse_upload_nome")
    if validacao_atual is not None and nome_upload_validado:
        st.success(f"Área validada: {nome_upload_validado}")
        resumo_validacao = pd.DataFrame(
            [
                {"metadado": "CRS original", "valor": validacao_atual.get("crs_original")},
                {"metadado": "Tipo de geometria", "valor": validacao_atual.get("tipo_geometria")},
                {"metadado": "Número de feições", "valor": validacao_atual.get("numero_feicoes")},
                {"metadado": "Área total (ha)", "valor": round(float(validacao_atual.get("area_ha") or 0), 6)},
                {"metadado": "BBox EPSG:31982", "valor": validacao_atual.get("bbox")},
            ]
        )
        st.table(resumo_validacao)
        st.caption("Colunas encontradas: " + ", ".join(validacao_atual.get("colunas") or []))

    # O st.form evita que a cada interacao parcial o Streamlit tente salvar ou validar
    # dados incompletos. As operacoes so acontecem quando um botao de submit e usado.
    with st.form(f"form_iniciar_projeto_{key_sufixo}"):
        st.markdown("### 1. Projeto")
        campos_desabilitados = projeto_existente and not editar_projeto
        codigo_desabilitado = projeto_existente
        nome_desabilitado = projeto_existente

        c1, c2 = st.columns(2)
        with c1:
            if projeto_existente:
                st.text_input("ID do projeto", value=str(projeto_id_selecionado), disabled=True, key=f"inicio_id_{key_sufixo}")
            codigo = st.text_input(
                "Código do projeto",
                value=codigo_default,
                disabled=codigo_desabilitado,
                key=f"inicio_codigo_{key_sufixo}",
            )
            nome = st.text_input(
                "Nome do projeto",
                value=nome_default,
                disabled=nome_desabilitado,
                key=f"inicio_nome_{key_sufixo}",
            )
            cliente = st.text_input("Cliente", value=valor_linha(projeto_row, "cliente"), disabled=campos_desabilitados, key=f"inicio_cliente_{key_sufixo}")
            municipio = st.text_input("Município", value=valor_linha(projeto_row, "municipio"), disabled=campos_desabilitados, key=f"inicio_municipio_{key_sufixo}")
            uf = st.text_input("UF", value=valor_linha(projeto_row, "uf"), disabled=campos_desabilitados, key=f"inicio_uf_{key_sufixo}")
        with c2:
            atividade = st.text_input("Atividade", value=valor_linha(projeto_row, "atividade"), disabled=campos_desabilitados, key=f"inicio_atividade_{key_sufixo}")
            tipo_estudo = st.text_input("Tipo de estudo", value=valor_linha(projeto_row, "tipo_estudo"), disabled=campos_desabilitados, key=f"inicio_tipo_estudo_{key_sufixo}")
            responsavel = st.text_input("Responsável", value=valor_linha(projeto_row, "responsavel", "Paulo"), disabled=campos_desabilitados, key=f"inicio_responsavel_{key_sufixo}")
            status_projeto = st.text_input("Status", value=valor_linha(projeto_row, "status", "ativo" if not projeto_existente else ""), disabled=campos_desabilitados, key=f"inicio_status_{key_sufixo}")
            descricao = st.text_area("Descrição", value=valor_linha(projeto_row, "descricao"), disabled=campos_desabilitados, key=f"inicio_descricao_{key_sufixo}")

        st.markdown("### 2. Pasta SIG")
        pasta_default = valor_linha(projeto_row, "pasta_sig") or sugerir_pasta_sig(nome_default or nome or "novo-projeto")
        pasta_sig = st.text_input(
            "Pasta SIG do projeto",
            value=pasta_default,
            disabled=campos_desabilitados,
            key=f"inicio_pasta_sig_{key_sufixo}",
        )
        st.caption("O navegador não abre seletor nativo de pastas; informe o caminho local da pasta SIG do projeto.")
        criar_pasta = st.checkbox(
            "Criar pasta SIG se ela não existir",
            value=False,
            disabled=campos_desabilitados,
            key=f"inicio_criar_pasta_{key_sufixo}",
        )

        st.markdown("### 3. Área de interesse")
        area_existente_id: int | None = None
        if projeto_existente and modo_area == "Usar área de interesse existente":
            opcao_area_para_id: dict[str, int] = {}
            labels_area = []
            for _, row in areas_df.iterrows():
                label = label_area_interesse_inicio(row)
                opcao_area_para_id[label] = int(row["id"])
                labels_area.append(label)
            escolha_area = st.selectbox("Área existente", labels_area, key=f"inicio_area_existente_{key_sufixo}")
            area_existente_id = opcao_area_para_id.get(escolha_area)
            if area_existente_id is not None:
                area_row = areas_df[areas_df["id"].astype("int64") == int(area_existente_id)].iloc[0]
                st.write(
                    {
                        "id": int(area_existente_id),
                        "nome": valor_linha(area_row, "nome"),
                        "tipo": valor_linha(area_row, "tipo"),
                        "area_ha": valor_linha(area_row, "area_ha"),
                        "srid_origem": valor_linha(area_row, "srid_origem"),
                    }
                )
        else:
            uploaded_file = st.file_uploader(
                "Insira a área de interesse",
                type=["gpkg", "geojson", "json", "zip"],
                key=f"inicio_upload_area_{key_sufixo}",
            )
            epsg_original = st.number_input(
                "EPSG original, se o arquivo não informar CRS",
                min_value=1,
                value=31982,
                step=1,
                key=f"inicio_epsg_{key_sufixo}",
            )
            layer = None
            upload_caminho = None
            if uploaded_file is not None:
                upload_caminho = salvar_upload_temporario(uploaded_file)
                if upload_caminho.suffix.lower() == ".gpkg":
                    layers = listar_layers_gpkg(upload_caminho)
                    if layers:
                        layer = st.selectbox("Layer do GPKG", layers, key=f"inicio_layer_gpkg_{key_sufixo}")
                    else:
                        st.warning("Não foi possível listar layers do GPKG. Será tentada a primeira layer disponível.")
            area_nome = st.text_input("Nome da área de interesse", value="Área de interesse principal", key=f"inicio_area_nome_{key_sufixo}")
            area_tipo = st.text_input("Tipo", value="empreendimento", key=f"inicio_area_tipo_{key_sufixo}")
            area_fonte = st.text_input("Fonte", value="upload_webgis", key=f"inicio_area_fonte_{key_sufixo}")
            area_observacao = st.text_area("Observação da área", key=f"inicio_area_observacao_{key_sufixo}")

        confirmar_gravacao = False
        if modo_area != "Usar área de interesse existente" or editar_projeto:
            confirmar_gravacao = st.checkbox("Confirmo que desejo salvar no banco.", key=f"inicio_confirmar_gravacao_{key_sufixo}")

        dados_projeto = {
            "codigo": codigo.strip() or None,
            "codigo_projeto": codigo.strip() or None,
            "nome": nome.strip() or None,
            "cliente": cliente.strip() or None,
            "municipio": municipio.strip() or None,
            "uf": uf.strip() or None,
            "atividade": atividade.strip() or None,
            "tipo_estudo": tipo_estudo.strip() or None,
            "responsavel": responsavel.strip() or None,
            "pasta_sig": pasta_sig.strip() or None,
            "status": status_projeto.strip() or None,
            "descricao": descricao.strip() or None,
        }

        if projeto_existente and modo_area == "Usar área de interesse existente":
            usar_existente = st.form_submit_button("Usar este projeto e esta área", type="primary")
            atualizar_existente = st.form_submit_button("Atualizar dados do projeto existente", type="secondary") if editar_projeto else False
            validar_upload = False
            salvar_area = False
            salvar_novo = False
        elif projeto_existente:
            validar_upload = st.form_submit_button("Validar upload")
            salvar_area = st.form_submit_button("Salvar nova área neste projeto", type="primary")
            atualizar_existente = st.form_submit_button("Atualizar dados do projeto existente", type="secondary") if editar_projeto else False
            usar_existente = False
            salvar_novo = False
        else:
            validar_upload = st.form_submit_button("Validar upload")
            salvar_novo = st.form_submit_button("Salvar projeto e área de interesse", type="primary")
            usar_existente = False
            atualizar_existente = False
            salvar_area = False

    if projeto_existente and editar_projeto and atualizar_existente:
        if not confirmar_gravacao:
            st.warning("Confirme explicitamente a gravação no banco.")
        else:
            try:
                atualizar_projeto_existente(int(projeto_id_selecionado), dados_projeto, criar_pasta)
                st.session_state["projeto_id"] = int(projeto_id_selecionado)
                st.session_state["projeto_nome"] = valor_linha(projeto_row, "nome") or dados_projeto.get("nome") or ""
                st.session_state["projeto_sig_dir"] = dados_projeto.get("pasta_sig") or valor_linha(projeto_row, "pasta_sig")
                st.success("Dados permitidos do projeto atualizados com sucesso.")
            except Exception as exc:
                st.error(f"Não foi possível atualizar o projeto: {exc}")

    if projeto_existente and modo_area == "Usar área de interesse existente" and usar_existente:
        if area_existente_id is None:
            st.warning("Selecione uma área de interesse existente.")
        else:
            st.session_state["projeto_id"] = int(projeto_id_selecionado)
            st.session_state["area_interesse_id"] = int(area_existente_id)
            st.session_state["projeto_nome"] = nome_default
            st.session_state["projeto_sig_dir"] = valor_linha(projeto_row, "pasta_sig") or pasta_sig.strip()
            st.success("Projeto e área de interesse selecionados para a composição do diagnóstico.")
            st.info("Siga para Compor diagnóstico para selecionar limites e camadas de análise.")

    if modo_area != "Usar área de interesse existente" and validar_upload:
        if uploaded_file is None or upload_caminho is None:
            st.warning("Faça upload de uma área de interesse antes de validar.")
        else:
            try:
                gdf = ler_area_interesse_upload(upload_caminho, layer=layer)
                validacao = validar_area_interesse_gdf(gdf, epsg_original=int(epsg_original))
                st.session_state["area_interesse_upload_validada"] = validacao
                st.session_state["area_interesse_upload_nome"] = uploaded_file.name
                st.success("Área de interesse validada para gravação.")
                st.info("Revise os metadados exibidos e, se estiverem corretos, use o botão de salvar.")
            except Exception as exc:
                st.session_state["area_interesse_upload_validada"] = None
                st.session_state["area_interesse_upload_nome"] = None
                st.error(f"Não foi possível validar a área de interesse: {exc}")

    if modo_area != "Usar área de interesse existente":
        dados_area = {
            "nome": area_nome.strip() or "Área de interesse principal",
            "tipo": area_tipo.strip() or "empreendimento",
            "fonte": area_fonte.strip() or "upload_webgis",
            "observacao": area_observacao.strip() or None,
        }
        validacao_salvar = st.session_state.get("area_interesse_upload_validada")
        upload_nome_atual = uploaded_file.name if uploaded_file is not None else None
        upload_confere = upload_nome_atual and st.session_state.get("area_interesse_upload_nome") == upload_nome_atual

        if projeto_existente and salvar_area:
            if not confirmar_gravacao:
                st.warning("Confirme explicitamente a gravação no banco.")
            elif validacao_salvar is None or not upload_confere:
                st.warning("Valide o upload atual antes de salvar a nova área.")
            else:
                try:
                    area_id_salva, area_ha = salvar_nova_area_interesse(int(projeto_id_selecionado), dados_area, validacao_salvar)
                    st.session_state["projeto_id"] = int(projeto_id_selecionado)
                    st.session_state["area_interesse_id"] = area_id_salva
                    st.session_state["projeto_nome"] = nome_default
                    st.session_state["projeto_sig_dir"] = valor_linha(projeto_row, "pasta_sig") or pasta_sig.strip()
                    st.success(f"Nova área de interesse {area_id_salva} salva no projeto {projeto_id_selecionado}.")
                    if area_ha is not None:
                        st.caption(f"Área gravada: {area_ha:.6f} ha")
                    st.info("Siga para Compor diagnóstico para selecionar limites e camadas de análise.")
                except Exception as exc:
                    st.error(f"Não foi possível salvar a nova área de interesse: {exc}")

        if not projeto_existente and salvar_novo:
            if not confirmar_gravacao:
                st.warning("Confirme explicitamente a gravação no banco.")
            elif not (dados_projeto.get("nome") or "").strip():
                st.warning("Nome do projeto é obrigatório.")
            elif not (dados_projeto.get("pasta_sig") or "").strip():
                st.warning("Pasta SIG do projeto é obrigatória.")
            elif validacao_salvar is None or not upload_confere:
                st.warning("Valide o upload atual antes de salvar o projeto e a área.")
            else:
                dados_projeto["codigo"] = dados_projeto.get("codigo") or sugerir_codigo_projeto(total_projetos)
                dados_projeto["codigo_projeto"] = dados_projeto.get("codigo_projeto") or dados_projeto["codigo"]
                dados_projeto["responsavel"] = dados_projeto.get("responsavel") or "Paulo"
                dados_projeto["status"] = dados_projeto.get("status") or "ativo"
                try:
                    projeto_id_salvo, area_id_salva, area_ha = salvar_projeto_area_interesse(
                        None,
                        dados_projeto,
                        dados_area,
                        validacao_salvar,
                        criar_pasta,
                    )
                    st.session_state["projeto_id"] = projeto_id_salvo
                    st.session_state["area_interesse_id"] = area_id_salva
                    st.session_state["projeto_nome"] = dados_projeto.get("nome") or ""
                    st.session_state["projeto_sig_dir"] = dados_projeto.get("pasta_sig") or ""
                    st.success(f"Projeto {projeto_id_salvo} e área de interesse {area_id_salva} salvos com sucesso.")
                    if area_ha is not None:
                        st.caption(f"Área gravada: {area_ha:.6f} ha")
                    st.info("Siga para Compor diagnóstico para selecionar limites e camadas de análise.")
                except Exception as exc:
                    st.error(f"Não foi possível salvar projeto e área de interesse: {exc}")

    st.markdown("### Próximo módulo")
    st.info(
        "A importação de bases oficiais ou locais para o banco corporativo será implementada no próximo módulo. "
        "Nesta etapa, o fluxo funcional habilitado é o cadastro ou seleção de projeto e área de interesse."
    )

def abrir_dialog_iniciar_projeto() -> None:
    """Abre o fluxo Iniciar projeto em modal ou no fallback da pagina."""
    if hasattr(st, "dialog"):
        @st.dialog("Iniciar projeto")
        def _dialog() -> None:
            renderizar_fluxo_iniciar_projeto()

        _dialog()
    else:
        renderizar_fluxo_iniciar_projeto()

def pagina_inicio() -> None:
    """Pagina inicial limpa: titulo, mapa base e botao Iniciar projeto."""
    st.title(APP_TITLE)
    st.caption(
        "WebGIS interno para iniciar projetos, validar áreas de interesse, "
        "compor diagnósticos e exportar produtos técnicos."
    )

    if folium is not None and st_folium is not None:
        mapa = folium.Map(location=[-27.6, -48.55], zoom_start=8, tiles="OpenStreetMap")
        st_folium(mapa, width=None, height=550)
    else:
        st.info("Mapa base indisponível nesta instalação. Instale folium e streamlit-folium para visualização cartográfica.")

    if st.button("Iniciar projeto", type="primary"):
        if hasattr(st, "dialog"):
            abrir_dialog_iniciar_projeto()
        else:
            st.session_state["mostrar_fluxo_inicio_projeto"] = True

    if st.session_state.get("mostrar_fluxo_inicio_projeto"):
        with st.expander("Iniciar projeto", expanded=True):
            renderizar_fluxo_iniciar_projeto()

def exibir_graficos_camadas(data: pd.DataFrame) -> None:
    """Mostra graficos administrativos sobre camadas cadastradas."""
    if data.empty:
        return
    graficos = st.columns(3)
    if "grupo" in data.columns:
        por_grupo = data.groupby("grupo", dropna=False, as_index=False).agg(total=("nome_logico", "count"))
        fig_grupo = px.bar(por_grupo.sort_values("total"), x="total", y="grupo", orientation="h", title="Camadas por grupo")
        with graficos[0]:
            exibir_plotly(fig_grupo, key="camadas_por_grupo")
    if "metrica_padrao" in data.columns:
        por_metrica = data.groupby("metrica_padrao", dropna=False, as_index=False).agg(total=("nome_logico", "count"))
        fig_metrica = px.bar(por_metrica, x="metrica_padrao", y="total", title="Camadas por metrica")
        with graficos[1]:
            exibir_plotly(fig_metrica, key="camadas_por_metrica")
    saidas = []
    for coluna, rotulo in (("exibir_dashboard", "Dashboard"), ("exportar_gpkg", "GPKG"), ("incluir_relatorio", "Relatorio")):
        if coluna in data.columns:
            saidas.append({"saida": rotulo, "total": int(data[coluna].sum())})
    if saidas:
        fig_saidas = px.bar(pd.DataFrame(saidas), x="saida", y="total", title="Disponibilidade por saida")
        with graficos[2]:
            exibir_plotly(fig_saidas, key="camadas_por_saida")

def pagina_projetos_areas() -> None:
    """Lista projetos e areas existentes; mantida como apoio tecnico legado."""
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



GRUPOS_INVENTARIO = (
    "meio_fisico",
    "meio_biotico",
    "socioeconomico",
    "territorial",
    "areas_protegidas",
    "urbano",
    "outros",
)

SCHEMAS_DESTINO_SUGERIDOS = (
    "geologia",
    "geomorfologia",
    "pedologia",
    "vegetacao",
    "hidrografia",
    "urbano",
    "social",
    "economia",
    "territorial",
    "areas_protegidas",
    "riscos",
    "importacao",
    "resultados",
    "outros",
)

GRAFICOS_INVENTARIO = (
    "Barra",
    "Barra horizontal",
    "Linha",
    "Dispersão",
    "Histograma",
    "Box plot",
    "Violino",
    "Área",
    "Heatmap 2D",
    "Treemap",
    "Sunburst",
    "Pizza",
)

NOMES_GENERICOS_TABELA = {"area_interesse", "camada", "upload", "base", "base_geografica", "arquivo"}

def detectar_formato_arquivo(caminho: Path) -> str:
    """Identifica o formato do upload a partir da extensao do arquivo salvo."""
    sufixo = caminho.suffix.lower()
    if sufixo == ".gpkg":
        return "gpkg"
    if sufixo in {".geojson", ".json"}:
        return "geojson"
    if sufixo == ".zip":
        return "shapefile_zip"
    if sufixo == ".shp":
        return "shapefile"
    return "formato_desconhecido"



def calcular_hash_arquivo(caminho: Path) -> str:
    """Calcula SHA256 do arquivo original enviado pelo usuario."""
    h = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()

def listar_shapefiles_zip(caminho: Path) -> tuple[list[str], bool]:
    """Lista arquivos .shp dentro de ZIP e informa se existe .prj."""
    with zipfile.ZipFile(caminho) as zf:
        nomes = zf.namelist()
    shapefiles = sorted(nome for nome in nomes if nome.lower().endswith(".shp"))
    possui_prj = any(nome.lower().endswith(".prj") for nome in nomes)
    return shapefiles, possui_prj


def _extrair_shapefile_zip(caminho: Path, shp_nome: str | None = None) -> Path:
    """Extrai ZIP de shapefile para pasta temporaria e devolve o .shp escolhido."""
    destino = Path(tempfile.mkdtemp(prefix="ea2s_inventario_shp_"))
    with zipfile.ZipFile(caminho) as zf:
        zf.extractall(destino)
    shapefiles = sorted(destino.rglob("*.shp"))
    if not shapefiles:
        raise ValueError("ZIP nao contem arquivo .shp.")
    if shp_nome:
        for shp in shapefiles:
            if shp.as_posix().endswith(shp_nome.replace("\\", "/")) or shp.name == Path(shp_nome).name:
                escolhido = shp
                break
        else:
            escolhido = shapefiles[0]
    else:
        escolhido = shapefiles[0]
    for obrigatorio in (".dbf", ".shx"):
        if not escolhido.with_suffix(obrigatorio).exists():
            raise ValueError(f"Shapefile incompleto. Falta {obrigatorio}.")
    return escolhido


def ler_base_geografica_upload(caminho: Path, layer: str | None = None) -> gpd.GeoDataFrame:
    """Le a base enviada com GeoPandas, sem importar para o banco."""
    # Esta funcao apenas abre o arquivo local temporario para metadados e previa.
    # Importacao para staging/promocao oficial sera etapa posterior.
    formato = detectar_formato_arquivo(caminho)
    if formato == "gpkg":
        return gpd.read_file(caminho, layer=layer) if layer else gpd.read_file(caminho)
    if formato == "geojson":
        return gpd.read_file(caminho)
    if formato == "shapefile_zip":
        shp = _extrair_shapefile_zip(caminho, layer)
        return gpd.read_file(shp)
    if formato == "shapefile":
        return gpd.read_file(caminho)
    raise ValueError("Formato nao suportado. Use GPKG, GeoJSON, SHP ou SHP zipado.")


def sanitizar_nome_tabela(texto: str) -> str:
    """Gera nome tecnico seguro para sugestao de tabela destino."""
    normalizado = unicodedata.normalize("NFKD", str(texto or "base_geografica"))
    ascii_texto = normalizado.encode("ascii", "ignore").decode("ascii")
    nome = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_texto).strip("_").lower()
    nome = re.sub(r"_+", "_", nome)
    if not nome or nome in NOMES_GENERICOS_TABELA:
        nome = "base_geografica"
    if nome[0].isdigit():
        nome = f"t_{nome}"
    return nome[:60].strip("_") or "base_geografica"


def sugerir_metadados_base(nome_arquivo: str, campos: list[str]) -> dict[str, str]:
    """Sugere metadados iniciais a partir do nome do arquivo e dos campos."""
    alvo = " ".join([nome_arquivo or "", *[str(campo) for campo in campos]]).lower()
    alvo_norm = unicodedata.normalize("NFKD", alvo).encode("ascii", "ignore").decode("ascii")
    base = Path(nome_arquivo or "base_geografica").stem
    sugestao = {
        "grupo": "outros",
        "tema": sanitizar_nome_tabela(base),
        "subtema": "",
        "schema_destino_sugerido": "outros",
        "tabela_destino_sugerida": sanitizar_nome_tabela(base),
    }

    tem_valor = any(p in alvo_norm for p in ("valor_m2", "valor m2", "valor_venal", "valor venal", "vl_m2"))
    if any(p in alvo_norm for p in ("pgv", "cadastro imobiliario", "lote", "lotes", "parcelamento")):
        tema = "cadastro_imobiliario" if any(p in alvo_norm for p in ("pgv", "cadastro imobiliario", "valor")) else "parcelamento_solo"
        sugestao.update({
            "grupo": "urbano",
            "tema": tema,
            "subtema": "valor_m2_pgv" if tem_valor else "",
            "schema_destino_sugerido": "urbano",
            "tabela_destino_sugerida": "pgv_pmf_2023" if tem_valor or "pgv" in alvo_norm else "parcelamento_solo_pmf_2023",
        })
    elif "zoneamento" in alvo_norm:
        sugestao.update({"grupo": "urbano", "tema": "zoneamento", "schema_destino_sugerido": "urbano"})
    elif any(p in alvo_norm for p in ("risco", "cprm", "sgb")):
        sugestao.update({"grupo": "meio_fisico", "tema": "risco_geologico", "schema_destino_sugerido": "riscos"})
    elif any(p in alvo_norm for p in ("uc", "unidade conservacao", "unidade de conservacao", "icmbio")):
        sugestao.update({"grupo": "areas_protegidas", "tema": "unidades_conservacao", "schema_destino_sugerido": "areas_protegidas"})
    elif any(p in alvo_norm for p in ("car", "sicar")):
        sugestao.update({"grupo": "territorial", "tema": "car", "schema_destino_sugerido": "territorial"})
    elif any(p in alvo_norm for p in ("prodes", "desmatamento")):
        sugestao.update({"grupo": "meio_biotico", "tema": "desmatamento", "schema_destino_sugerido": "vegetacao"})

    tabela = sugestao.get("tabela_destino_sugerida") or ""
    if tabela in NOMES_GENERICOS_TABELA or tabela == "base_geografica":
        tabela = "_".join(v for v in (sugestao.get("tema"), sugestao.get("schema_destino_sugerido")) if v)
    sugestao["tabela_destino_sugerida"] = sanitizar_nome_tabela(tabela)
    return sugestao

def validar_base_geografica(gdf: gpd.GeoDataFrame, epsg_padrao: int | None = None) -> dict[str, Any]:
    """Valida CRS, geometria, campos e estatisticas basicas da base."""
    # CRS e obrigatorio para interpretar coordenadas. Area e comprimento sao
    # calculados apenas em CRS metrico, usando EPSG:31982 como referencia do MVP.
    tem_geometria = hasattr(gdf, "geometry") and gdf.geometry is not None
    tem_crs = bool(getattr(gdf, "crs", None))
    srid_detectado = int(gdf.crs.to_epsg()) if tem_crs and gdf.crs.to_epsg() else epsg_padrao
    campos = [{"nome_campo": str(coluna), "tipo_detectado": str(dtype)} for coluna, dtype in gdf.drop(columns=[gdf.geometry.name], errors="ignore").dtypes.items()]

    status = "valido"
    mensagens: list[str] = []
    tipo_geometria = "sem_geometria"
    bbox = None
    area_total_ha = None
    comprimento_total_km = None
    geometria_valida = False

    if not tem_geometria:
        status = "sem_geometria"
        mensagens.append("Base sem coluna geometrica.")
    else:
        geometrias = gdf.geometry.dropna()
        tipo_geometria = ", ".join(sorted({str(valor) for valor in geometrias.geom_type.unique()})) if not geometrias.empty else "sem_geometria"
        if geometrias.empty:
            status = "sem_geometria"
            mensagens.append("Base sem geometrias preenchidas.")
        else:
            invalidas = int((~geometrias.is_valid).sum())
            geometria_valida = invalidas == 0
            if invalidas:
                status = "geometria_invalida"
                mensagens.append(f"{invalidas} geometria(s) invalida(s). Correção fica para staging.")
            bbox = tuple(round(float(valor), 6) for valor in geometrias.total_bounds)

    if not tem_crs:
        if status == "valido":
            status = "revisar_crs"
        mensagens.append("CRS ausente. Informe EPSG manualmente antes de qualquer importacao.")

    if tem_geometria and not gdf.geometry.dropna().empty and (tem_crs or epsg_padrao):
        try:
            base = gdf.copy()
            if base.crs is None and epsg_padrao:
                base = base.set_crs(epsg=epsg_padrao, allow_override=True)
            metric = base.to_crs(epsg=31982)
            tipos = set(metric.geometry.dropna().geom_type.astype(str))
            if tipos & {"Polygon", "MultiPolygon"}:
                area_total_ha = float(metric.geometry.area.sum(skipna=True) / 10000.0)
            if tipos & {"LineString", "MultiLineString"}:
                comprimento_total_km = float(metric.geometry.length.sum(skipna=True) / 1000.0)
        except Exception as exc:
            mensagens.append(f"Nao foi possivel calcular area/comprimento em CRS metrico: {exc}")

    return {
        "crs_original": str(gdf.crs) if tem_crs else None,
        "srid_detectado": srid_detectado,
        "tipo_geometria": tipo_geometria,
        "numero_feicoes": int(len(gdf)),
        "numero_campos": int(len(gdf.columns)),
        "campos": campos,
        "bbox": bbox,
        "area_total_ha": area_total_ha,
        "comprimento_total_km": comprimento_total_km,
        "tem_geometria": bool(tem_geometria),
        "geometria_valida": bool(geometria_valida),
        "tem_crs": bool(tem_crs),
        "status_validacao": status,
        "mensagem_validacao": " ".join(mensagens) if mensagens else "Base valida para inventario.",
    }


def montar_inventario_base(
    gdf: gpd.GeoDataFrame,
    caminho: Path,
    formato: str,
    epsg_padrao: int | None = None,
    layer_name: str | None = None,
    nome_original_upload: str | None = None,
) -> dict[str, Any]:
    """Monta dicionario consolidado do inventario sem gravar no banco."""
    inventario = validar_base_geografica(gdf, epsg_padrao=epsg_padrao)
    inventario.update(
        {
            "formato": formato,
            "nome_arquivo": caminho.name,
            "nome_original_upload": nome_original_upload or caminho.name,
            "layer_name": layer_name,
            "hash_arquivo": calcular_hash_arquivo(caminho),
            "caminho_temporario": str(caminho),
            "tamanho_bytes": caminho.stat().st_size if caminho.exists() else None,
        }
    )
    return inventario


def buscar_inventarios_por_hash(hash_arquivo: str | None) -> QueryResult:
    """Busca inventarios ja registrados para o mesmo SHA256."""
    if not hash_arquivo:
        return QueryResult(True, pd.DataFrame(), "")
    try:
        return fetch_dataframe(
            """
            SELECT
                ia.id AS inventario_arquivo_id,
                ia.lote_id,
                ia.nome_arquivo,
                ia.layer_name,
                ia.hash_arquivo,
                left(ia.hash_arquivo, 12) AS hash_abreviado,
                ia.criado_em,
                li.nome_lote,
                li.status
            FROM importacao.inventario_arquivo AS ia
            INNER JOIN importacao.lote_importacao AS li
                ON li.id = ia.lote_id
            WHERE ia.hash_arquivo = %s
            ORDER BY ia.criado_em DESC;
            """,
            (hash_arquivo,),
        )
    except Exception as exc:
        return QueryResult(False, pd.DataFrame(), f"Não foi possível verificar duplicidade por hash: {exc}")

def validar_pronto_para_registro_inventario(
    nome_lote: str | None,
    grupo: str | None,
    tema: str | None,
    schema_destino_sugerido: str | None,
    tabela_destino_sugerida: str | None,
    confirmacao_registro: bool,
    duplicidade_bloqueante: bool = False,
    permitir_duplicado: bool = False,
    inventario_tecnico: dict[str, Any] | None = None,
    ja_registrado_sessao: bool = False,
) -> list[str]:
    """Retorna pendencias que impedem registrar inventario, sem bloquear por geometria invalida."""
    pendencias: list[str] = []
    if not inventario_tecnico:
        pendencias.append("A base ainda não foi lida ou o inventário técnico não foi montado.")
    else:
        tem_hash = bool(inventario_tecnico.get("hash_arquivo"))
        entrada_url = inventario_tecnico.get("formato") == "url"
        if not (tem_hash or entrada_url):
            pendencias.append("A base ainda não foi lida ou o inventário técnico não foi montado.")
    if not str(nome_lote or "").strip():
        pendencias.append("Preencha o nome do lote.")
    if not str(grupo or "").strip():
        pendencias.append("Informe o grupo.")
    if not str(tema or "").strip():
        pendencias.append("Informe o tema.")
    if not str(schema_destino_sugerido or "").strip():
        pendencias.append("Informe o schema destino sugerido.")
    if not str(tabela_destino_sugerida or "").strip():
        pendencias.append("Informe a tabela destino sugerida.")
    if not confirmacao_registro:
        pendencias.append("Marque a confirmação para registrar.")
    if ja_registrado_sessao:
        pendencias.append("Este arquivo já foi registrado nesta sessão. Recarregue outro arquivo para evitar clique duplo ou rerun duplicado.")
    if duplicidade_bloqueante and not permitir_duplicado:
        pendencias.append("Este arquivo já foi inventariado. Marque a opção de registrar mesmo assim para criar novo inventário.")
    return pendencias


def registrar_inventario_base(inventario: dict[str, Any], metadados: dict[str, Any]) -> tuple[int, int]:
    """Grava apenas o inventario em importacao.*, nunca em schemas oficiais."""
    # Inventariar e registrar metadados. Importar geometrias para staging e promover
    # para schema oficial sao fluxos separados, ainda futuros.
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO importacao.lote_importacao (
                        nome_lote,
                        tipo_lote,
                        origem,
                        responsavel,
                        status,
                        observacao
                    )
                    VALUES (%s, 'base_geografica', %s, %s, 'inventariado', %s)
                    RETURNING id;
                    """,
                    (
                        metadados["nome_lote"],
                        metadados.get("fonte"),
                        metadados.get("responsavel"),
                        metadados.get("observacao"),
                    ),
                )
                lote_id = int(cur.fetchone()[0])
                cur.execute(
                    """
                    INSERT INTO importacao.inventario_arquivo (
                        lote_id,
                        nome_arquivo,
                        formato,
                        caminho_temporario,
                        tamanho_bytes,
                        crs_original,
                        srid_detectado,
                        tipo_geometria,
                        numero_feicoes,
                        numero_campos,
                        campos,
                        bbox,
                        area_total_ha,
                        comprimento_total_km,
                        tem_geometria,
                        geometria_valida,
                        tem_crs,
                        mensagem_validacao,
                        status_validacao,
                        grupo_sugerido,
                        tema_sugerido,
                        subtema_sugerido,
                        schema_destino_sugerido,
                        tabela_destino_sugerida,
                        fonte,
                        orgao_produtor,
                        ano_referencia,
                        observacao,
                        hash_arquivo,
                        layer_name,
                        nome_original_upload,
                        registrado_por,
                        permitir_duplicado
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s
                    )
                    RETURNING id;
                    """,
                    (
                        lote_id,
                        inventario.get("nome_arquivo"),
                        inventario.get("formato"),
                        inventario.get("caminho_temporario"),
                        inventario.get("tamanho_bytes"),
                        inventario.get("crs_original"),
                        inventario.get("srid_detectado"),
                        inventario.get("tipo_geometria"),
                        inventario.get("numero_feicoes"),
                        inventario.get("numero_campos"),
                        json.dumps(inventario.get("campos") or [], ensure_ascii=False),
                        json.dumps(inventario.get("bbox"), ensure_ascii=False),
                        inventario.get("area_total_ha"),
                        inventario.get("comprimento_total_km"),
                        inventario.get("tem_geometria"),
                        inventario.get("geometria_valida"),
                        inventario.get("tem_crs"),
                        inventario.get("mensagem_validacao"),
                        inventario.get("status_validacao"),
                        metadados.get("grupo"),
                        metadados.get("tema"),
                        metadados.get("subtema"),
                        metadados.get("schema_destino"),
                        metadados.get("tabela_destino"),
                        metadados.get("fonte"),
                        metadados.get("orgao_produtor"),
                        metadados.get("ano_referencia"),
                        metadados.get("observacao"),
                        inventario.get("hash_arquivo"),
                        inventario.get("layer_name"),
                        inventario.get("nome_original_upload"),
                        metadados.get("responsavel"),
                        bool(metadados.get("permitir_duplicado")),
                    ),
                )
                inventario_id = int(cur.fetchone()[0])
            conn.commit()
            return lote_id, inventario_id
        except Exception:
            conn.rollback()
            raise

def carregar_inventarios_recentes() -> QueryResult:
    """Lista inventarios recentes se o script SQL 13/14 ja tiver sido aplicado."""
    if not view_existe("importacao.vw_inventario_bases_geograficas"):
        return QueryResult(False, pd.DataFrame(), "Aplique o script sql/13_inventario_bases_geograficas.sql para habilitar o histórico de inventários.")
    # A view de inventario pode expor datas especificas como arquivo_criado_em
    # e lote_criado_em. O app usa arquivo_criado_em como data principal e cria o
    # alias local criado_em apenas para exibicao na tabela de recentes.
    return fetch_dataframe(
        """
        SELECT
            lote_id,
            inventario_arquivo_id,
            nome_lote,
            nome_arquivo,
            nome_original_upload,
            left(hash_arquivo, 12) AS hash_abreviado,
            layer_name,
            grupo_sugerido,
            tema_sugerido,
            schema_destino_sugerido,
            tabela_destino_sugerida,
            status_validacao,
            arquivo_criado_em AS criado_em,
            status_lote,
            formato,
            srid_detectado,
            tipo_geometria,
            numero_feicoes,
            numero_campos,
            area_total_ha,
            comprimento_total_km,
            tem_geometria,
            geometria_valida,
            tem_crs,
            mensagem_validacao,
            subtema_sugerido,
            fonte,
            orgao_produtor,
            ano_referencia,
            registrado_por,
            permitir_duplicado
        FROM importacao.vw_inventario_bases_geograficas
        ORDER BY arquivo_criado_em DESC
        LIMIT 20;
        """
    )


def montar_inventario_url(url: str) -> dict[str, Any]:
    """Monta inventario pendente para URL sem baixar o arquivo automaticamente."""
    nome = url.rstrip("/").split("/")[-1] or "base_url"
    return {
        "formato": "url",
        "nome_arquivo": nome,
        "nome_original_upload": url,
        "layer_name": None,
        "hash_arquivo": None,
        "caminho_temporario": url,
        "tamanho_bytes": None,
        "crs_original": None,
        "srid_detectado": None,
        "tipo_geometria": None,
        "numero_feicoes": None,
        "numero_campos": None,
        "campos": [],
        "bbox": None,
        "area_total_ha": None,
        "comprimento_total_km": None,
        "tem_geometria": None,
        "geometria_valida": None,
        "tem_crs": None,
        "status_validacao": "pendente",
        "mensagem_validacao": "URL registrada para inventario. O download automatico sera consolidado em etapa futura.",
    }


def _nome_atributo_normalizado(nome: Any) -> str:
    """Remove acentos e padroniza nome de campo para regras de inferencia."""
    texto = unicodedata.normalize("NFKD", str(nome or ""))
    return texto.encode("ascii", "ignore").decode("ascii").lower()


def _valor_para_numero(valor: Any) -> float | None:
    """Converte textos numericos comuns, sem modificar o dado original."""
    if pd.isna(valor):
        return None
    texto = str(valor).strip()
    if not texto:
        return None
    texto = texto.replace("R$", "").replace("$", "").replace("%", "").replace(" ", "")
    texto = re.sub(r"[^0-9,\.\-]", "", texto)
    if not texto or texto in {"-", ".", ","}:
        return None
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def _serie_para_numero(serie: pd.Series) -> pd.Series:
    """Retorna copia numerica da serie, preservando nulos como nulos."""
    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_numeric(serie, errors="coerce")
    return serie.map(_valor_para_numero).astype("float64")


def _nome_indica_codigo(nome: str) -> bool:
    """Reconhece campos que representam identificadores ou codigos."""
    return (
        nome in {"id", "fid", "gid", "objectid", "mslink", "cod"}
        or nome.startswith(("cd_", "cod", "id_"))
        or nome.endswith("_id")
        or any(p in nome for p in ("codigo", "setor", "quadra", "lote", "inscricao", "matricula"))
    )


def _nome_indica_booleano(nome: str) -> bool:
    """Booleano so e sugerido quando o nome tambem indica flag/binario."""
    return any(p in nome for p in ("flag", "ativo", "inativo", "bool", "boolean", "controle", "validado", "selecionado")) or nome in {"sim", "nao", "não"}


def _nome_indica_data(nome: str) -> bool:
    """Reconhece nomes que normalmente guardam data ou data de cadastro."""
    return any(p in nome for p in ("data", "date", "dt_", "dt", "cadastr", "cadastro", "atualizacao", "atualizacao"))


def _serie_tem_padrao_data_textual(serie: pd.Series, permitir_ano_puro: bool = False) -> pd.Series:
    """Marca valores que parecem datas textuais, evitando numeros puros soltos."""
    texto = serie.astype(str).str.strip()
    padrao_data = (
        texto.str.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}(\s+\d{1,2}:\d{2}(:\d{2}(\.\d+)?)?)?$", na=False)
        | texto.str.match(r"^\d{1,2}/\d{1,2}/\d{2,4}$", na=False)
        | texto.str.match(r"^\d{1,2}/\d{4}$", na=False)
    )
    if permitir_ano_puro:
        padrao_data = padrao_data | texto.str.match(r"^(19|20)\d{2}$", na=False)
    return padrao_data


def _serie_numerica_pura(serie: pd.Series) -> bool:
    """Identifica series numericas ou texto numerico sem padrao textual de data."""
    if pd.api.types.is_numeric_dtype(serie):
        return True
    texto = serie.dropna().astype(str).str.strip()
    if texto.empty:
        return False
    return bool(texto.str.match(r"^-?\d+([\.,]\d+)?$", na=False).all())


def _converter_data_segura(serie: pd.Series, nome: str) -> pd.Series:
    """Converte apenas valores com padrao textual de data; numeros puros ficam nulos."""
    if pd.api.types.is_numeric_dtype(serie):
        return pd.Series(pd.NaT, index=serie.index, dtype="datetime64[ns]")
    texto = serie.astype(str).str.strip()
    mascara = _serie_tem_padrao_data_textual(serie, permitir_ano_puro=_nome_indica_data(nome))
    convertida = pd.Series(pd.NaT, index=serie.index, dtype="datetime64[ns]")
    convertida.loc[mascara] = pd.to_datetime(texto.loc[mascara], errors="coerce", dayfirst=True)
    return convertida


def _tipo_efetivo_perfil(perfil: pd.Series) -> str:
    """Usa tipo_confirmado quando preenchido; senao usa tipo_sugerido."""
    confirmado = perfil.get("tipo_confirmado")
    if pd.notna(confirmado) and str(confirmado).strip():
        return str(confirmado).strip()
    sugerido = perfil.get("tipo_sugerido")
    return str(sugerido).strip() if pd.notna(sugerido) else "texto"


def inferir_tipo_campo(serie: pd.Series) -> dict[str, Any]:
    """Sugere tipo tecnico de um campo para revisao antes de staging/exportacao."""
    nome = _nome_atributo_normalizado(serie.name)
    total = int(len(serie))
    nao_nulos_serie = serie.dropna()
    nao_nulos = int(len(nao_nulos_serie))
    nulos = total - nao_nulos
    valores_unicos = int(nao_nulos_serie.astype(str).str.strip().nunique()) if nao_nulos else 0
    exemplos = [str(valor) for valor in nao_nulos_serie.astype(str).head(10).tolist()]
    resultado: dict[str, Any] = {
        "tipo_sugerido": "ignorar" if nao_nulos == 0 else "texto",
        "percentual_conversao": None,
        "min_num": None,
        "max_num": None,
        "media_num": None,
        "min_data": None,
        "max_data": None,
        "total_registros": total,
        "nulos": nulos,
        "nao_nulos": nao_nulos,
        "valores_unicos": valores_unicos,
        "exemplos_valores": exemplos,
    }
    if nao_nulos == 0:
        return resultado

    texto = nao_nulos_serie.astype(str).str.strip()
    nome_codigo = _nome_indica_codigo(nome)
    codigo_por_valor = bool(texto.str.match(r"^0\d+", na=False).any()) or bool(texto.str.len().median() >= 12 and valores_unicos > max(20, nao_nulos * 0.5))

    numeros = _serie_para_numero(nao_nulos_serie)
    pct_num = float(numeros.notna().sum() / nao_nulos * 100.0) if nao_nulos else 0.0
    if pct_num >= 80.0:
        nums = numeros.dropna()
        resultado.update({
            "percentual_conversao": round(pct_num, 4),
            "min_num": float(nums.min()) if not nums.empty else None,
            "max_num": float(nums.max()) if not nums.empty else None,
            "media_num": float(nums.mean()) if not nums.empty else None,
        })
        valores_num = set(nums.dropna().astype(float).unique())
        if nome_codigo or codigo_por_valor:
            resultado["tipo_sugerido"] = "codigo"
        elif _nome_indica_booleano(nome) and valores_num.issubset({0.0, 1.0}):
            resultado["tipo_sugerido"] = "booleano"
        elif any(p in nome for p in ("valor", "valor_", "vl_", "preco", "preco", "renda")) or texto.str.contains("R$", regex=False).any() or texto.str.contains("$", regex=False).any():
            resultado["tipo_sugerido"] = "monetario"
        elif any(p in nome for p in ("percentual", "percent", "perc", "taxa", "tx_")) or texto.str.contains("%", regex=False).any():
            resultado["tipo_sugerido"] = "percentual"
        elif (nums % 1 == 0).all():
            resultado["tipo_sugerido"] = "inteiro"
        else:
            resultado["tipo_sugerido"] = "decimal"
        return resultado

    valores_bool = {v.lower() for v in texto.unique()}
    mapa_bool = {"true", "false", "sim", "nao", "não", "s", "n", "yes", "no", "verdadeiro", "falso", "0", "1"}
    if _nome_indica_booleano(nome) and not nome_codigo and valores_bool and valores_bool.issubset(mapa_bool) and valores_unicos <= 4:
        resultado["tipo_sugerido"] = "booleano"
        resultado["percentual_conversao"] = 100.0
        return resultado

    datas = _converter_data_segura(nao_nulos_serie, nome)
    pct_data = float(datas.notna().sum() / nao_nulos * 100.0) if nao_nulos else 0.0
    tem_padrao_data = bool(_serie_tem_padrao_data_textual(nao_nulos_serie, permitir_ano_puro=_nome_indica_data(nome)).mean() >= 0.8)
    if pct_data >= 80.0 and tem_padrao_data and not nome_codigo and not _serie_numerica_pura(nao_nulos_serie):
        resultado.update({
            "tipo_sugerido": "data",
            "percentual_conversao": round(pct_data, 4),
            "min_data": datas.min().isoformat() if datas.notna().any() else None,
            "max_data": datas.max().isoformat() if datas.notna().any() else None,
        })
        return resultado

    nome_categoria = any(p in nome for p in ("nm_", "nome", "classe", "tipo", "zona", "categoria", "uso"))
    valores_curto = texto.str.len().median() <= 80
    if nome_categoria and valores_curto and valores_unicos <= max(60, int(nao_nulos * 0.5)):
        resultado["tipo_sugerido"] = "categoria"
    elif valores_curto and valores_unicos <= max(30, int(nao_nulos * 0.2)):
        resultado["tipo_sugerido"] = "categoria"
    else:
        resultado["tipo_sugerido"] = "texto"
    resultado["percentual_conversao"] = round(max(pct_num, pct_data), 4)
    return resultado

def _categoria_uso_padrao(tipo_sugerido: str) -> str:
    """Define categoria de uso inicial para revisao no data_editor."""
    if tipo_sugerido == "ignorar":
        return "ignorar"
    if tipo_sugerido == "codigo":
        return "identificador"
    if tipo_sugerido == "categoria":
        return "classificacao"
    if tipo_sugerido in {"inteiro", "decimal", "monetario", "percentual"}:
        return "medida"
    if tipo_sugerido == "data":
        return "temporal"
    return "descricao"


def inferir_perfil_atributos(df: pd.DataFrame) -> pd.DataFrame:
    """Gera perfil editavel dos atributos, sem alterar o DataFrame original."""
    if isinstance(df, gpd.GeoDataFrame):
        df = pd.DataFrame(df.drop(columns=df.geometry.name, errors="ignore"))
    registros: list[dict[str, Any]] = []
    for coluna in df.columns:
        perfil = inferir_tipo_campo(df[coluna])
        tipo = perfil["tipo_sugerido"]
        registros.append({
            "nome_campo": str(coluna),
            "tipo_original": str(df[coluna].dtype),
            "tipo_sugerido": tipo,
            "tipo_confirmado": tipo,
            "categoria_uso": _categoria_uso_padrao(tipo),
            "total_registros": perfil["total_registros"],
            "nulos": perfil["nulos"],
            "nao_nulos": perfil["nao_nulos"],
            "valores_unicos": perfil["valores_unicos"],
            "exemplos_valores": perfil["exemplos_valores"],
            "percentual_conversao": perfil["percentual_conversao"],
            "min_num": perfil["min_num"],
            "max_num": perfil["max_num"],
            "media_num": perfil["media_num"],
            "min_data": perfil["min_data"],
            "max_data": perfil["max_data"],
            "usar_dashboard": tipo not in {"ignorar", "texto"},
            "usar_grafico": tipo != "ignorar",
            "usar_mapa_popup": tipo in {"codigo", "categoria", "texto", "monetario", "percentual"},
            "usar_exportacao": tipo != "ignorar",
            "observacao": "",
        })
    return pd.DataFrame(registros)


def aplicar_conversoes_para_visualizacao(df: pd.DataFrame, perfil_df: pd.DataFrame | None) -> pd.DataFrame:
    """Converte uma copia para graficos/estatisticas, preservando fonte e banco."""
    data = df.copy()
    if perfil_df is None or perfil_df.empty:
        return data
    for _, perfil in perfil_df.iterrows():
        coluna = perfil.get("nome_campo")
        if coluna not in data.columns:
            continue
        tipo = _tipo_efetivo_perfil(perfil)
        if tipo == "ignorar":
            continue
        if tipo == "inteiro":
            data[coluna] = _serie_para_numero(data[coluna]).round().astype("Int64")
        elif tipo in {"decimal", "monetario", "percentual"}:
            data[coluna] = _serie_para_numero(data[coluna])
        elif tipo == "data":
            data[coluna] = _converter_data_segura(data[coluna], _nome_atributo_normalizado(coluna))
        elif tipo == "booleano":
            texto = data[coluna].astype(str).str.strip().str.lower()
            compativeis = {"true", "false", "sim", "nao", "não", "s", "n", "yes", "no", "verdadeiro", "falso", "1", "0"}
            valores = set(texto[data[coluna].notna()].unique())
            if valores and valores.issubset(compativeis):
                data[coluna] = texto.map({
                    "true": True,
                    "sim": True,
                    "s": True,
                    "yes": True,
                    "verdadeiro": True,
                    "1": True,
                    "false": False,
                    "nao": False,
                    "não": False,
                    "n": False,
                    "no": False,
                    "falso": False,
                    "0": False,
                })
            else:
                data[coluna] = data[coluna].where(data[coluna].isna(), data[coluna].astype(str))
        elif tipo in {"codigo", "categoria", "texto"}:
            data[coluna] = data[coluna].where(data[coluna].isna(), data[coluna].astype(str))
    return data

def carregar_perfil_atributos(conn: Any, inventario_arquivo_id: int) -> pd.DataFrame:
    """Carrega perfil confirmado para reuso em dashboard, exportacoes e staging."""
    return pd.read_sql_query(
        """
        SELECT *
        FROM importacao.perfil_atributo
        WHERE inventario_arquivo_id = %s
        ORDER BY nome_campo;
        """,
        conn,
        params=(int(inventario_arquivo_id),),
    )


def preparar_dataframe_para_visualizacao(df: pd.DataFrame, perfil_atributos: pd.DataFrame | None) -> pd.DataFrame:
    """Prepara copia tabular usando tipos confirmados ou sugeridos no perfil."""
    return aplicar_conversoes_para_visualizacao(df, perfil_atributos)


def salvar_perfil_atributos(inventario_arquivo_id: int, perfil_df: pd.DataFrame) -> tuple[bool, str]:
    """Grava perfis em importacao.perfil_atributo com upsert por inventario/campo."""
    if perfil_df is None or perfil_df.empty:
        return False, "Perfil de atributos vazio."
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                for _, row in perfil_df.iterrows():
                    exemplos = row.get("exemplos_valores") if isinstance(row.get("exemplos_valores"), list) else []
                    cur.execute(
                        """
                        INSERT INTO importacao.perfil_atributo (
                            inventario_arquivo_id, nome_campo, tipo_original, tipo_sugerido,
                            tipo_confirmado, categoria_uso, total_registros, nulos, nao_nulos,
                            valores_unicos, exemplos_valores, percentual_conversao, min_num,
                            max_num, media_num, min_data, max_data, usar_dashboard, usar_grafico,
                            usar_mapa_popup, usar_exportacao, observacao, atualizado_em
                        )
                        VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s::jsonb, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, now()
                        )
                        ON CONFLICT (inventario_arquivo_id, nome_campo) DO UPDATE SET
                            tipo_original = EXCLUDED.tipo_original,
                            tipo_sugerido = EXCLUDED.tipo_sugerido,
                            tipo_confirmado = EXCLUDED.tipo_confirmado,
                            categoria_uso = EXCLUDED.categoria_uso,
                            total_registros = EXCLUDED.total_registros,
                            nulos = EXCLUDED.nulos,
                            nao_nulos = EXCLUDED.nao_nulos,
                            valores_unicos = EXCLUDED.valores_unicos,
                            exemplos_valores = EXCLUDED.exemplos_valores,
                            percentual_conversao = EXCLUDED.percentual_conversao,
                            min_num = EXCLUDED.min_num,
                            max_num = EXCLUDED.max_num,
                            media_num = EXCLUDED.media_num,
                            min_data = EXCLUDED.min_data,
                            max_data = EXCLUDED.max_data,
                            usar_dashboard = EXCLUDED.usar_dashboard,
                            usar_grafico = EXCLUDED.usar_grafico,
                            usar_mapa_popup = EXCLUDED.usar_mapa_popup,
                            usar_exportacao = EXCLUDED.usar_exportacao,
                            observacao = EXCLUDED.observacao,
                            atualizado_em = now();
                        """,
                        (
                            int(inventario_arquivo_id),
                            row.get("nome_campo"),
                            row.get("tipo_original"),
                            row.get("tipo_sugerido"),
                            row.get("tipo_confirmado"),
                            row.get("categoria_uso"),
                            int(row.get("total_registros") or 0),
                            int(row.get("nulos") or 0),
                            int(row.get("nao_nulos") or 0),
                            int(row.get("valores_unicos") or 0),
                            json.dumps(exemplos, ensure_ascii=False),
                            row.get("percentual_conversao") if pd.notna(row.get("percentual_conversao")) else None,
                            row.get("min_num") if pd.notna(row.get("min_num")) else None,
                            row.get("max_num") if pd.notna(row.get("max_num")) else None,
                            row.get("media_num") if pd.notna(row.get("media_num")) else None,
                            row.get("min_data") if pd.notna(row.get("min_data")) else None,
                            row.get("max_data") if pd.notna(row.get("max_data")) else None,
                            bool(row.get("usar_dashboard")),
                            bool(row.get("usar_grafico")),
                            bool(row.get("usar_mapa_popup")),
                            bool(row.get("usar_exportacao")),
                            row.get("observacao") if pd.notna(row.get("observacao")) else None,
                        ),
                    )
            conn.commit()
            return True, "Perfil de atributos salvo."
        except Exception as exc:
            conn.rollback()
            return False, f"Não foi possível salvar perfil de atributos: {exc}"

def _campo_texto_curto(data: pd.DataFrame, coluna: str) -> bool:
    """Identifica campos textuais que ainda funcionam bem como categoria visual."""
    if coluna not in data.columns:
        return False
    serie = data[coluna].dropna().astype(str).str.strip()
    if serie.empty:
        return False
    limite_cardinalidade = max(30, int(len(serie) * 0.35))
    return bool(serie.str.len().median() <= 80 and serie.nunique() <= limite_cardinalidade)


def _nome_indica_rotulo(nome: str) -> bool:
    """Reconhece campos bons para rotulo, hover e identificacao visual."""
    return (
        nome in {"id", "label"}
        or nome.startswith(("nm_", "nome", "desc", "descr", "classe", "tipo", "zona", "uso", "categoria", "cd_", "cod"))
        or any(p in nome for p in ("nome", "descricao", "descrição", "classe", "tipo", "zona", "uso", "categoria", "label", "codigo"))
    )


def classificar_colunas_inventario(data: pd.DataFrame, perfil_df: pd.DataFrame | None = None) -> dict[str, list[str]]:
    """Classifica colunas para eixos, cor, rotulo e hover no Explorador Grafico."""
    tipos_por_coluna: dict[str, str] = {}
    if perfil_df is not None and not perfil_df.empty:
        for _, perfil in perfil_df.iterrows():
            coluna = perfil.get("nome_campo")
            if coluna in data.columns:
                tipos_por_coluna[str(coluna)] = _tipo_efetivo_perfil(perfil)

    classes: dict[str, list[str]] = {
        "colunas_numericas": [],
        "colunas_categoricas": [],
        "colunas_datas": [],
        "colunas_codigo": [],
        "colunas_texto": [],
        "colunas_booleanas": [],
        "todas_colunas": [],
        "colunas_texto_curto": [],
        "colunas_rotulo": [],
    }

    for col in data.columns:
        tipo = tipos_por_coluna.get(str(col))
        nome = _nome_atributo_normalizado(col)
        if tipo == "ignorar":
            continue

        classes["todas_colunas"].append(col)
        texto_curto = _campo_texto_curto(data, col)
        if texto_curto:
            classes["colunas_texto_curto"].append(col)
        if _nome_indica_rotulo(nome):
            classes["colunas_rotulo"].append(col)

        if tipo == "codigo" or _nome_indica_codigo(nome):
            classes["colunas_codigo"].append(col)
        elif tipo == "booleano" or pd.api.types.is_bool_dtype(data[col]):
            classes["colunas_booleanas"].append(col)
        elif tipo == "data" or pd.api.types.is_datetime64_any_dtype(data[col]):
            classes["colunas_datas"].append(col)
        elif tipo in {"inteiro", "decimal", "monetario", "percentual"} or pd.api.types.is_numeric_dtype(data[col]):
            classes["colunas_numericas"].append(col)
        elif tipo == "categoria":
            classes["colunas_categoricas"].append(col)
        else:
            classes["colunas_texto"].append(col)
            if texto_curto:
                classes["colunas_categoricas"].append(col)

    for chave, valores in classes.items():
        classes[chave] = list(dict.fromkeys(valores))
    return classes


def colunas_por_tipo_inventario(data: pd.DataFrame) -> tuple[list[str], list[str], list[str]]:
    """Mantem compatibilidade com chamadas antigas que esperam tres listas."""
    classes = classificar_colunas_inventario(data)
    return classes["colunas_numericas"], classes["colunas_categoricas"], classes["colunas_datas"]


def _selectbox_opcional(label: str, opcoes: list[str], key: str, preferida: str | None = None) -> str | None:
    valores = ["Nenhum"] + list(dict.fromkeys(opcoes))
    index = valores.index(preferida) if preferida in valores else 0
    escolha = st.selectbox(label, valores, index=index, key=key)
    return None if escolha == "Nenhum" else escolha


def _multiselect_opcional(label: str, opcoes: list[str], key: str, padrao: list[str] | None = None) -> list[str]:
    padrao_valido = [valor for valor in (padrao or []) if valor in opcoes]
    return st.multiselect(label, opcoes, default=padrao_valido, key=key)


def _primeira_coluna(opcoes: list[str], excluir: str | None = None) -> str | None:
    for coluna in opcoes:
        if coluna != excluir:
            return coluna
    return None


def _classes_para_grafico(data: pd.DataFrame, perfil_df: pd.DataFrame | None) -> dict[str, list[str]]:
    classes = classificar_colunas_inventario(data, perfil_df)
    classes["colunas_agrupamento"] = list(dict.fromkeys(
        classes["colunas_categoricas"]
        + classes["colunas_codigo"]
        + classes["colunas_texto_curto"]
        + classes["colunas_booleanas"]
    ))
    classes["colunas_ordenaveis"] = list(dict.fromkeys(
        classes["colunas_datas"] + classes["colunas_numericas"] + classes["colunas_codigo"] + classes["colunas_categoricas"]
    ))
    classes["colunas_rotulo"] = list(dict.fromkeys(classes["colunas_rotulo"] + classes["colunas_codigo"] + classes["colunas_texto_curto"]))
    return classes


def sugerir_colunas_grafico(df: pd.DataFrame, perfil_df: pd.DataFrame | None, tipo_grafico: str) -> dict[str, Any]:
    """Sugere defaults uteis, sem impedir ajuste manual pelo usuario."""
    classes = _classes_para_grafico(df, perfil_df)
    numericas = classes["colunas_numericas"]
    agrupaveis = classes["colunas_agrupamento"]
    datas = classes["colunas_datas"]
    ordenaveis = classes["colunas_ordenaveis"]
    rotulos = classes["colunas_rotulo"]

    sugestao: dict[str, Any] = {
        "eixo_x": None,
        "eixo_y": None,
        "cor": _primeira_coluna(agrupaveis),
        "rotulo": _primeira_coluna(rotulos),
        "hover": list(dict.fromkeys((rotulos[:3] + agrupaveis[:3] + numericas[:3])))[:8],
        "tamanho": None,
        "valor": _primeira_coluna(numericas),
        "hierarquia_1": _primeira_coluna(agrupaveis),
        "hierarquia_2": _primeira_coluna(agrupaveis, excluir=_primeira_coluna(agrupaveis)),
        "facet": None,
    }

    if tipo_grafico == "Dispersão":
        sugestao["eixo_x"] = _primeira_coluna(numericas)
        sugestao["eixo_y"] = _primeira_coluna(numericas, excluir=sugestao["eixo_x"])
        sugestao["tamanho"] = None
    elif tipo_grafico == "Linha":
        sugestao["eixo_x"] = _primeira_coluna(datas + ordenaveis)
        sugestao["eixo_y"] = _primeira_coluna(numericas)
    elif tipo_grafico == "Área":
        sugestao["eixo_x"] = _primeira_coluna(datas + ordenaveis)
        sugestao["eixo_y"] = _primeira_coluna(numericas)
    elif tipo_grafico == "Barra":
        sugestao["eixo_x"] = _primeira_coluna(agrupaveis + datas)
        sugestao["eixo_y"] = None
        sugestao["valor"] = None
    elif tipo_grafico == "Barra horizontal":
        sugestao["eixo_y"] = _primeira_coluna(agrupaveis)
        sugestao["eixo_x"] = None
        sugestao["valor"] = None
    elif tipo_grafico == "Histograma":
        sugestao["eixo_x"] = _primeira_coluna(numericas + datas + agrupaveis)
        sugestao["valor"] = None
    elif tipo_grafico in {"Box plot", "Violino"}:
        sugestao["eixo_x"] = _primeira_coluna(agrupaveis)
        sugestao["eixo_y"] = _primeira_coluna(numericas)
    elif tipo_grafico == "Heatmap 2D":
        sugestao["eixo_x"] = _primeira_coluna(numericas)
        sugestao["eixo_y"] = _primeira_coluna(numericas, excluir=sugestao["eixo_x"])
    elif tipo_grafico in {"Treemap", "Sunburst"}:
        sugestao["eixo_x"] = None
        sugestao["eixo_y"] = None
        sugestao["valor"] = None
    elif tipo_grafico == "Pizza":
        sugestao["eixo_x"] = _primeira_coluna(agrupaveis)
        sugestao["valor"] = None
    return sugestao


def validar_configuracao_grafico(
    tipo_grafico: str,
    eixo_x: str | None,
    eixo_y: str | None,
    cor: str | None,
    valor: str | None,
    modo_selecao: str,
    df: pd.DataFrame,
) -> tuple[bool, str]:
    """Valida a configuracao antes do Plotly para evitar quebra da interface."""
    del cor
    colunas = set(df.columns)
    selecionadas = [col for col in (eixo_x, eixo_y, valor) if col]
    inexistentes = [col for col in selecionadas if col not in colunas]
    if inexistentes:
        return False, f"Campo inexistente no DataFrame: {', '.join(inexistentes)}."
    if valor and not pd.api.types.is_numeric_dtype(df[valor]):
        return False, "A coluna de valor precisa ser numérica. Use contagem automática ou escolha outro campo."
    if tipo_grafico in {"Linha", "Área", "Box plot", "Violino"}:
        if not eixo_y:
            return False, "Este tipo de gráfico precisa de um eixo Y numérico."
        if not pd.api.types.is_numeric_dtype(df[eixo_y]):
            return False, "O eixo Y precisa ser numérico para este tipo de gráfico."
    if tipo_grafico in {"Barra", "Histograma", "Pizza"} and not eixo_x:
        return False, "Escolha uma coluna de categoria ou eixo X para montar este gráfico."
    if tipo_grafico == "Barra horizontal" and not eixo_y:
        return False, "Escolha uma coluna de categoria no eixo Y para montar a barra horizontal."
    if tipo_grafico in {"Dispersão", "Heatmap 2D"}:
        if not eixo_x or not eixo_y:
            return False, "Este tipo de gráfico exige duas colunas numéricas compatíveis."
        if not pd.api.types.is_numeric_dtype(df[eixo_x]) or not pd.api.types.is_numeric_dtype(df[eixo_y]):
            return False, "Eixo X e eixo Y precisam ser numéricos para este tipo de gráfico."
        if eixo_x == eixo_y and modo_selecao == "Recomendado":
            return False, "Eixo X e eixo Y estão iguais. Escolha campos diferentes para um gráfico de dispersão mais útil."
        if eixo_x == eixo_y:
            return True, "Eixo X e eixo Y estão iguais. Escolha campos diferentes para um gráfico de dispersão mais útil."
    return True, ""


def _opcoes_por_modo(classes: dict[str, list[str]], modo_selecao: str, recomendadas: list[str]) -> list[str]:
    if modo_selecao == "Avançado":
        return classes["todas_colunas"]
    return list(dict.fromkeys(recomendadas))


def _agrupar_contagem(df: pd.DataFrame, grupos: list[str]) -> pd.DataFrame:
    """Cria contagem automatica para graficos quando nao ha medida numerica escolhida."""
    grupos_validos = [grupo for grupo in dict.fromkeys(grupos) if grupo and grupo in df.columns]
    if not grupos_validos:
        return df.assign(contagem=len(df))
    return df.groupby(grupos_validos, dropna=False).size().reset_index(name="contagem")


def _parametros_comuns_plotly(
    df_plot: pd.DataFrame,
    campo_cor: str | None,
    campos_hover: list[str],
    campo_rotulo: str | None,
    campo_facet: str | None,
    incluir_texto: bool = False,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if campo_cor in df_plot.columns:
        params["color"] = campo_cor
    hovers = [campo for campo in campos_hover if campo in df_plot.columns]
    if hovers:
        params["hover_data"] = hovers
    if incluir_texto and campo_rotulo in df_plot.columns:
        params["text"] = campo_rotulo
    if campo_facet in df_plot.columns:
        params["facet_col"] = campo_facet
    return params


def renderizar_grafico_exploratorio_inventario(
    gdf: gpd.GeoDataFrame,
    contexto: str,
    nome_arquivo: str | None = None,
    layer_name: str | None = None,
    perfil_df: pd.DataFrame | None = None,
) -> None:
    """Mostra graficos Plotly para explorar atributos do arquivo enviado."""
    # O grafico exploratorio serve apenas para analise visual inicial dos
    # atributos da base inventariada. Ele nao substitui o processamento espacial
    # oficial no PostGIS nem valida a promocao da base para schemas oficiais.
    st.markdown("#### Gráfico exploratório")
    atributos = pd.DataFrame(gdf.drop(columns=gdf.geometry.name, errors="ignore"))
    if atributos.empty:
        st.info("A base não possui atributos tabulares para gráfico exploratório.")
        return

    data_plot = preparar_dataframe_para_visualizacao(atributos, perfil_df)
    if perfil_df is None or perfil_df.empty:
        for coluna in data_plot.columns:
            if pd.api.types.is_numeric_dtype(data_plot[coluna]):
                continue
            convertida = _converter_data_segura(data_plot[coluna], _nome_atributo_normalizado(coluna))
            if convertida.notna().sum() >= max(3, int(data_plot[coluna].notna().sum() * 0.8)):
                data_plot[coluna] = convertida

    tipo_grafico = st.selectbox("Tipo de gráfico", GRAFICOS_INVENTARIO, key=make_key(contexto, "tipo_grafico"))
    modo_selecao = st.radio(
        "Modo de seleção das colunas",
        ["Recomendado", "Avançado"],
        horizontal=True,
        key=make_key(contexto, tipo_grafico, "modo_selecao"),
    )
    if modo_selecao == "Avançado":
        # O modo avancado existe para permitir investigacao livre, mesmo quando a
        # combinacao nao e a recomendada para o tipo de grafico escolhido.
        st.caption("Modo avançado: algumas combinações podem não gerar gráficos úteis. O sistema tentará validar antes de plotar.")

    classes = _classes_para_grafico(data_plot, perfil_df)
    numericas = classes["colunas_numericas"]
    agrupaveis = classes["colunas_agrupamento"]
    datas = classes["colunas_datas"]
    codigos = classes["colunas_codigo"]
    textos = classes["colunas_texto"]
    texto_curto = classes["colunas_texto_curto"]
    booleanas = classes["colunas_booleanas"]
    ordenaveis = classes["colunas_ordenaveis"]
    todas_colunas = classes["todas_colunas"]
    sugestao = sugerir_colunas_grafico(data_plot, perfil_df, tipo_grafico)

    eixo_x: str | None = None
    eixo_y: str | None = None
    hierarquia_1: str | None = None
    hierarquia_2: str | None = None
    coluna_valor: str | None = None

    # Eixo X/Y posiciona os dados no grafico. Campos de nome e descricao ficam
    # preferencialmente em rotulo/hover, porque nao sao eixos numericos uteis em
    # graficos como dispersao e heatmap.
    if tipo_grafico == "Histograma":
        opcoes_x = _opcoes_por_modo(classes, modo_selecao, numericas + datas + agrupaveis)
        eixo_x = st.selectbox("Eixo X", opcoes_x, index=opcoes_x.index(sugestao["eixo_x"]) if sugestao["eixo_x"] in opcoes_x else 0, key=make_key(contexto, tipo_grafico, modo_selecao, "x")) if opcoes_x else None
    elif tipo_grafico == "Barra":
        opcoes_x = _opcoes_por_modo(classes, modo_selecao, agrupaveis + datas)
        eixo_x = st.selectbox("Eixo X", opcoes_x, index=opcoes_x.index(sugestao["eixo_x"]) if sugestao["eixo_x"] in opcoes_x else 0, key=make_key(contexto, tipo_grafico, modo_selecao, "x")) if opcoes_x else None
        eixo_y = _selectbox_opcional("Eixo Y", numericas if modo_selecao == "Recomendado" else todas_colunas, make_key(contexto, tipo_grafico, modo_selecao, "y"), sugestao["eixo_y"])
    elif tipo_grafico == "Barra horizontal":
        opcoes_y = _opcoes_por_modo(classes, modo_selecao, agrupaveis)
        eixo_y = st.selectbox("Eixo Y", opcoes_y, index=opcoes_y.index(sugestao["eixo_y"]) if sugestao["eixo_y"] in opcoes_y else 0, key=make_key(contexto, tipo_grafico, modo_selecao, "y")) if opcoes_y else None
        eixo_x = _selectbox_opcional("Eixo X", numericas if modo_selecao == "Recomendado" else todas_colunas, make_key(contexto, tipo_grafico, modo_selecao, "x"), sugestao["eixo_x"])
    elif tipo_grafico in {"Linha", "Área"}:
        opcoes_x = _opcoes_por_modo(classes, modo_selecao, datas + ordenaveis)
        eixo_x = st.selectbox("Eixo X", opcoes_x, index=opcoes_x.index(sugestao["eixo_x"]) if sugestao["eixo_x"] in opcoes_x else 0, key=make_key(contexto, tipo_grafico, modo_selecao, "x")) if opcoes_x else None
        eixo_y = st.selectbox("Eixo Y", numericas if modo_selecao == "Recomendado" else todas_colunas, index=0, key=make_key(contexto, tipo_grafico, modo_selecao, "y")) if (numericas or modo_selecao == "Avançado") else None
    elif tipo_grafico == "Dispersão":
        opcoes_xy = _opcoes_por_modo(classes, modo_selecao, numericas)
        eixo_x = st.selectbox("Eixo X", opcoes_xy, index=opcoes_xy.index(sugestao["eixo_x"]) if sugestao["eixo_x"] in opcoes_xy else 0, key=make_key(contexto, tipo_grafico, modo_selecao, "x")) if opcoes_xy else None
        eixo_y = st.selectbox("Eixo Y", opcoes_xy, index=opcoes_xy.index(sugestao["eixo_y"]) if sugestao["eixo_y"] in opcoes_xy else min(1, len(opcoes_xy) - 1), key=make_key(contexto, tipo_grafico, modo_selecao, "y")) if opcoes_xy else None
    elif tipo_grafico in {"Box plot", "Violino"}:
        eixo_x = _selectbox_opcional("Eixo X", agrupaveis if modo_selecao == "Recomendado" else todas_colunas, make_key(contexto, tipo_grafico, modo_selecao, "x"), sugestao["eixo_x"])
        eixo_y = st.selectbox("Eixo Y", numericas if modo_selecao == "Recomendado" else todas_colunas, index=0, key=make_key(contexto, tipo_grafico, modo_selecao, "y")) if (numericas or modo_selecao == "Avançado") else None
    elif tipo_grafico == "Heatmap 2D":
        opcoes_xy = _opcoes_por_modo(classes, modo_selecao, numericas)
        eixo_x = st.selectbox("Eixo X", opcoes_xy, index=opcoes_xy.index(sugestao["eixo_x"]) if sugestao["eixo_x"] in opcoes_xy else 0, key=make_key(contexto, tipo_grafico, modo_selecao, "x")) if opcoes_xy else None
        eixo_y = st.selectbox("Eixo Y", opcoes_xy, index=opcoes_xy.index(sugestao["eixo_y"]) if sugestao["eixo_y"] in opcoes_xy else min(1, len(opcoes_xy) - 1), key=make_key(contexto, tipo_grafico, modo_selecao, "y")) if opcoes_xy else None
    elif tipo_grafico in {"Treemap", "Sunburst"}:
        opcoes_hierarquia = _opcoes_por_modo(classes, modo_selecao, agrupaveis)
        hierarquia_1 = st.selectbox("Hierarquia 1", opcoes_hierarquia, index=opcoes_hierarquia.index(sugestao["hierarquia_1"]) if sugestao["hierarquia_1"] in opcoes_hierarquia else 0, key=make_key(contexto, tipo_grafico, modo_selecao, "h1")) if opcoes_hierarquia else None
        hierarquia_2 = _selectbox_opcional("Hierarquia 2", [c for c in opcoes_hierarquia if c != hierarquia_1], make_key(contexto, tipo_grafico, modo_selecao, "h2"), sugestao["hierarquia_2"])
        coluna_valor = _selectbox_opcional("Coluna de valor", numericas if modo_selecao == "Recomendado" else todas_colunas, make_key(contexto, tipo_grafico, modo_selecao, "valor"), None)
    elif tipo_grafico == "Pizza":
        opcoes_x = _opcoes_por_modo(classes, modo_selecao, agrupaveis)
        eixo_x = st.selectbox("Categoria", opcoes_x, index=opcoes_x.index(sugestao["eixo_x"]) if sugestao["eixo_x"] in opcoes_x else 0, key=make_key(contexto, tipo_grafico, modo_selecao, "categoria")) if opcoes_x else None
        coluna_valor = _selectbox_opcional("Coluna de valor", numericas if modo_selecao == "Recomendado" else todas_colunas, make_key(contexto, tipo_grafico, modo_selecao, "valor"), None)

    # Cor agrupa visualmente, rotulo escreve nomes no grafico, hover adiciona
    # contexto no tooltip e tamanho varia o marcador em graficos de dispersao.
    opcoes_cor = agrupaveis if modo_selecao == "Recomendado" else list(dict.fromkeys(agrupaveis + texto_curto + booleanas + codigos + textos))
    coluna_cor = _selectbox_opcional("Campo de cor/agrupamento", opcoes_cor, make_key(contexto, tipo_grafico, modo_selecao, "cor"), sugestao["cor"])
    coluna_rotulo = _selectbox_opcional("Campo de rótulo", classes["colunas_rotulo"] if modo_selecao == "Recomendado" else todas_colunas, make_key(contexto, tipo_grafico, modo_selecao, "rotulo"), sugestao["rotulo"])
    campos_hover = _multiselect_opcional("Campos de hover", todas_colunas, make_key(contexto, tipo_grafico, modo_selecao, "hover"), sugestao["hover"])
    coluna_tamanho = _selectbox_opcional("Campo de tamanho", numericas, make_key(contexto, tipo_grafico, modo_selecao, "tamanho"), sugestao["tamanho"]) if tipo_grafico == "Dispersão" else None
    coluna_facet = _selectbox_opcional("Facet/coluna de separação", opcoes_cor, make_key(contexto, tipo_grafico, modo_selecao, "facet"), sugestao["facet"]) if tipo_grafico not in {"Pizza", "Treemap", "Sunburst"} else None

    compat, mensagem = validar_configuracao_grafico(tipo_grafico, eixo_x, eixo_y, coluna_cor, coluna_valor, modo_selecao, data_plot)
    if mensagem:
        st.warning(mensagem)
    if not compat:
        return
    if tipo_grafico in {"Treemap", "Sunburst"} and not hierarquia_1:
        st.warning("Escolha ao menos uma coluna de hierarquia para montar este gráfico.")
        return
    if tipo_grafico == "Dispersão" and modo_selecao == "Recomendado" and len(numericas) < 2:
        st.warning("Dispersão precisa de pelo menos duas colunas numéricas.")
        return

    amostra = data_plot.head(500).copy()
    try:
        if tipo_grafico == "Barra":
            if eixo_y:
                fig = px.bar(amostra, x=eixo_x, y=eixo_y, **_parametros_comuns_plotly(amostra, coluna_cor, campos_hover, coluna_rotulo, coluna_facet, incluir_texto=True))
            else:
                # Contagem automatica deixa o grafico util mesmo quando a base so tem strings.
                dados = _agrupar_contagem(amostra, [eixo_x, coluna_cor])
                fig = px.bar(dados, x=eixo_x, y="contagem", color=coluna_cor if coluna_cor in dados.columns else None, hover_data=[c for c in campos_hover if c in dados.columns])
        elif tipo_grafico == "Barra horizontal":
            if eixo_x:
                fig = px.bar(amostra, x=eixo_x, y=eixo_y, orientation="h", **_parametros_comuns_plotly(amostra, coluna_cor, campos_hover, coluna_rotulo, coluna_facet, incluir_texto=True))
            else:
                dados = _agrupar_contagem(amostra, [eixo_y, coluna_cor])
                fig = px.bar(dados, x="contagem", y=eixo_y, color=coluna_cor if coluna_cor in dados.columns else None, orientation="h", hover_data=[c for c in campos_hover if c in dados.columns])
        elif tipo_grafico == "Linha":
            fig = px.line(amostra, x=eixo_x, y=eixo_y, **_parametros_comuns_plotly(amostra, coluna_cor, campos_hover, coluna_rotulo, coluna_facet, incluir_texto=True))
        elif tipo_grafico == "Dispersão":
            params = _parametros_comuns_plotly(amostra, coluna_cor, campos_hover, coluna_rotulo, coluna_facet, incluir_texto=True)
            if coluna_tamanho in amostra.columns:
                params["size"] = coluna_tamanho
            fig = px.scatter(amostra, x=eixo_x, y=eixo_y, **params)
        elif tipo_grafico == "Histograma":
            fig = px.histogram(amostra, x=eixo_x, **_parametros_comuns_plotly(amostra, coluna_cor, campos_hover, None, coluna_facet))
        elif tipo_grafico == "Box plot":
            fig = px.box(amostra, x=eixo_x, y=eixo_y, **_parametros_comuns_plotly(amostra, coluna_cor, campos_hover, None, coluna_facet))
        elif tipo_grafico == "Violino":
            fig = px.violin(amostra, x=eixo_x, y=eixo_y, box=True, **_parametros_comuns_plotly(amostra, coluna_cor, campos_hover, None, coluna_facet))
        elif tipo_grafico == "Área":
            fig = px.area(amostra, x=eixo_x, y=eixo_y, **_parametros_comuns_plotly(amostra, coluna_cor, campos_hover, None, coluna_facet))
        elif tipo_grafico == "Heatmap 2D":
            params = _parametros_comuns_plotly(amostra, None, campos_hover, None, coluna_facet)
            fig = px.density_heatmap(amostra, x=eixo_x, y=eixo_y, **params)
        elif tipo_grafico == "Treemap":
            caminho = [c for c in (hierarquia_1, hierarquia_2) if c]
            dados = amostra if coluna_valor else _agrupar_contagem(amostra, caminho)
            fig = px.treemap(dados, path=caminho, values=coluna_valor if coluna_valor else "contagem", hover_data=[c for c in campos_hover if c in dados.columns])
        elif tipo_grafico == "Sunburst":
            caminho = [c for c in (hierarquia_1, hierarquia_2) if c]
            dados = amostra if coluna_valor else _agrupar_contagem(amostra, caminho)
            fig = px.sunburst(dados, path=caminho, values=coluna_valor if coluna_valor else "contagem", hover_data=[c for c in campos_hover if c in dados.columns])
        else:
            dados = amostra if coluna_valor else _agrupar_contagem(amostra, [eixo_x])
            fig = px.pie(dados, names=eixo_x, values=coluna_valor if coluna_valor else "contagem", hover_data=[c for c in campos_hover if c in dados.columns])
        exibir_plotly(
            fig,
            key=make_key(
                "inventario",
                "grafico_exploratorio",
                tipo_grafico,
                modo_selecao,
                nome_arquivo,
                layer_name,
                eixo_x,
                eixo_y,
                coluna_cor,
                coluna_rotulo,
                coluna_valor,
                coluna_tamanho,
                coluna_facet,
                hierarquia_1,
                hierarquia_2,
                ",".join(campos_hover),
            ),
        )
    except Exception as exc:
        st.warning(f"Não foi possível montar gráfico exploratório: {exc}")
        return

    st.markdown("#### Dados usados no gráfico")
    if len(data_plot) > 500:
        st.caption("Exibindo amostra dos primeiros 500 registros para manter a interface leve.")
    st.dataframe(amostra, use_container_width=True)

def renderizar_inventarios_recentes(recentes: QueryResult) -> None:
    """Exibe historico recente com colunas curtas primeiro e detalhes em expander."""
    if not recentes.ok:
        st.info("Não foi possível carregar inventários recentes. Verifique a view importacao.vw_inventario_bases_geograficas.")
        if recentes.erro:
            st.caption(recentes.erro)
        return
    data = recentes.data.copy()
    if data.empty:
        st.info("Nenhum inventário registrado ainda.")
        return
    colunas_resumo = [coluna for coluna in ("lote_id", "inventario_arquivo_id", "nome_lote", "nome_arquivo", "hash_abreviado", "grupo_sugerido", "tema_sugerido", "schema_destino_sugerido", "tabela_destino_sugerida", "status_validacao", "criado_em") if coluna in data.columns]
    st.dataframe(data[colunas_resumo], use_container_width=True)
    with st.expander("Detalhes completos dos inventários recentes", expanded=False):
        st.dataframe(data, use_container_width=True)

def renderizar_perfil_atributos(gdf: gpd.GeoDataFrame, contexto: str) -> pd.DataFrame:
    """Renderiza perfil editavel dos atributos da base inventariada."""
    st.markdown("#### Perfil de atributos")
    st.caption(
        "A inferencia ajuda a visualizar dados publicos que chegam como texto. "
        "A conversao aqui e temporaria e nao altera arquivo original, banco ou schemas oficiais."
    )
    atributos = pd.DataFrame(gdf.drop(columns=gdf.geometry.name, errors="ignore"))
    perfil_df = inferir_perfil_atributos(atributos)
    if perfil_df.empty:
        st.info("A base não possui atributos tabulares para perfilamento.")
        return perfil_df

    colunas_editor = [
        "nome_campo",
        "tipo_original",
        "tipo_sugerido",
        "tipo_confirmado",
        "categoria_uso",
        "percentual_conversao",
        "valores_unicos",
        "nulos",
        "usar_dashboard",
        "usar_grafico",
        "usar_mapa_popup",
        "usar_exportacao",
        "observacao",
    ]
    perfil_editado = st.data_editor(
        perfil_df[colunas_editor],
        use_container_width=True,
        hide_index=True,
        key=make_key(contexto, "perfil_atributos_editor"),
        disabled=["nome_campo", "tipo_original", "tipo_sugerido", "percentual_conversao", "valores_unicos", "nulos"],
        column_config={
            "tipo_confirmado": st.column_config.SelectboxColumn(
                "Tipo confirmado",
                options=["texto", "categoria", "inteiro", "decimal", "monetario", "percentual", "data", "booleano", "codigo", "ignorar"],
            ),
            "categoria_uso": st.column_config.SelectboxColumn(
                "Categoria de uso",
                options=["identificador", "classificacao", "medida", "temporal", "descricao", "ignorar", "outro"],
            ),
        },
    )
    perfil_editado = perfil_editado.merge(
        perfil_df[["nome_campo", "total_registros", "nao_nulos", "exemplos_valores", "min_num", "max_num", "media_num", "min_data", "max_data"]],
        on="nome_campo",
        how="left",
    )

    with st.expander("Exemplos de valores por campo", expanded=False):
        exemplos = perfil_df[["nome_campo", "exemplos_valores"]].copy()
        exemplos["exemplos_valores"] = exemplos["exemplos_valores"].map(lambda valores: ", ".join(map(str, valores)) if isinstance(valores, list) else "")
        st.dataframe(exemplos, use_container_width=True)

    ultimo_inventario_id = st.session_state.get("ultimo_inventario_arquivo_id")
    if ultimo_inventario_id:
        if st.button("Salvar perfil de atributos", key=make_key(contexto, "salvar_perfil_atributos")):
            ok, mensagem = salvar_perfil_atributos(int(ultimo_inventario_id), perfil_editado)
            if ok:
                st.success(f"{mensagem} inventario_arquivo_id={ultimo_inventario_id}.")
            else:
                st.warning(mensagem)
    else:
        st.caption("O perfil sera salvo junto com o inventario. Para inventarios existentes, use o botao apos haver inventario_arquivo_id na sessao.")
    return perfil_editado

def renderizar_inventario_nova_base() -> None:
    """Interface de entrada, validacao, perfilamento e registro de inventario."""
    st.subheader("Inventariar nova base")
    st.caption(
        "Inventariar registra metadados, qualidade e perfil de atributos. Nesta etapa não há importação "
        "para staging nem alteração de schemas oficiais."
    )

    metodo_entrada = st.selectbox(
        "Método de entrada da base",
        ["Upload pela interface", "Caminho local ou de rede", "URL de download"],
        key="inventario_metodo_entrada",
    )

    inventario: dict[str, Any] | None = None
    gdf: gpd.GeoDataFrame | None = None
    caminho: Path | None = None
    formato = ""
    layer: str | None = None
    epsg_manual: int | None = None
    nome_original = ""
    perfil_editado: pd.DataFrame | None = None

    if metodo_entrada == "Upload pela interface":
        uploaded_file = st.file_uploader(
            "Selecione a base geográfica",
            type=["gpkg", "geojson", "json", "zip"],
            key="inventario_upload_base",
        )
        if uploaded_file is not None:
            caminho = salvar_upload_temporario(uploaded_file)
            nome_original = uploaded_file.name
    elif metodo_entrada == "Caminho local ou de rede":
        caminho_texto = st.text_input(
            "Caminho do arquivo",
            placeholder=r"C:\Users\Usuario\OneDrive\EA2S\Bases\PMF\zoneamento.gpkg",
            key="inventario_caminho_arquivo",
        )
        st.caption(r"Exemplos: D:\Bases\CPRM\risco_geologico.gpkg ou \\servidor\sig\bases\zoneamento.shp")
        if caminho_texto.strip():
            caminho = Path(caminho_texto.strip().strip('"'))
            nome_original = caminho.name
            if not caminho.exists():
                st.error("O caminho informado não existe. Corrija o caminho antes de continuar.")
                caminho = None
            elif caminho.is_dir():
                st.error("Informe o caminho completo do arquivo, não apenas a pasta.")
                caminho = None
    else:
        url_base = st.text_input(
            "URL da base geográfica",
            placeholder="https://exemplo.gov.br/dados/base.gpkg",
            key="inventario_url_base",
        )
        st.info("O registro de URL está preparado. O download automático será consolidado em etapa futura.")
        confirmar_url = st.checkbox("Confirmo que desejo registrar esta URL como inventário pendente.", key="inventario_confirmar_url")
        if url_base.strip() and confirmar_url:
            inventario = montar_inventario_url(url_base.strip())
            nome_original = inventario["nome_original_upload"]

    if caminho is not None:
        formato = detectar_formato_arquivo(caminho)
        if formato == "gpkg":
            layers = listar_layers_gpkg(caminho)
            if len(layers) > 1:
                layer = st.selectbox("Layer do GPKG", layers, key="inventario_layer_gpkg")
            elif len(layers) == 1:
                layer = layers[0]
                st.caption(f"Layer detectada: {layer}")
            else:
                st.warning("Não foi possível listar layers do GPKG; será tentada a primeira layer disponível.")
        elif formato == "shapefile_zip":
            try:
                shapefiles, possui_prj = listar_shapefiles_zip(caminho)
                if len(shapefiles) > 1:
                    layer = st.selectbox("Shapefile do ZIP", shapefiles, key="inventario_shp_zip")
                elif len(shapefiles) == 1:
                    layer = shapefiles[0]
                    st.caption(f"Shapefile detectado: {layer}")
                if not possui_prj:
                    st.warning("O ZIP não possui .prj. Informe EPSG manualmente se necessário.")
            except Exception as exc:
                st.error(f"Não foi possível inspecionar o ZIP: {exc}")

        try:
            gdf = ler_base_geografica_upload(caminho, layer=layer)
            if gdf.crs is None:
                epsg_manual = st.number_input("EPSG manual para estatísticas", min_value=1, value=31982, step=1, key="inventario_epsg_manual")
            inventario = montar_inventario_base(
                gdf,
                caminho,
                formato,
                epsg_padrao=epsg_manual,
                layer_name=layer,
                nome_original_upload=nome_original or caminho.name,
            )
        except Exception as exc:
            inventario = {
                "formato": formato or detectar_formato_arquivo(caminho),
                "nome_arquivo": nome_original or caminho.name,
                "nome_original_upload": nome_original or caminho.name,
                "layer_name": layer,
                "hash_arquivo": calcular_hash_arquivo(caminho) if caminho.exists() else None,
                "caminho_temporario": str(caminho),
                "tamanho_bytes": caminho.stat().st_size if caminho.exists() else None,
                "status_validacao": "erro_leitura",
                "mensagem_validacao": str(exc),
                "campos": [],
            }
            st.error(f"Erro de leitura: {exc}")

    if inventario:
        campos_nomes = [item.get("nome_campo", "") for item in inventario.get("campos") or []]
        sugestoes = sugerir_metadados_base(inventario.get("nome_original_upload") or inventario.get("nome_arquivo") or "", campos_nomes)
        hash_arquivo = inventario.get("hash_arquivo")
        hash_abreviado = str(hash_arquivo)[:12] if hash_arquivo else "-"

        st.markdown("#### Resumo técnico da base")
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Feições", formatar_inteiro(inventario.get("numero_feicoes")))
        m2.metric("Campos", formatar_inteiro(inventario.get("numero_campos")))
        m3.metric("SRID", inventario.get("srid_detectado") or "-")
        m4.metric("Geometria", inventario.get("tipo_geometria") or "-")
        m5.metric("Área ha", formatar_numero(inventario.get("area_total_ha"), 4))
        m6.metric("Comprimento km", formatar_numero(inventario.get("comprimento_total_km"), 3))
        st.info(inventario.get("mensagem_validacao") or "Base inventariada para revisão.")
        if inventario.get("status_validacao") == "geometria_invalida":
            st.warning(
                "Atenção: foram encontradas geometrias inválidas. "
                "O inventário será registrado com essa informação. "
                "A correção será tratada na etapa de staging."
            )
        st.json({"metodo_entrada": metodo_entrada, "nome_original_upload": inventario.get("nome_original_upload"), "hash_sha256_12": hash_abreviado, "layer_name": inventario.get("layer_name"), "bbox": inventario.get("bbox"), "status_validacao": inventario.get("status_validacao")})

        duplicados = buscar_inventarios_por_hash(hash_arquivo)
        tem_duplicado = bool(hash_arquivo and duplicados.ok and not duplicados.data.empty)
        if hash_arquivo and not duplicados.ok:
            st.warning(duplicados.erro)
        elif tem_duplicado:
            st.warning("Este arquivo já foi inventariado anteriormente.")
            st.dataframe(duplicados.data, use_container_width=True)
        elif not hash_arquivo:
            st.caption("Entrada sem hash de arquivo. Para URLs, a deduplicação por SHA256 ocorrerá após download futuro controlado.")

        if inventario.get("campos"):
            st.markdown("#### Campos")
            st.dataframe(pd.DataFrame(inventario.get("campos") or []), use_container_width=True)

        if gdf is not None:
            perfil_editado = renderizar_perfil_atributos(gdf, "inventario_base")
            st.markdown("#### Prévia sem geometria")
            atributos_convertidos = preparar_dataframe_para_visualizacao(
                pd.DataFrame(gdf.drop(columns=gdf.geometry.name, errors="ignore")),
                perfil_editado,
            )
            st.dataframe(atributos_convertidos.head(20), use_container_width=True)
            with st.expander("Resumo estatístico", expanded=False):
                try:
                    st.dataframe(atributos_convertidos.describe(include="all"), use_container_width=True)
                except Exception as exc:
                    st.warning(f"Não foi possível gerar resumo estatístico: {exc}")
            renderizar_grafico_exploratorio_inventario(
                gdf,
                "inventario_base",
                nome_arquivo=inventario.get("nome_original_upload") or inventario.get("nome_arquivo"),
                layer_name=inventario.get("layer_name"),
                perfil_df=perfil_editado,
            )

        st.markdown("#### Metadados complementares")
        with st.form("form_registrar_inventario_base"):
            nome_lote = st.text_input("Nome do lote", value=Path(inventario.get("nome_arquivo") or "base_geografica").stem)
            c1, c2, c3 = st.columns(3)
            grupo_index = GRUPOS_INVENTARIO.index(sugestoes["grupo"]) if sugestoes["grupo"] in GRUPOS_INVENTARIO else GRUPOS_INVENTARIO.index("outros")
            grupo = c1.selectbox("Grupo", GRUPOS_INVENTARIO, index=grupo_index, key="inventario_grupo")
            tema = c2.text_input("Tema", value=sugestoes["tema"])
            subtema = c3.text_input("Subtema", value=sugestoes.get("subtema") or "")
            c4, c5, c6 = st.columns(3)
            fonte = c4.text_input("Fonte")
            orgao_produtor = c5.text_input("Órgão produtor")
            ano_referencia = c6.number_input("Ano de referência", min_value=0, max_value=3000, value=0, step=1)
            schema_sugerido = sugestoes.get("schema_destino_sugerido") or "outros"
            schema_destino = st.selectbox("Schema destino sugerido", SCHEMAS_DESTINO_SUGERIDOS, index=SCHEMAS_DESTINO_SUGERIDOS.index(schema_sugerido) if schema_sugerido in SCHEMAS_DESTINO_SUGERIDOS else 0)
            tabela_base = sugestoes.get("tabela_destino_sugerida") or sanitizar_nome_tabela(f"{tema}_{fonte}_{ano_referencia}" if fonte or ano_referencia else tema)
            if tabela_base in NOMES_GENERICOS_TABELA or tabela_base == "base_geografica":
                tabela_base = sanitizar_nome_tabela("_".join(str(v) for v in (tema, fonte, ano_referencia) if v))
            tabela_destino = st.text_input("Tabela destino sugerida", value=tabela_base)
            observacao = st.text_area("Observação")
            registrar_duplicado = False
            if tem_duplicado:
                registrar_duplicado = st.checkbox("Registrar mesmo assim como novo inventário", key=make_key("inventario", "permitir_duplicado", hash_abreviado or inventario.get("nome_original_upload") or "sem_hash"))
            confirmar = st.checkbox(
                "Confirmo que desejo registrar este inventário no banco.",
                key=make_key("inventario", "confirmacao_registro", hash_abreviado or inventario.get("nome_original_upload") or "sem_hash"),
            )
            # O submit fica sempre clicavel. Widgets dentro de st.form so atualizam
            # no envio; por isso a validacao ocorre depois do clique, nao no disabled.
            registrar = st.form_submit_button("Registrar inventário", type="primary")

        ja_registrado_sessao = bool(hash_arquivo and st.session_state.get("ultimo_hash_inventariado") == hash_arquivo)
        pendencias_registro = validar_pronto_para_registro_inventario(
            nome_lote=nome_lote,
            grupo=grupo,
            tema=tema,
            schema_destino_sugerido=schema_destino,
            tabela_destino_sugerida=tabela_destino,
            confirmacao_registro=bool(confirmar),
            duplicidade_bloqueante=bool(tem_duplicado),
            permitir_duplicado=bool(registrar_duplicado),
            inventario_tecnico=inventario,
            ja_registrado_sessao=ja_registrado_sessao,
        )
        if pendencias_registro and not registrar:
            st.info("Pendências para registro:")
            for pendencia in pendencias_registro:
                st.caption(f"- {pendencia}")

        if registrar:
            if pendencias_registro:
                st.error("Não foi possível registrar o inventário.")
                for pendencia in pendencias_registro:
                    st.warning(pendencia)
                return
            metadados = {
                "nome_lote": nome_lote.strip(),
                "grupo": grupo,
                "tema": tema.strip(),
                "subtema": subtema.strip() or None,
                "schema_destino": schema_destino.strip(),
                "tabela_destino": sanitizar_nome_tabela(tabela_destino.strip()),
                "fonte": fonte.strip() or None,
                "orgao_produtor": orgao_produtor.strip() or None,
                "ano_referencia": int(ano_referencia) if ano_referencia else None,
                "observacao": observacao.strip() or None,
                "responsavel": st.session_state.get("usuario_execucao") or "Paulo",
                "permitir_duplicado": bool(registrar_duplicado),
            }
            try:
                lote_id, inventario_id = registrar_inventario_base(inventario, metadados)
                if hash_arquivo:
                    st.session_state["ultimo_hash_inventariado"] = hash_arquivo
                st.session_state["ultimo_inventario_arquivo_id"] = inventario_id
                st.session_state["ultimo_lote_id"] = lote_id
                st.success(f"Inventário registrado. lote_id={lote_id}; inventario_arquivo_id={inventario_id}.")
                caminho_persistente = copiar_arquivo_original_para_persistente(
                    inventario.get("caminho_temporario"),
                    lote_id,
                    inventario_id,
                    inventario.get("nome_original_upload") or inventario.get("nome_arquivo"),
                )
                if caminho_persistente:
                    st.success(f"Arquivo original preservado em: {caminho_persistente}")
                elif inventario.get("formato") != "url":
                    st.warning("Inventário registrado, mas o arquivo original não foi copiado para data/importacao/originais. Faça a cópia antes de importar para staging.")
                if perfil_editado is not None and not perfil_editado.empty:
                    ok_perfil, msg_perfil = salvar_perfil_atributos(inventario_id, perfil_editado)
                    if ok_perfil:
                        st.success("Perfil de atributos salvo junto com o inventário.")
                    else:
                        st.warning(msg_perfil)
                st.info("Inventário registrado. A próxima etapa será importar para staging e validar antes de promover para a base oficial.")
            except Exception as exc:
                st.error(f"Não foi possível registrar o inventário: {exc}")

    st.markdown("#### Inventários recentes")
    renderizar_inventarios_recentes(carregar_inventarios_recentes())

def carregar_inventarios_para_staging() -> QueryResult:
    """Carrega inventarios candidatos a importacao para staging. Apenas leitura."""
    if not view_existe("importacao.vw_inventario_bases_geograficas"):
        return QueryResult(False, pd.DataFrame(), "View importacao.vw_inventario_bases_geograficas nao encontrada.")
    return fetch_dataframe(
        """
        SELECT
            lote_id,
            inventario_arquivo_id,
            nome_lote,
            nome_arquivo,
            nome_original_upload,
            caminho_temporario,
            left(hash_arquivo, 12) AS hash_abreviado,
            hash_arquivo,
            layer_name,
            schema_destino_sugerido,
            tabela_destino_sugerida,
            fonte,
            orgao_produtor,
            ano_referencia,
            grupo_sugerido,
            tema_sugerido,
            status_validacao,
            numero_feicoes,
            numero_campos,
            srid_detectado,
            tipo_geometria,
            geometria_valida,
            mensagem_validacao,
            arquivo_criado_em AS criado_em
        FROM importacao.vw_inventario_bases_geograficas
        ORDER BY arquivo_criado_em DESC
        LIMIT 200;
        """
    )


def carregar_staging_importacoes_recentes() -> QueryResult:
    """Lista importacoes para staging quando SQL 16 ja tiver sido aplicado."""
    if not view_existe("importacao.vw_staging_importacoes"):
        return QueryResult(False, pd.DataFrame(), "Aplique sql/16_importacao_staging.sql para habilitar o controle de staging.")
    return fetch_dataframe(
        """
        SELECT
            staging_importacao_id,
            inventario_arquivo_id,
            lote_id,
            nome_lote,
            nome_original,
            schema_staging,
            tabela_staging,
            status_importacao,
            status_validacao,
            numero_feicoes_staging,
            geometrias_invalidas_staging,
            criado_em
        FROM importacao.vw_staging_importacoes
        ORDER BY criado_em DESC
        LIMIT 50;
        """
    )


def carregar_importacoes_oficiais_recentes() -> QueryResult:
    """Lista importacoes oficiais quando SQL 18 ja tiver sido aplicado."""
    if not view_existe("importacao.vw_importacoes_oficiais"):
        return QueryResult(False, pd.DataFrame(), "Aplique sql/18_importacao_direta_schema_oficial.sql para habilitar o controle de importacao oficial.")
    return fetch_dataframe(
        """
        SELECT
            importacao_oficial_id,
            inventario_arquivo_id,
            nome_lote,
            schema_destino,
            tabela_destino,
            grupo,
            tema,
            status_qualidade,
            pode_usar_diagnostico,
            cadastrada_em_config,
            config_ativo,
            criado_em
        FROM importacao.vw_importacoes_oficiais
        ORDER BY criado_em DESC
        LIMIT 50;
        """
    )


def renderizar_importacao_oficial() -> None:
    """Fluxo principal: inventario validado para tabela oficial nova."""
    st.markdown("### Importar para base oficial")
    st.caption(
        "Fluxo principal simplificado: inventário, validação técnica, correção opcional e importação direta "
        "para uma nova tabela em schema oficial. Não sobrescreve tabelas existentes."
    )
    inventarios = carregar_inventarios_para_staging()
    if not inventarios.ok:
        st.warning("Não foi possível carregar inventários registrados.")
        if inventarios.erro:
            st.caption(inventarios.erro)
        return
    if inventarios.data.empty:
        st.info("Nenhum inventário encontrado para importação oficial.")
        return

    dados = inventarios.data.copy()
    dados["rotulo"] = dados.apply(
        lambda row: f"#{row.get('inventario_arquivo_id')} | {row.get('nome_original_upload') or row.get('nome_arquivo')} | {row.get('status_validacao')}",
        axis=1,
    )
    rotulo = st.selectbox("Inventário registrado", dados["rotulo"].tolist(), key="oficial_inventario_selecionado")
    row = dados.loc[dados["rotulo"] == rotulo].iloc[0].to_dict()
    inv_id = int(row["inventario_arquivo_id"])
    caminho_original = localizar_arquivo_original(row)

    st.markdown("#### Resumo do inventário")
    resumo_cols = [
        col
        for col in (
            "inventario_arquivo_id",
            "lote_id",
            "nome_lote",
            "nome_original_upload",
            "hash_abreviado",
            "srid_detectado",
            "tipo_geometria",
            "numero_feicoes",
            "status_validacao",
            "geometria_valida",
            "grupo_sugerido",
            "tema_sugerido",
            "subtema_sugerido",
            "fonte",
            "orgao_produtor",
            "ano_referencia",
            "schema_destino_sugerido",
            "tabela_destino_sugerida",
        )
        if col in row
    ]
    st.dataframe(pd.DataFrame([row])[resumo_cols], use_container_width=True)
    if caminho_original:
        st.success(f"Arquivo persistido localizado: {caminho_original}")
    else:
        st.error("O arquivo persistido não foi encontrado. Reenvie ou persista novamente a base antes de importar.")
        return

    schema_default = str(row.get("schema_destino_sugerido") or "").strip()
    tabela_default = gerar_nome_tabela_oficial(
        schema_default,
        row.get("tabela_destino_sugerida"),
        row.get("fonte"),
        row.get("ano_referencia"),
    )
    st.markdown("#### Destino oficial")
    c1, c2 = st.columns(2)
    with c1:
        schema_destino = st.text_input("Schema destino", value=schema_default, key=make_key("oficial", "schema", inv_id))
    with c2:
        tabela_destino = st.text_input("Tabela destino", value=tabela_default, key=make_key("oficial", "tabela", inv_id))
    st.caption("A importação só cria tabela nova. Se a tabela já existir, o fluxo deve bloquear e sugerir nome _v2.")

    diagnostico_key = make_key("oficial", "diagnostico", inv_id)
    if st.button("Diagnosticar inventário para importação oficial", key=make_key("oficial", "diagnosticar", inv_id)):
        try:
            with get_connection() as conn:
                st.session_state[diagnostico_key] = diagnosticar_inventario_para_importacao_oficial(inv_id, conn)
        except Exception as exc:
            st.session_state[diagnostico_key] = {"status_preliminar": "bloqueado", "bloqueios": [str(exc)], "avisos": []}

    diagnostico = st.session_state.get(diagnostico_key)
    if diagnostico:
        st.markdown("#### Diagnóstico técnico")
        status = diagnostico.get("status_preliminar")
        if status == "valido":
            st.success("Status preliminar: válido.")
        elif status == "pendencias":
            st.warning("Status preliminar: importável com pendências técnicas.")
        else:
            st.error("Status preliminar: bloqueado.")
        diag_cols = st.columns(4)
        diag_cols[0].metric("Feições", diagnostico.get("numero_feicoes") or "-")
        diag_cols[1].metric("SRID", diagnostico.get("srid") or "-")
        diag_cols[2].metric("Geometrias inválidas", diagnostico.get("geometrias_invalidas") if diagnostico.get("geometrias_invalidas") is not None else "-")
        diag_cols[3].metric("Geometrias nulas", diagnostico.get("geometrias_nulas") if diagnostico.get("geometrias_nulas") is not None else "-")
        if diagnostico.get("avisos"):
            st.warning("Avisos: " + "; ".join(str(item) for item in diagnostico.get("avisos", [])))
        if diagnostico.get("bloqueios"):
            st.error("Bloqueios: " + "; ".join(str(item) for item in diagnostico.get("bloqueios", [])))
        if diagnostico.get("tabela_destino_sugerida_v2"):
            st.caption(f"Sugestão se a tabela já existir: {diagnostico['tabela_destino_sugerida_v2']}")

        if (diagnostico.get("geometrias_invalidas") or 0) > 0:
            st.info(
                "Esta camada possui geometrias inválidas. O sistema pode tentar corrigir automaticamente em memória. "
                "Se a correção não resolver tudo, ainda será possível importar com pendências para ajuste posterior no QGIS."
            )
            if st.button("Testar correção automática de geometrias", key=make_key("oficial", "corrigir", inv_id)):
                try:
                    with get_connection() as conn:
                        st.session_state[make_key("oficial", "correcao", inv_id)] = testar_correcao_inventario(inv_id, conn)
                except Exception as exc:
                    st.session_state[make_key("oficial", "correcao", inv_id)] = {"erro": str(exc)}

    correcao = st.session_state.get(make_key("oficial", "correcao", inv_id))
    if correcao:
        st.markdown("#### Teste de correção automática")
        if correcao.get("erro"):
            st.error(correcao["erro"])
        else:
            st.dataframe(pd.DataFrame([{k: v for k, v in correcao.items() if k != "arquivo_persistido"}]), use_container_width=True)
            if correcao.get("geometrias_invalidas_depois") == 0:
                st.success("Camada corrigida e apta para importação oficial.")
            else:
                st.warning("A correção automática não resolveu todos os problemas. A camada pode ser importada com pendências para correção posterior no QGIS.")

    st.markdown("#### Confirmação de importação")
    corrigir_geometrias = st.checkbox("Corrigir geometrias em memória antes de importar", key=make_key("oficial", "corrigir_importacao", inv_id))
    cadastrar_config = st.checkbox("Cadastrar esta camada para uso em Compor diagnóstico", key=make_key("oficial", "cadastrar_config", inv_id))
    config_ativo = st.checkbox("Cadastrar como ativo no diagnóstico", value=False, disabled=not cadastrar_config, key=make_key("oficial", "config_ativo", inv_id))
    confirmar_valida = st.checkbox("Confirmo importar como camada válida quando não houver pendências críticas.", key=make_key("oficial", "confirmar_valida", inv_id))
    confirmar_pendencias = st.checkbox(
        "Confirmo importar esta camada com pendências técnicas. Entendo que ela poderá precisar de correção posterior no QGIS antes do uso em diagnósticos automáticos.",
        key=make_key("oficial", "confirmar_pendencias", inv_id),
    )

    c_validar, c_pend = st.columns(2)
    with c_validar:
        importar_valida = st.button("Importar como camada válida", type="primary", key=make_key("oficial", "importar_valida", inv_id))
    with c_pend:
        importar_pend = st.button("Importar com pendências", key=make_key("oficial", "importar_pendencias", inv_id))

    if importar_valida or importar_pend:
        permitir_pendencias = bool(importar_pend and confirmar_pendencias)
        if importar_valida and not confirmar_valida:
            st.warning("Confirme a importação como camada válida antes de prosseguir.")
            return
        if importar_pend and not confirmar_pendencias:
            st.warning("Confirme explicitamente a importação com pendências antes de prosseguir.")
            return
        try:
            with get_connection() as conn:
                resultado = importar_inventario_para_schema_oficial(
                    inv_id,
                    schema_destino=schema_destino,
                    tabela_destino=tabela_destino,
                    corrigir_geometrias=bool(corrigir_geometrias),
                    permitir_importar_com_pendencias=permitir_pendencias,
                    cadastrar_config=bool(cadastrar_config),
                    config_ativo=bool(config_ativo),
                    conn=conn,
                )
            if resultado.get("ok"):
                st.success("Importação oficial concluída.")
            else:
                st.warning(resultado.get("mensagem") or "Importação oficial não concluída.")
            st.json(resultado)
        except Exception as exc:
            st.error(f"Não foi possível importar para schema oficial: {exc}")
            st.info("Verifique se sql/18_importacao_direta_schema_oficial.sql foi aplicado e se sqlalchemy, geoalchemy2 e psycopg2 estão disponíveis.")

    st.markdown("#### Importações oficiais recentes")
    recentes = carregar_importacoes_oficiais_recentes()
    if recentes.ok:
        st.dataframe(recentes.data, use_container_width=True)
    else:
        st.info(recentes.erro or "Controle de importações oficiais ainda não disponível.")

def renderizar_importacao_staging() -> None:
    """Interface inicial para importar inventarios registrados para schema staging."""
    st.markdown("### Staging avançado")
    st.caption(
        "Esta etapa cria uma copia operacional no schema staging. "
        "Nao promove dados para schemas oficiais e nao cadastra camadas automaticamente."
    )
    inventarios = carregar_inventarios_para_staging()
    if not inventarios.ok:
        st.warning("Não foi possível carregar inventários para staging.")
        if inventarios.erro:
            st.caption(inventarios.erro)
        return
    if inventarios.data.empty:
        st.info("Nenhum inventário disponível para importar.")
        return

    data = inventarios.data.copy()
    data["rotulo"] = data.apply(
        lambda row: f"{int(row['inventario_arquivo_id'])} - {row.get('nome_original_upload') or row.get('nome_arquivo')} ({row.get('status_validacao')})",
        axis=1,
    )
    escolha = st.selectbox("Inventário", data["rotulo"].tolist(), key="staging_inventario_escolha")
    row = data.loc[data["rotulo"] == escolha].iloc[0].to_dict()
    inv_id = int(row["inventario_arquivo_id"])
    lote_id = int(row["lote_id"])
    nome_tabela = gerar_nome_tabela_staging(row.get("schema_destino_sugerido"), row.get("tabela_destino_sugerida"), inv_id)
    caminho_original = localizar_arquivo_original(row)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Inventário", inv_id)
    c2.metric("Lote", lote_id)
    c3.metric("Feições", formatar_inteiro(row.get("numero_feicoes")))
    c4.metric("SRID", row.get("srid_detectado") or "-")
    c5.metric("Status", row.get("status_validacao") or "-")
    st.markdown("#### Resumo")
    st.dataframe(
        pd.DataFrame([row])[[col for col in (
            "nome_lote", "nome_arquivo", "nome_original_upload", "layer_name", "schema_destino_sugerido",
            "tabela_destino_sugerida", "status_validacao", "mensagem_validacao"
        ) if col in row]],
        use_container_width=True,
    )
    if row.get("status_validacao") == "geometria_invalida":
        st.warning("A camada pode ser importada para staging com geometrias inválidas. Corrija antes de promover para schema oficial.")
        st.button("Corrigir geometrias em staging", disabled=True, help="Etapa futura: correção controlada no schema staging.")
    if caminho_original:
        st.success(f"Arquivo original localizado: {caminho_original}")
    else:
        st.error("Arquivo original persistente não localizado. Copie o arquivo para data/importacao/originais antes de importar para staging.")

    st.markdown("#### Destino staging")
    st.code(f"staging.{nome_tabela}")
    existentes = carregar_staging_importacoes_recentes()
    ja_importado = False
    if existentes.ok and not existentes.data.empty:
        existentes_inv = existentes.data[existentes.data["inventario_arquivo_id"] == inv_id]
        ja_importado = not existentes_inv.empty
        if ja_importado:
            st.warning("Este inventário já foi importado para staging.")
            st.dataframe(existentes_inv, use_container_width=True)
    reimportar = False
    if ja_importado:
        reimportar = st.checkbox("Reimportar criando nova tabela staging", key=make_key("staging", "reimportar", inv_id))

    confirmar = st.checkbox(
        "Confirmo importar apenas para schema staging, sem promover para schema oficial.",
        key=make_key("staging", "confirmar_importacao", inv_id),
    )
    if not confirmar:
        st.info("Marque a confirmação para habilitar a execução futura da importação.")
    importar = st.button("Importar para staging", type="primary", key=make_key("staging", "executar", inv_id))
    if importar:
        if not confirmar:
            st.error("Não foi possível importar para staging.")
            st.warning("Marque a confirmação para importar.")
            return
        if caminho_original is None:
            st.error("Não foi possível importar para staging.")
            st.warning("Arquivo original persistente não localizado.")
            return
        try:
            with get_connection() as conn:
                resultado = importar_inventario_para_staging(inv_id, conn, reimportar=bool(reimportar))
            if resultado.get("ja_importado"):
                st.warning(resultado.get("mensagem"))
            elif resultado.get("ok"):
                st.success(resultado.get("mensagem"))
                st.json(resultado)
            else:
                st.warning(resultado.get("mensagem") or "Importação não concluída.")
        except Exception as exc:
            st.error(f"Não foi possível importar para staging: {exc}")
            st.info("Verifique se sql/16_importacao_staging.sql foi aplicado e se sqlalchemy, geoalchemy2 e psycopg2 estão disponíveis.")

    st.markdown("#### Importações recentes para staging")
    if existentes.ok:
        st.dataframe(existentes.data, use_container_width=True)
    else:
        st.info(existentes.erro)


def pagina_camadas_analise() -> None:
    """Pagina tecnica para consultar, cadastrar e inventariar camadas."""
    st.title("Banco de dados geográficos")
    st.caption(
        "Cadastro operacional e inventário técnico de bases geográficas. "
        "Importações oficiais exigem diagnóstico técnico e confirmação explícita."
    )

    tab_camadas, tab_inventario, tab_oficial, tab_staging = st.tabs(["Camadas cadastradas", "Inventariar nova base", "Importar para base oficial", "Staging avançado"])

    with tab_camadas:
        result = carregar_camadas_analise_ativas()
        data = result.data if result.ok else pd.DataFrame()

        if not result.ok:
            st.warning(
                "A configuração de camadas ainda não foi criada. "
                "Aplique o script sql/11_config_camadas_analise.sql no banco com autorização explícita."
            )
        elif data.empty:
            st.info("Nenhuma camada ativa encontrada em config.vw_camadas_analise_ativas.")
        else:
            col1, col2, col3, col4 = st.columns(4)
            grupos = ["Todos"] + sorted(data.get("grupo", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
            temas = ["Todos"] + sorted(data.get("tema", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
            metricas = ["Todas"] + sorted(data.get("metrica_padrao", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
            with col1:
                filtro_grupo = st.selectbox("Grupo", grupos, key="camadas_filtro_grupo")
            with col2:
                filtro_tema = st.selectbox("Tema", temas, key="camadas_filtro_tema")
            with col3:
                filtro_metrica = st.selectbox("Métrica", metricas, key="camadas_filtro_metrica")
            with col4:
                filtro_status = st.selectbox("Status", ["Ativas", "Todas"], key="camadas_filtro_status")

            filtrado = dataframe_camadas_filtrado(data, filtro_grupo, filtro_tema, filtro_metrica, filtro_status)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Camadas ativas", int(data["ativo"].sum()) if "ativo" in data.columns else len(data))
            c2.metric("Grupos", int(data["grupo"].nunique()) if "grupo" in data.columns else 0)
            c3.metric("Métricas", int(data["metrica_padrao"].nunique()) if "metrica_padrao" in data.columns else 0)
            c4.metric("No relatório", int(data["incluir_relatorio"].sum()) if "incluir_relatorio" in data.columns else 0)

            colunas_exibir = [
                coluna
                for coluna in (
                    "nome_logico",
                    "titulo",
                    "grupo",
                    "tema",
                    "schema_name",
                    "table_name",
                    "geom_column",
                    "tipo_geometria",
                    "srid",
                    "metrica_padrao",
                    "tipo_processamento",
                    "usar_area_interesse",
                    "usar_buffer_1000m",
                    "usar_microbacia",
                    "usar_setor_censitario",
                    "exibir_dashboard",
                    "exportar_gpkg",
                    "incluir_relatorio",
                    "ativo",
                )
                if coluna in filtrado.columns
            ]
            st.dataframe(filtrado[colunas_exibir], use_container_width=True)

            st.markdown("#### Sínteses administrativas")
            if {"grupo", "metrica_padrao", "exportar_gpkg", "incluir_relatorio"}.issubset(data.columns):
                resumo = (
                    data.groupby("grupo", dropna=False)
                    .agg(
                        total_camadas=("nome_logico", "count"),
                        metricas=("metrica_padrao", "nunique"),
                        exportar_gpkg=("exportar_gpkg", "sum"),
                        incluir_relatorio=("incluir_relatorio", "sum"),
                    )
                    .reset_index()
                )
                st.dataframe(resumo, use_container_width=True)
                exibir_graficos_camadas(data)

        with st.expander("Cadastrar ou editar camada", expanded=False):
            st.caption(
                "O formulário grava somente em config.camadas_analise. Para remover uma camada do uso, "
                "desmarque Ativo; não há exclusão física por esta interface."
            )

            with st.form("form_camada_analise"):
                c1, c2 = st.columns(2)
                with c1:
                    nome_logico = st.text_input("nome_logico", key="camada_nome_logico")
                    titulo = st.text_input("título", key="camada_titulo")
                    grupo = st.text_input("grupo", value="fisico_biotico", key="camada_grupo")
                    tema = st.text_input("tema", key="camada_tema")
                    subtema = st.text_input("subtema", key="camada_subtema")
                    schema_name = st.text_input("schema_name", key="camada_schema_name")
                    table_name = st.text_input("table_name", key="camada_table_name")
                    geom_column = st.text_input("geom_column", value="geom", key="camada_geom_column")
                    pk_column = st.text_input("pk_column", value="id", key="camada_pk_column")
                with c2:
                    tipo_geometria = st.selectbox("tipo_geometria", TIPOS_GEOMETRIA_CAMADAS, key="camada_tipo_geometria")
                    srid = st.number_input("srid", min_value=0, value=4674, step=1, key="camada_srid")
                    fonte = st.text_input("fonte", key="camada_fonte")
                    orgao_produtor = st.text_input("orgao_produtor", key="camada_orgao_produtor")
                    ano_referencia = st.number_input(
                        "ano_referencia",
                        min_value=0,
                        max_value=3000,
                        value=0,
                        step=1,
                        key="camada_ano_referencia",
                    )
                    campo_valor_principal = st.text_input("campo_valor_principal", key="camada_campo_valor_principal")
                    campos_descritivos_txt = st.text_area("campos_descritivos separados por vírgula", key="camada_campos_descritivos")
                    metrica_padrao = st.selectbox("metrica_padrao", METRICAS_CAMADAS, key="camada_metrica_padrao")
                    tipo_processamento = st.selectbox("tipo_processamento", TIPOS_PROCESSAMENTO_CAMADAS, key="camada_tipo_processamento")

                st.markdown("#### Unidades e saídas")
                u1, u2, u3, u4 = st.columns(4)
                usar_area_interesse = u1.checkbox("Área de interesse", value=True, key="camada_usar_area")
                usar_buffer_1000m = u2.checkbox("Buffer 1000 m", value=True, key="camada_usar_buffer")
                usar_microbacia = u3.checkbox("Microbacia", value=True, key="camada_usar_microbacia")
                usar_setor_censitario = u4.checkbox("Setor censitário", value=False, key="camada_usar_setor")

                s1, s2, s3, s4 = st.columns(4)
                exibir_dashboard = s1.checkbox("Dashboard", value=True, key="camada_dashboard")
                exportar_gpkg = s2.checkbox("GPKG", value=True, key="camada_gpkg")
                incluir_relatorio = s3.checkbox("Relatório", value=True, key="camada_relatorio")
                ativo = s4.checkbox("Ativo", value=True, key="camada_ativo")

                observacao = st.text_area("observacao", key="camada_observacao")
                confirmar = st.checkbox("Confirmo gravar somente em config.camadas_analise", key="camada_confirmar")
                submitted = st.form_submit_button("Salvar camada")

            if submitted:
                if not confirmar:
                    st.warning("Marque a confirmação antes de salvar.")
                elif not nome_logico.strip() or not titulo.strip() or not schema_name.strip() or not table_name.strip():
                    st.warning("Informe ao menos nome_logico, título, schema_name e table_name.")
                else:
                    dados = {
                        "nome_logico": nome_logico.strip(),
                        "titulo": titulo.strip(),
                        "grupo": grupo.strip() or None,
                        "tema": tema.strip() or None,
                        "subtema": subtema.strip() or None,
                        "schema_name": schema_name.strip(),
                        "table_name": table_name.strip(),
                        "geom_column": geom_column.strip() or "geom",
                        "pk_column": pk_column.strip() or None,
                        "tipo_geometria": tipo_geometria,
                        "srid": int(srid) if srid else None,
                        "fonte": fonte.strip() or None,
                        "orgao_produtor": orgao_produtor.strip() or None,
                        "ano_referencia": int(ano_referencia) if ano_referencia else None,
                        "campo_valor_principal": campo_valor_principal.strip() or None,
                        "campos_descritivos": json.dumps(lista_csv(campos_descritivos_txt), ensure_ascii=False),
                        "metrica_padrao": metrica_padrao,
                        "tipo_processamento": tipo_processamento,
                        "usar_area_interesse": usar_area_interesse,
                        "usar_buffer_1000m": usar_buffer_1000m,
                        "usar_microbacia": usar_microbacia,
                        "usar_setor_censitario": usar_setor_censitario,
                        "exibir_dashboard": exibir_dashboard,
                        "exportar_gpkg": exportar_gpkg,
                        "incluir_relatorio": incluir_relatorio,
                        "ativo": ativo,
                        "observacao": observacao.strip() or None,
                    }
                    ok, mensagem = salvar_camada_analise(dados)
                    if ok:
                        st.success(mensagem)
                    else:
                        st.warning(f"Não foi possível salvar a camada: {mensagem}")

    with tab_inventario:
        renderizar_inventario_nova_base()

    with tab_oficial:
        renderizar_importacao_oficial()

    with tab_staging:
        renderizar_importacao_staging()

def pagina_configurar() -> None:
    """Pagina Compor diagnostico organizada em projeto, limites e camadas."""
    st.title("Compor diagnóstico")
    st.caption(
        "Configure os limites e camadas que orientarão o diagnóstico. "
        "Nesta versão, a seleção alimenta a sessão e os comandos; o processamento seletivo real ainda é etapa futura."
    )

    projeto_id = st.session_state.get("projeto_id")
    area_id = st.session_state.get("area_interesse_id")
    projeto_nome = st.session_state.get("projeto_nome") or "-"
    area_nome = st.session_state.get("area_interesse_nome") or "-"
    pasta_sig = st.session_state.get("projeto_sig_dir") or "-"

    st.markdown("### Passo 1 - Projeto e área")
    if not projeto_id or not area_id:
        st.warning("Nenhum projeto/área selecionado. Clique em Início > Iniciar projeto.")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Projeto ID", projeto_id or "-")
    c2.metric("Nome do projeto", projeto_nome)
    c3.metric("Área de interesse ID", area_id or "-")
    c4.metric("Nome da área", area_nome)
    c5.metric("Pasta SIG", pasta_sig)

    result = carregar_camadas_analise_ativas()
    atual = parametros()
    selecionadas_atuais = st.session_state.get("camadas_selecionadas") or atual.get("camadas_selecionadas") or camadas_ambientais_padrao()

    # O formulario evita que cada checkbox reprocesse a configuracao. A sessao so
    # recebe novos limites/camadas quando o usuario clica no botao final.
    with st.form("form_compor_diagnostico"):
        st.markdown("### Passo 2 - Limites de análise")
        l1, l2, l3, l4, l5 = st.columns(5)
        usar_area = l1.checkbox("Área de interesse", value=bool(atual.get("area_interesse", True)), key="compor_limite_area")
        usar_buffer = l2.checkbox("Buffer", value=bool(atual.get("usar_buffer", True)), key="compor_limite_buffer")
        usar_micro = l3.checkbox("Microbacias", value=bool(atual.get("microbacias", True)), key="compor_limite_micro")
        usar_setores = l4.checkbox("Setores censitários", value=bool(atual.get("setores_censitarios", True)), key="compor_limite_setores")
        l5.checkbox("Município", value=False, disabled=True, key="compor_limite_municipio")
        distancia = int(atual.get("distancia_buffer_m") or 1000)
        if usar_buffer:
            distancia = st.number_input(
                "Distância do buffer (m)",
                min_value=0,
                value=distancia,
                step=100,
                key="compor_distancia_buffer",
            )

        st.markdown("### Passo 3 - Camadas e atributos")
        novas_selecionadas: list[str] = []
        socioeconomia = st.checkbox(
            ANALISES_ROTULOS["socioeconomia"],
            value=bool(atual.get("socioeconomia", True)),
            key="compor_socioeconomia",
        )

        if result.ok and not result.data.empty:
            data = result.data.copy()
            for grupo, grupo_df in data.groupby("grupo", dropna=False, sort=True):
                grupo_txt = str(grupo or "Sem grupo")
                with st.expander(grupo_txt.replace("_", " ").title(), expanded=False):
                    for _, row in grupo_df.sort_values(["ordem_exibicao", "titulo"], na_position="last").iterrows():
                        nome_logico = str(row.get("nome_logico") or "").strip()
                        if not nome_logico:
                            continue
                        titulo = str(row.get("titulo") or nome_logico).strip()
                        marcado = nome_logico in selecionadas_atuais
                        if st.checkbox(titulo, value=marcado, key=make_key("compor", "camada", nome_logico)):
                            novas_selecionadas.append(nome_logico)
                        schema = str(row.get("schema_name") or "").strip()
                        tabela = str(row.get("table_name") or "").strip()
                        metrica = str(row.get("metrica_padrao") or "").strip()
                        detalhes = " | ".join(item for item in (f"{schema}.{tabela}" if schema and tabela else "", f"métrica: {metrica}" if metrica else "") if item)
                        if detalhes:
                            st.caption(detalhes)
        else:
            st.warning(
                "A configuração dinâmica de camadas ainda não está disponível. "
                "Aplique o script sql/11_config_camadas_analise.sql no banco para habilitar a seleção por cadastro."
            )
            for chave in ANALISES_AMBIENTAIS:
                if st.checkbox(
                    ANALISES_ROTULOS[chave],
                    value=bool(atual.get(chave, chave != "hidrografia_ana")),
                    key=make_key("compor", "fallback", chave),
                ):
                    novas_selecionadas.append(chave)

        submitted = st.form_submit_button("Salvar configuração do diagnóstico", type="primary")

    if submitted:
        limites_selecionados = []
        if usar_area:
            limites_selecionados.append("area_interesse")
        if usar_buffer:
            limites_selecionados.append("buffer_1000m")
        if usar_micro:
            limites_selecionados.append("microbacia")
        if usar_setores:
            limites_selecionados.append("setores_censitarios")

        st.session_state["limites_selecionados"] = limites_selecionados
        st.session_state["camadas_selecionadas"] = novas_selecionadas
        st.session_state["parametros_diagnostico"] = sincronizar_parametros_camadas(
            novas_selecionadas,
            socioeconomia,
            usar_area,
            usar_buffer,
            usar_micro,
            usar_setores,
            int(distancia),
        )
        st.success("Configuração salva. Siga para Dashboard ou Exportações.")

    with st.expander("Configuração atual", expanded=False):
        st.json(
            {
                "limites_selecionados": st.session_state.get("limites_selecionados"),
                "camadas_selecionadas": st.session_state.get("camadas_selecionadas"),
                "parametros_diagnostico": st.session_state.get("parametros_diagnostico"),
            }
        )


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
    """Pagina Exportacoes: monta comandos, mas nao executa automaticamente."""
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
            "camadas_selecionadas": st.session_state.get("camadas_selecionadas"),
            "unidades_analise": {
                "area_interesse": parametros().get("area_interesse"),
                "buffer_1000m": parametros().get("usar_buffer"),
                "microbacias": parametros().get("microbacias"),
                "setores_censitarios": parametros().get("setores_censitarios"),
            },
            "buffer": {
                "usar_buffer": parametros().get("usar_buffer"),
                "distancia_buffer_m": parametros().get("distancia_buffer_m"),
            },
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
    """Mostra tabelas de resultado ja processadas para a execucao escolhida."""
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
    """Renderiza mapa Folium com camadas do projeto e da execucao."""
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

def exibir_fisico_biotico_resumo(classes_fb: pd.DataFrame, limite_analise: str, contexto: str = "dashboard") -> None:
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
    exibir_plotly(fig_classes, key=make_key(contexto, "fb_classes", limite_analise))

    fig_dominante = px.bar(
        resumo.sort_values("percentual_dominante"),
        x="percentual_dominante",
        y="tema",
        orientation="h",
        title="Percentual dominante por tema",
    )
    exibir_plotly(fig_dominante, key=make_key(contexto, "fb_dominante", limite_analise))

    fig_area = px.bar(
        resumo.sort_values("area_total_ha"),
        x="area_total_ha",
        y="tema",
        orientation="h",
        title="Área total por tema (ha)",
    )
    exibir_plotly(fig_area, key=make_key(contexto, "fb_area_tema", limite_analise))

    classes_top = classes_fb.sort_values("area_ha", ascending=False).head(25).copy()
    if not classes_top.empty:
        classes_top["classe_tema"] = classes_top["tema"].astype(str) + " - " + classes_top["valor_principal"].astype(str)
        fig_area_classe = px.bar(
            classes_top.sort_values("area_ha"),
            x="area_ha",
            y="classe_tema",
            color="tema",
            orientation="h",
            title="Área por classe temática (ha)",
        )
        exibir_plotly(fig_area_classe, key=make_key(contexto, "fb_area_classe", limite_analise))


def exibir_socioeconomico_resumo(total_socio: pd.DataFrame, contexto_socio: pd.DataFrame, contexto: str = "dashboard") -> None:
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
            exibir_plotly(fig_status, key=make_key(contexto, "socio_status_dados"))
        if {"cd_setor", "populacao_total_setor"}.issubset(contexto_socio.columns):
            fig_pop = px.bar(
                contexto_socio,
                x="cd_setor",
                y="populacao_total_setor",
                title="População por setor censitário",
            )
            exibir_plotly(fig_pop, key=make_key(contexto, "socio_populacao_setor"))
        if {"cd_setor", "total_domicilios_setor"}.issubset(contexto_socio.columns):
            fig_dom = px.bar(
                contexto_socio,
                x="cd_setor",
                y="total_domicilios_setor",
                title="Domicílios por setor censitário",
            )
            exibir_plotly(fig_dom, key=make_key(contexto, "socio_domicilios_setor"))
        if {"cd_setor", "renda_media_responsavel_setor"}.issubset(contexto_socio.columns):
            fig_renda = px.bar(
                contexto_socio,
                x="cd_setor",
                y="renda_media_responsavel_setor",
                title="Renda média por setor censitário",
            )
            exibir_plotly(fig_renda, key=make_key(contexto, "socio_renda_setor"))

    st.markdown("#### Pirâmide etária")
    colunas_piramide = {"faixa_etaria", "sexo", "populacao"}
    if colunas_piramide.issubset(contexto_socio.columns):
        piramide = contexto_socio.groupby(["faixa_etaria", "sexo"], dropna=False, as_index=False)["populacao"].sum()
        fig_piramide = go.Figure()
        for sexo, sinal in (("Masculino", -1), ("Feminino", 1)):
            dados = piramide[piramide["sexo"].astype(str).str.lower() == sexo.lower()]
            fig_piramide.add_trace(
                go.Bar(
                    y=dados["faixa_etaria"],
                    x=dados["populacao"] * sinal,
                    name=sexo,
                    orientation="h",
                )
            )
        fig_piramide.update_layout(title="Pirâmide etária", barmode="relative")
        exibir_plotly(fig_piramide, key=make_key(contexto, "socio_piramide_etaria"))
    else:
        st.info("Dados de pirâmide etária e estrutura por sexo ainda não disponíveis para esta execução.")

    st.markdown("#### Estrutura por sexo")
    if {"sexo", "populacao"}.issubset(contexto_socio.columns):
        sexo = contexto_socio.groupby("sexo", dropna=False, as_index=False)["populacao"].sum()
        fig_sexo = px.bar(sexo, x="sexo", y="populacao", title="Estrutura por sexo")
        exibir_plotly(fig_sexo, key=make_key(contexto, "socio_estrutura_sexo"))
    else:
        st.info("Dados de estrutura por sexo ainda não disponíveis para esta execução.")


def exibir_hidrografia_resumo(hidrografia: pd.DataFrame, limite_analise: str, contexto: str = "dashboard") -> None:
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
        exibir_plotly(fig_micro, key=make_key(contexto, "hidrografia_microbacia", limite_analise))

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
        exibir_plotly(fig_comprimento, key=make_key(contexto, "hidrografia_comprimento_ordem", limite_analise))
        fig_quantidade = px.bar(
            por_ordem,
            x="nuordemcda",
            y="quantidade_trechos",
            title="Quantidade de trechos por ordem do curso d'água",
        )
        exibir_plotly(fig_quantidade, key=make_key(contexto, "hidrografia_quantidade_ordem", limite_analise))


def pagina_resumo_estatistico() -> None:
    """Pagina de graficos e indicadores resumidos do diagnostico."""
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

def valor_coluna_linha(data: pd.DataFrame, colunas: tuple[str, ...]) -> Any:
    """Retorna o primeiro valor disponivel entre nomes de colunas possiveis."""
    if data.empty:
        return None
    linha = data.iloc[0]
    for coluna in colunas:
        if coluna in linha and pd.notna(linha.get(coluna)):
            return linha.get(coluna)
    return None


def renderizar_mapa_folium_dashboard(
    projeto_id: int,
    area_interesse_id: int,
    execucao_id: int | None,
    distancia_buffer_m: int,
    contexto: str,
) -> None:
    """Renderiza o mapa operacional dentro do Dashboard com fit_bounds e LayerControl."""
    # O Folium trabalha em EPSG:4326 para exibicao web; as consultas ja devolvem
    # GeoJSON nessa projeção, enquanto os calculos oficiais permanecem no PostGIS.
    if folium is None or st_folium is None:
        st.warning("Instale folium e streamlit-folium para visualizar o mapa.")
        return

    c1, c2, c3, c4, c5 = st.columns(5)
    mostrar_area = c1.checkbox("Área de interesse", value=True, key=make_key(contexto, "mapa", "area"))
    mostrar_buffer = c2.checkbox("Buffer", value=True, key=make_key(contexto, "mapa", "buffer"))
    mostrar_microbacias = c3.checkbox("Microbacias", value=True, key=make_key(contexto, "mapa", "microbacias"))
    mostrar_setores = c4.checkbox("Setores censitários", value=execucao_id is not None, key=make_key(contexto, "mapa", "setores"))
    mostrar_hidrografia = c5.checkbox("Hidrografia", value=execucao_id is not None and hidrografia_marcada(), key=make_key(contexto, "mapa", "hidrografia"))

    mapa = folium.Map(location=[-27.6, -48.5], zoom_start=10, tiles="OpenStreetMap")
    camada_area = None
    try:
        with get_connection() as conn:
            conn.set_session(readonly=True, autocommit=True)
            if mostrar_area:
                camada_area = adicionar_geojson(
                    mapa,
                    carregar_geojson_area_interesse(conn, projeto_id, area_interesse_id),
                    "Área de interesse",
                    estilo_area_interesse,
                )
                if camada_area is None:
                    st.info("Área de interesse sem geometria disponível para o mapa.")
            if mostrar_buffer:
                camada_buffer = adicionar_geojson(
                    mapa,
                    carregar_geojson_buffer(conn, projeto_id, area_interesse_id, distancia_buffer_m),
                    f"Buffer {distancia_buffer_m} m",
                    estilo_buffer,
                )
                if camada_buffer is None:
                    st.info("Buffer sem geometria disponível para o mapa.")
            if mostrar_microbacias:
                camada_micro = adicionar_geojson(
                    mapa,
                    carregar_geojson_microbacias(conn, projeto_id, area_interesse_id),
                    "Microbacias interceptadas",
                    estilo_microbacias,
                )
                if camada_micro is None:
                    st.info("Nenhuma microbacia disponível para o mapa.")
            if mostrar_setores:
                if execucao_id is None:
                    st.info("Informe uma execução para carregar setores censitários.")
                else:
                    camada_setores = adicionar_geojson(
                        mapa,
                        carregar_geojson_setores(conn, execucao_id, projeto_id, area_interesse_id),
                        "Setores censitários",
                        estilo_setores,
                    )
                    if camada_setores is None:
                        st.info("Nenhum setor censitário disponível para esta execução.")
            if mostrar_hidrografia:
                if execucao_id is None:
                    st.info("Informe uma execução para carregar hidrografia.")
                else:
                    camada_hidro = adicionar_geojson(
                        mapa,
                        carregar_geojson_hidrografia(conn, execucao_id, projeto_id, area_interesse_id),
                        "Hidrografia ANA",
                        estilo_hidrografia,
                    )
                    if camada_hidro is None:
                        st.info("Nenhuma hidrografia disponível para esta execução.")
    except Exception as exc:  # pragma: no cover - exibido na interface
        st.warning(f"Não foi possível carregar todas as camadas do mapa: {exc}")

    if camada_area is not None:
        try:
            mapa.fit_bounds(camada_area.get_bounds())
        except Exception:
            pass
    folium.LayerControl().add_to(mapa)
    st_folium(mapa, width=None, height=650, key=make_key(contexto, "folium"))


def exibir_cards_resumo_dashboard(
    sintese: pd.DataFrame,
    classes_fb: pd.DataFrame,
    total_socio: pd.DataFrame,
    hidrografia: pd.DataFrame,
    microbacias: pd.DataFrame,
) -> None:
    """Mostra indicadores-chave do Dashboard sem quebrar quando algum dado falta."""
    area_ha = valor_coluna_linha(sintese, ("area_interesse_ha", "area_ha", "area_total_ha"))
    total_classes = classes_fb["valor_principal"].nunique(dropna=True) if "valor_principal" in classes_fb.columns else None
    populacao = valor_coluna_linha(total_socio, ("populacao_total_setores", "populacao_estimada"))
    domicilios = valor_coluna_linha(total_socio, ("total_domicilios_setores", "total_domicilios"))
    comprimento = hidrografia["comprimento_total_km"].sum(skipna=True) if "comprimento_total_km" in hidrografia.columns else None
    numero_micro = microbacias["cd_micro"].nunique(dropna=True) if "cd_micro" in microbacias.columns else None

    cols = st.columns(6)
    cols[0].metric("Área de interesse ha", formatar_numero(area_ha, 4))
    cols[1].metric("Classes físico-bióticas", formatar_inteiro(total_classes))
    cols[2].metric("População total", formatar_inteiro(populacao))
    cols[3].metric("Domicílios totais", formatar_inteiro(domicilios))
    cols[4].metric("Hidrografia km", formatar_numero(comprimento, 3))
    cols[5].metric("Microbacias", formatar_inteiro(numero_micro))


def criar_figura_explorador(data: pd.DataFrame, tipo: str, eixo_x: str, eixo_y: str | None, cor: str | None) -> Any:
    """Cria figuras Plotly dinamicas a partir das escolhas do Explorador Analitico."""
    color_arg = cor if cor and cor != "Nenhum" else None
    if tipo == "Barra":
        return px.bar(data, x=eixo_x, y=eixo_y, color=color_arg)
    if tipo == "Barra horizontal":
        return px.bar(data, x=eixo_y, y=eixo_x, color=color_arg, orientation="h")
    if tipo == "Linha":
        return px.line(data, x=eixo_x, y=eixo_y, color=color_arg)
    if tipo == "Dispersão":
        return px.scatter(data, x=eixo_x, y=eixo_y, color=color_arg)
    if tipo == "Histograma":
        return px.histogram(data, x=eixo_x, color=color_arg)
    return px.box(data, x=eixo_x, y=eixo_y, color=color_arg)


def renderizar_explorador_analitico(fontes: dict[str, pd.DataFrame], contexto: str) -> None:
    """Explorador analitico com fonte, tipo de grafico e variaveis selecionaveis."""
    # Esta aba nao cria dados novos: ela apenas reutiliza DataFrames ja carregados
    # pelas views do Dashboard e oferece combinacoes visuais com Plotly Express.
    st.subheader("Explorador analítico")
    fonte = st.selectbox("Fonte de dados", list(fontes.keys()), key=make_key(contexto, "fonte"))
    data = fontes.get(fonte, pd.DataFrame()).copy()
    if data.empty:
        st.info("A fonte selecionada não possui dados para os filtros atuais.")
        return

    tipo = st.selectbox(
        "Tipo de gráfico",
        ["Barra", "Barra horizontal", "Linha", "Dispersão", "Histograma", "Box plot"],
        key=make_key(contexto, "tipo_grafico"),
    )
    colunas = [str(coluna) for coluna in data.columns]
    numericas = [coluna for coluna in colunas if pd.api.types.is_numeric_dtype(data[coluna])]
    eixo_x = st.selectbox("Eixo X", colunas, key=make_key(contexto, fonte, "x"))
    eixo_y: str | None = None
    if tipo not in {"Histograma"}:
        opcoes_y = numericas or colunas
        eixo_y = st.selectbox("Eixo Y", opcoes_y, key=make_key(contexto, fonte, "y"))
    cor = st.selectbox("Cor / agrupamento", ["Nenhum"] + colunas, key=make_key(contexto, fonte, "cor"))

    try:
        fig = criar_figura_explorador(data, tipo, eixo_x, eixo_y, cor)
        fig.update_layout(title=f"{fonte} - {tipo}")
        exibir_plotly(fig, key=make_key("explorador", fonte, tipo, eixo_x, eixo_y, cor))
    except Exception as exc:
        st.warning(f"Não foi possível montar o gráfico com essas variáveis: {exc}")

    st.markdown("#### Dados usados no gráfico")
    st.dataframe(data, use_container_width=True)


def exibir_dados_brutos_dashboard(fontes: dict[str, pd.DataFrame]) -> None:
    """Organiza os DataFrames do Dashboard em expanders para reduzir poluicao visual."""
    for nome, data in fontes.items():
        with st.expander(nome, expanded=False):
            if data.empty:
                st.info("Sem dados para os filtros atuais.")
            else:
                st.dataframe(data, use_container_width=True)
    with st.expander("Camadas selecionadas", expanded=False):
        st.json(st.session_state.get("camadas_selecionadas") or [])


def pagina_dashboard() -> None:
    """Dashboard guiado com mapa, resumo, temas e Explorador Analitico."""
    st.title("Dashboard")
    st.caption("Centro de análise do MVP: mapa, resumo, temas, exploração gráfica e dados brutos.")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        projeto_id = st.number_input("Projeto", min_value=1, value=int(st.session_state.get("projeto_id") or 1), key="dash_projeto_id")
    with col2:
        area_interesse_id = st.number_input("Área de interesse", min_value=1, value=int(st.session_state.get("area_interesse_id") or 1), key="dash_area_id")
    with col3:
        execucao_id_txt = st.text_input("Execução", value=str(st.session_state.get("execucao_id") or ""), key="dash_execucao_id").strip()
    with col4:
        limite_label = st.selectbox("Limite de análise", list(LIMITES_ANALISE_RESUMO.keys()), key="dash_limite")

    st.session_state["projeto_id"] = int(projeto_id)
    st.session_state["area_interesse_id"] = int(area_interesse_id)
    st.session_state["execucao_id"] = execucao_id_txt

    limite_analise = LIMITES_ANALISE_RESUMO[limite_label]
    execucao_id: int | None = None
    if execucao_id_txt:
        try:
            execucao_id = int(execucao_id_txt)
        except ValueError:
            st.warning("Informe um execucao_id numérico para carregar estatísticas.")

    sintese = pd.DataFrame()
    classes_fb = pd.DataFrame()
    total_socio = pd.DataFrame()
    contexto_socio = pd.DataFrame()
    hidrografia = pd.DataFrame()
    microbacias = pd.DataFrame()

    if execucao_id is not None:
        try:
            with get_connection() as conn:
                conn.set_session(readonly=True, autocommit=True)
                if view_existe_conn(conn, "resultados.vw_relatorio_sintese_executiva"):
                    sintese = executar_select_df(
                        conn,
                        """
                        SELECT *
                        FROM resultados.vw_relatorio_sintese_executiva
                        WHERE execucao_id = %s
                          AND projeto_id = %s
                          AND area_interesse_id = %s;
                        """,
                        (execucao_id, int(projeto_id), int(area_interesse_id)),
                    )
                microbacias = carregar_microbacias_resumo(conn, execucao_id, int(projeto_id), int(area_interesse_id))
                if limite_analise != "setores_censitarios":
                    classes_fb = carregar_fisico_biotico_resumo(conn, limite_analise, execucao_id, int(projeto_id), int(area_interesse_id), None)
                    hidrografia = carregar_hidrografia_resumo(conn, limite_analise, execucao_id, int(projeto_id), int(area_interesse_id), None)
                total_socio = carregar_socio_total_setores(conn, execucao_id, int(projeto_id), int(area_interesse_id))
                contexto_socio = carregar_socio_contexto_setores(conn, execucao_id, int(projeto_id), int(area_interesse_id))
        except Exception as exc:  # pragma: no cover - exibido na interface
            st.error(f"Não foi possível carregar os dados do Dashboard: {exc}")
    else:
        st.info("Informe uma execução para carregar os dados analíticos.")

    fontes = {
        "Síntese executiva": sintese,
        "Físico-biótico": classes_fb,
        "Socioeconômico": contexto_socio if not contexto_socio.empty else total_socio,
        "Hidrografia": hidrografia,
    }

    tabs = st.tabs(["Mapa", "Resumo", "Físico-biótico", "Socioeconômico", "Hidrografia", "Explorador analítico", "Dados brutos"])
    with tabs[0]:
        distancia = int(parametros().get("distancia_buffer_m") or 1000)
        renderizar_mapa_folium_dashboard(int(projeto_id), int(area_interesse_id), execucao_id, distancia, "dashboard_mapa")
    with tabs[1]:
        exibir_cards_resumo_dashboard(sintese, classes_fb, total_socio, hidrografia, microbacias)
    with tabs[2]:
        exibir_fisico_biotico_resumo(classes_fb, limite_analise, contexto="dashboard_fisico_biotico")
    with tabs[3]:
        exibir_socioeconomico_resumo(total_socio, contexto_socio, contexto="dashboard_socioeconomico")
    with tabs[4]:
        exibir_hidrografia_resumo(hidrografia, limite_analise, contexto="dashboard_hidrografia")
    with tabs[5]:
        renderizar_explorador_analitico(fontes, contexto="dashboard_explorador")
    with tabs[6]:
        exibir_dados_brutos_dashboard(fontes)


def pagina_administracao() -> None:
    """Area tecnica para status do banco, execucoes e parametros de sessao."""
    st.title("Administração")
    st.caption("Status, execucoes, parametros de sessao e informacoes tecnicas da interface interna.")

    st.subheader("Status do banco")
    status = testar_conexao()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Conexão", "OK" if status["ok"] else "Indisponível")
    col2.metric("Banco", status.get("database") or "-")
    col3.metric("Projetos cadastrados", status.get("total_projetos") or 0)
    col4.metric("Modo", MODO_APP)

    st.subheader("Últimas execuções")
    ultimas = carregar_ultimas_execucoes(30)
    if ultimas.ok and not ultimas.data.empty:
        c1, c2 = st.columns(2)
        with c1:
            por_status = ultimas.data.groupby("status", dropna=False, as_index=False).agg(total=("id", "count"))
            fig_status = px.bar(por_status, x="status", y="total", title="Execucoes por status")
            exibir_plotly(fig_status, key="admin_execucoes_status")
        with c2:
            por_tipo = ultimas.data.groupby("tipo_execucao", dropna=False, as_index=False).agg(total=("id", "count"))
            fig_tipo = px.bar(por_tipo, x="tipo_execucao", y="total", title="Execucoes por tipo")
            exibir_plotly(fig_tipo, key="admin_execucoes_tipo")
        st.dataframe(ultimas.data, use_container_width=True)
    elif ultimas.ok:
        st.info("Nenhuma execucao recente encontrada.")
    else:
        st.warning(ultimas.erro or "Nao foi possivel consultar execucoes.")

    camadas = carregar_camadas_analise_ativas()
    if camadas.ok and not camadas.data.empty:
        st.subheader("Camadas ativas por grupo")
        exibir_graficos_camadas(camadas.data)

    with st.expander("Parametros de sessao", expanded=False):
        st.json({key: str(value) for key, value in st.session_state.items()})

    with st.expander("Pendencias operacionais", expanded=False):
        st.markdown(
            "- Login e controle de acesso.\n"
            "- Pagina publica somente leitura.\n"
            "- Testar upload real de area de interesse em ambiente autorizado.\n"
            "- Importacao real de dados oficiais para PostGIS.\n"
            "- Processamento seletivo real por camada.\n"
            "- Geracao de relatorio DOCX.\n"
            "- Refinamento visual do dashboard."
        )
def main() -> None:
    """Ponto de entrada da interface: configura pagina, estado e menu lateral."""
    configurar_pagina()
    inicializar_estado()

    st.sidebar.title("EA2S SIG")
    pagina = st.sidebar.radio("Navegação", PAGE_OPTIONS)
    st.sidebar.caption(f"WebGIS operacional | modo {MODO_APP}")

    if pagina == "Início":
        pagina_inicio()
    elif pagina == "Banco de dados geográficos":
        pagina_camadas_analise()
    elif pagina == "Compor diagnóstico":
        pagina_configurar()
    elif pagina == "Dashboard":
        pagina_dashboard()
    elif pagina == "Exportações":
        pagina_executar()
    elif pagina == "Administração":
        pagina_administracao()

if __name__ == "__main__":
    main()
