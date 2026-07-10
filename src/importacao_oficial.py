"""Fluxo local de importacao direta controlada para schema oficial.

Este modulo simplifica o caminho principal do EA2S SIG:
Inventario -> validacao tecnica -> correcao opcional -> importacao oficial.

Ele nao apaga, substitui ou trunca tabelas. A importacao oficial sempre cria
uma tabela nova no schema destino informado e registra o controle em
`importacao.importacao_oficial`.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import json

import geopandas as gpd
import pandas as pd
from psycopg2 import sql

from importacao_staging import (
    PROJECT_ROOT,
    SRID_STAGING_PADRAO,
    _carregar_metadados_inventario,
    _carregar_perfil,
    _criar_engine_sqlalchemy,
    _ler_arquivo_geografico,
    _normalizar_identificador,
    aplicar_perfil_confirmado,
    localizar_arquivo_original,
)

SCHEMAS_OPERACIONAIS_BLOQUEADOS = {"importacao", "staging", "resultados", "logs", "config", "public"}
PASTA_CORRIGIDOS = PROJECT_ROOT / "data/importacao/corrigidos"


def gerar_nome_tabela_oficial(
    schema_destino: str | None,
    tabela_destino_sugerida: str | None,
    fonte: str | None = None,
    ano_referencia: int | str | None = None,
) -> str:
    """Gera nome seguro para tabela oficial, sem sobrescrever a existencia no banco."""
    del schema_destino
    base = _normalizar_identificador(tabela_destino_sugerida or "camada")
    partes = [base]
    fonte_norm = _normalizar_identificador(fonte or "") if fonte else ""
    ano = str(ano_referencia).strip() if ano_referencia else ""
    if fonte_norm and fonte_norm not in base:
        partes.append(fonte_norm)
    if ano and ano not in base:
        partes.append(ano)
    nome = _normalizar_identificador("_".join(partes))
    return nome[:63].strip("_") or "camada"


def pasta_corrigidos_inventario(lote_id: int, inventario_arquivo_id: int) -> Path:
    return PASTA_CORRIGIDOS / f"lote_{int(lote_id)}" / f"inventario_{int(inventario_arquivo_id)}"


def _serie_geometria(gdf: gpd.GeoDataFrame) -> gpd.GeoSeries:
    if gdf.geometry is None:
        raise RuntimeError("A base nao possui coluna geometrica ativa.")
    return gdf.geometry


def _contar_geometrias_invalidas(gdf: gpd.GeoDataFrame) -> int:
    geom = _serie_geometria(gdf)
    validas = geom.is_valid.fillna(False)
    existentes = geom.notna()
    return int((existentes & ~validas).sum())


def _contar_geometrias_nulas(gdf: gpd.GeoDataFrame) -> int:
    return int(_serie_geometria(gdf).isna().sum())


def testar_correcao_geometrias(gdf: gpd.GeoDataFrame) -> dict[str, Any]:
    """Tenta corrigir geometrias em memoria, preservando o arquivo original."""
    antes_invalidas = _contar_geometrias_invalidas(gdf)
    feicoes_antes = int(len(gdf))
    corrigido = gdf.copy()
    metodo = "sem_correcao"

    if antes_invalidas > 0:
        try:
            from shapely import make_valid

            corrigido["geom"] = corrigido.geometry.apply(lambda geom: make_valid(geom) if geom is not None else geom)
            if corrigido.geometry.name != "geom":
                corrigido = corrigido.set_geometry("geom")
            metodo = "shapely.make_valid"
        except Exception:
            def corrigir_buffer_zero(geom: Any) -> Any:
                if geom is None:
                    return geom
                if getattr(geom, "geom_type", "") in {"Polygon", "MultiPolygon"}:
                    return geom.buffer(0)
                return geom

            corrigido["geom"] = corrigido.geometry.apply(corrigir_buffer_zero)
            if corrigido.geometry.name != "geom":
                corrigido = corrigido.set_geometry("geom")
            metodo = "buffer_0_poligonal"

    depois_invalidas = _contar_geometrias_invalidas(corrigido)
    return {
        "gdf": corrigido,
        "geometrias_invalidas_antes": antes_invalidas,
        "geometrias_invalidas_depois": depois_invalidas,
        "feicoes_antes": feicoes_antes,
        "feicoes_depois": int(len(corrigido)),
        "metodo_aplicado": metodo,
        "corrigiu_geometrias": antes_invalidas > depois_invalidas,
        "status_final": "valido" if depois_invalidas == 0 else "pendencias",
    }


def _schema_existe(conn: Any, schema: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = %s);", (schema,))
        return bool(cur.fetchone()[0])


def _tabela_existe(conn: Any, schema: str, tabela: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_name = %s
            );
            """,
            (schema, tabela),
        )
        return bool(cur.fetchone()[0])


def _sugerir_nome_v2(tabela: str) -> str:
    base = tabela[:60].rstrip("_")
    return f"{base}_v2"


def _preparar_gdf(inventario: dict[str, Any], conn: Any, inventario_arquivo_id: int) -> tuple[gpd.GeoDataFrame, Path, int | None]:
    caminho = localizar_arquivo_original(inventario)
    if caminho is None:
        raise RuntimeError("O arquivo persistido nao foi encontrado. Reenvie ou persista novamente a base antes de importar.")
    gdf = _ler_arquivo_geografico(caminho, inventario.get("layer_name"))
    if gdf.empty:
        raise RuntimeError("Arquivo lido sem feicoes para importar.")
    if gdf.geometry is None:
        raise RuntimeError("Arquivo sem geometria ativa.")
    if gdf.geometry.name != "geom":
        gdf = gdf.rename_geometry("geom")
    srid_origem = inventario.get("srid_detectado") or (gdf.crs.to_epsg() if gdf.crs else None)
    if srid_origem and gdf.crs is None:
        gdf = gdf.set_crs(int(srid_origem), allow_override=True)
    perfil = _carregar_perfil(conn, inventario_arquivo_id)
    gdf = aplicar_perfil_confirmado(gdf, perfil)
    if gdf.geometry.name != "geom":
        gdf = gdf.rename_geometry("geom")
    return gdf, caminho, int(srid_origem) if srid_origem else None


def diagnosticar_inventario_para_importacao_oficial(inventario_arquivo_id: int, conn: Any) -> dict[str, Any]:
    """Diagnostica se o inventario pode virar tabela oficial nova."""
    avisos: list[str] = []
    bloqueios: list[str] = []
    inventario = _carregar_metadados_inventario(conn, inventario_arquivo_id)
    schema_destino = str(inventario.get("schema_destino_sugerido") or "").strip()
    tabela_sugerida = gerar_nome_tabela_oficial(
        schema_destino,
        inventario.get("tabela_destino_sugerida"),
        inventario.get("fonte"),
        inventario.get("ano_referencia"),
    )

    caminho = localizar_arquivo_original(inventario)
    if caminho is None:
        bloqueios.append("O arquivo persistido nao foi encontrado. Reenvie ou persista novamente a base antes de importar.")
        return {
            "ok_leitura": False,
            "status_preliminar": "bloqueado",
            "inventario": inventario,
            "schema_destino": schema_destino,
            "tabela_destino": tabela_sugerida,
            "arquivo_persistido": None,
            "geometrias_invalidas": None,
            "geometrias_nulas": None,
            "avisos": avisos,
            "bloqueios": bloqueios,
            "pode_importar": False,
            "pode_importar_com_pendencias": False,
            "tabela_destino_sugerida_v2": _sugerir_nome_v2(tabela_sugerida),
        }

    try:
        gdf, _, srid_origem = _preparar_gdf(inventario, conn, inventario_arquivo_id)
        ok_leitura = True
    except Exception as exc:
        bloqueios.append(str(exc))
        return {
            "ok_leitura": False,
            "status_preliminar": "bloqueado",
            "inventario": inventario,
            "schema_destino": schema_destino,
            "tabela_destino": tabela_sugerida,
            "arquivo_persistido": str(caminho),
            "geometrias_invalidas": None,
            "geometrias_nulas": None,
            "avisos": avisos,
            "bloqueios": bloqueios,
            "pode_importar": False,
            "pode_importar_com_pendencias": False,
            "tabela_destino_sugerida_v2": _sugerir_nome_v2(tabela_sugerida),
        }

    if not schema_destino:
        bloqueios.append("Schema destino nao informado no inventario.")
    elif schema_destino in SCHEMAS_OPERACIONAIS_BLOQUEADOS:
        bloqueios.append(f"Schema destino '{schema_destino}' e operacional, nao oficial.")
    elif not _schema_existe(conn, schema_destino):
        bloqueios.append(f"Schema destino '{schema_destino}' nao existe.")

    if _tabela_existe(conn, schema_destino, tabela_sugerida) if schema_destino else False:
        bloqueios.append(f"Tabela destino {schema_destino}.{tabela_sugerida} ja existe.")

    srid = srid_origem or (gdf.crs.to_epsg() if gdf.crs else None)
    if not srid:
        bloqueios.append("SRID nao identificado. Informe/corrija o SRID antes da importacao oficial.")
    geometrias_nulas = _contar_geometrias_nulas(gdf)
    geometrias_invalidas = _contar_geometrias_invalidas(gdf)
    if geometrias_nulas:
        avisos.append(f"{geometrias_nulas} feicoes com geometria nula.")
    if geometrias_invalidas:
        avisos.append(f"{geometrias_invalidas} geometrias invalidas detectadas.")

    status = "bloqueado" if bloqueios else ("pendencias" if avisos else "valido")
    return {
        "ok_leitura": ok_leitura,
        "status_preliminar": status,
        "inventario": inventario,
        "schema_destino": schema_destino,
        "tabela_destino": tabela_sugerida,
        "arquivo_persistido": str(caminho),
        "srid": int(srid) if srid else None,
        "tipo_geometria": str(gdf.geom_type.dropna().iloc[0]) if not gdf.geom_type.dropna().empty else None,
        "numero_feicoes": int(len(gdf)),
        "geometrias_invalidas": geometrias_invalidas,
        "geometrias_nulas": geometrias_nulas,
        "avisos": avisos,
        "bloqueios": bloqueios,
        "pode_importar": not bloqueios and not avisos,
        "pode_importar_com_pendencias": not bloqueios and bool(avisos),
        "tabela_destino_sugerida_v2": _sugerir_nome_v2(tabela_sugerida),
    }


def testar_correcao_inventario(inventario_arquivo_id: int, conn: Any) -> dict[str, Any]:
    inventario = _carregar_metadados_inventario(conn, inventario_arquivo_id)
    gdf, caminho, _ = _preparar_gdf(inventario, conn, inventario_arquivo_id)
    resultado = testar_correcao_geometrias(gdf)
    resultado["arquivo_persistido"] = str(caminho)
    resultado.pop("gdf", None)
    return resultado


def _colunas_tabela(conn: Any, schema: str, tabela: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s;
            """,
            (schema, tabela),
        )
        return {row[0] for row in cur.fetchall()}


def _cadastrar_em_config_camadas(conn: Any, dados: dict[str, Any], ativo: bool) -> tuple[bool, int | None]:
    if not _tabela_existe(conn, "config", "camadas_analise"):
        return False, None
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id
            FROM config.camadas_analise
            WHERE schema_name = %s
              AND table_name = %s
              AND tema IS NOT DISTINCT FROM %s
            LIMIT 1;
            """,
            (dados["schema_destino"], dados["tabela_destino"], dados.get("tema")),
        )
        existente = cur.fetchone()
        if existente:
            return True, int(existente[0])

    colunas_existentes = _colunas_tabela(conn, "config", "camadas_analise")
    valores = {
        "nome_logico": _normalizar_identificador(dados.get("nome_camada") or dados["tabela_destino"]),
        "titulo": dados.get("nome_camada") or dados["tabela_destino"],
        "grupo": dados.get("grupo"),
        "tema": dados.get("tema"),
        "subtema": dados.get("subtema"),
        "schema_name": dados["schema_destino"],
        "table_name": dados["tabela_destino"],
        "geom_column": "geom",
        "pk_column": None,
        "tipo_geometria": dados.get("tipo_geometria"),
        "srid": dados.get("srid"),
        "fonte": dados.get("fonte"),
        "orgao_produtor": dados.get("orgao_produtor"),
        "ano_referencia": dados.get("ano_referencia"),
        "ativo": bool(ativo),
        "observacao": "Cadastro gerado pelo fluxo de importacao oficial controlada.",
    }
    colunas = [col for col in valores if col in colunas_existentes]
    if not colunas:
        return False, None
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("INSERT INTO config.camadas_analise ({}) VALUES ({}) RETURNING id;").format(
                sql.SQL(", ").join(sql.Identifier(col) for col in colunas),
                sql.SQL(", ").join(sql.Placeholder() for _ in colunas),
            ),
            [valores[col] for col in colunas],
        )
        return True, int(cur.fetchone()[0])


def importar_inventario_para_schema_oficial(
    inventario_arquivo_id: int,
    schema_destino: str,
    tabela_destino: str,
    corrigir_geometrias: bool = False,
    permitir_importar_com_pendencias: bool = False,
    cadastrar_config: bool = False,
    config_ativo: bool = False,
    conn: Any | None = None,
) -> dict[str, Any]:
    """Cria nova tabela no schema oficial e registra importacao controlada."""
    if conn is None:
        raise RuntimeError("Conexao obrigatoria nao informada.")
    try:
        import geoalchemy2  # noqa: F401
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise RuntimeError("Dependencia ausente para to_postgis: geoalchemy2.") from exc

    schema_destino = str(schema_destino or "").strip()
    tabela_destino = _normalizar_identificador(tabela_destino or "")
    avisos: list[str] = []
    bloqueios: list[str] = []
    if not schema_destino or schema_destino in SCHEMAS_OPERACIONAIS_BLOQUEADOS:
        bloqueios.append("Schema destino ausente ou operacional; informe um schema oficial existente.")
    if not tabela_destino:
        bloqueios.append("Nome de tabela destino invalido.")
    if bloqueios:
        raise RuntimeError("; ".join(bloqueios))

    inventario = _carregar_metadados_inventario(conn, inventario_arquivo_id)
    if not _schema_existe(conn, schema_destino):
        raise RuntimeError(f"Schema destino '{schema_destino}' nao existe.")
    if _tabela_existe(conn, schema_destino, tabela_destino):
        raise RuntimeError(f"Tabela destino {schema_destino}.{tabela_destino} ja existe. Sugestao: {_sugerir_nome_v2(tabela_destino)}")

    gdf, caminho, srid_origem = _preparar_gdf(inventario, conn, inventario_arquivo_id)
    geometrias_invalidas_antes = _contar_geometrias_invalidas(gdf)
    metodo_correcao = None
    corrigiu = False
    if corrigir_geometrias and geometrias_invalidas_antes:
        correcao = testar_correcao_geometrias(gdf)
        gdf = correcao["gdf"]
        metodo_correcao = correcao["metodo_aplicado"]
        corrigiu = bool(correcao["corrigiu_geometrias"])
    geometrias_invalidas_depois = _contar_geometrias_invalidas(gdf)
    if geometrias_invalidas_depois:
        avisos.append(f"{geometrias_invalidas_depois} geometrias invalidas apos validacao/correcao.")
    if gdf.crs is not None and gdf.crs.to_epsg() != SRID_STAGING_PADRAO:
        gdf = gdf.to_crs(epsg=SRID_STAGING_PADRAO)
    elif gdf.crs is None:
        raise RuntimeError("SRID ausente. Corrija o inventario antes da importacao oficial.")

    status_qualidade = "valido" if not avisos else "importado_com_pendencias"
    if status_qualidade == "importado_com_pendencias" and not permitir_importar_com_pendencias:
        return {
            "ok": False,
            "status_qualidade": status_qualidade,
            "mensagem": "Importacao com pendencias exige confirmacao explicita.",
            "avisos": avisos,
        }

    gdf["_ea2s_inventario_arquivo_id"] = int(inventario_arquivo_id)
    gdf["_ea2s_lote_id"] = int(inventario["lote_id"])
    gdf["_ea2s_hash_arquivo"] = inventario.get("hash_arquivo")
    gdf["_ea2s_importado_em"] = datetime.now()
    gdf["_ea2s_status_qualidade"] = status_qualidade

    try:
        engine = _criar_engine_sqlalchemy()
        gdf.to_postgis(tabela_destino, engine, schema=schema_destino, if_exists="fail", index=False)
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {}.{} USING GIST ({});").format(
                    sql.Identifier(f"idx_{tabela_destino[:45]}_geom"),
                    sql.Identifier(schema_destino),
                    sql.Identifier(tabela_destino),
                    sql.Identifier("geom"),
                )
            )

        dados_config = {
            "schema_destino": schema_destino,
            "tabela_destino": tabela_destino,
            "nome_camada": inventario.get("tabela_destino_sugerida") or tabela_destino,
            "grupo": inventario.get("grupo_sugerido"),
            "tema": inventario.get("tema_sugerido"),
            "subtema": inventario.get("subtema_sugerido"),
            "fonte": inventario.get("fonte"),
            "orgao_produtor": inventario.get("orgao_produtor"),
            "ano_referencia": inventario.get("ano_referencia"),
            "tipo_geometria": str(gdf.geom_type.dropna().iloc[0]) if not gdf.geom_type.dropna().empty else None,
            "srid": SRID_STAGING_PADRAO,
        }
        cadastrada = False
        camada_analise_id = None
        if cadastrar_config:
            cadastrada, camada_analise_id = _cadastrar_em_config_camadas(conn, dados_config, ativo=bool(config_ativo and status_qualidade == "valido"))

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO importacao.importacao_oficial (
                    inventario_arquivo_id, lote_id, schema_destino, tabela_destino,
                    nome_camada, grupo, tema, subtema, fonte, orgao_produtor,
                    ano_referencia, hash_arquivo, srid, tipo_geometria, numero_feicoes,
                    geometrias_invalidas_antes, geometrias_invalidas_depois,
                    corrigiu_geometrias, metodo_correcao_geometria, status_qualidade,
                    status_importacao, mensagem, avisos, pode_usar_diagnostico,
                    cadastrada_em_config, camada_analise_id, config_ativo, importado_por,
                    atualizado_em
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, now())
                RETURNING id;
                """,
                (
                    int(inventario_arquivo_id),
                    int(inventario["lote_id"]),
                    schema_destino,
                    tabela_destino,
                    dados_config["nome_camada"],
                    dados_config["grupo"],
                    dados_config["tema"],
                    dados_config["subtema"],
                    dados_config["fonte"],
                    dados_config["orgao_produtor"],
                    int(dados_config["ano_referencia"]) if dados_config.get("ano_referencia") else None,
                    inventario.get("hash_arquivo"),
                    SRID_STAGING_PADRAO,
                    dados_config["tipo_geometria"],
                    int(len(gdf)),
                    geometrias_invalidas_antes,
                    geometrias_invalidas_depois,
                    corrigiu,
                    metodo_correcao,
                    status_qualidade,
                    "importado",
                    "Importacao oficial concluida." if status_qualidade == "valido" else "Importacao oficial concluida com pendencias tecnicas.",
                    json.dumps(avisos, ensure_ascii=False),
                    status_qualidade == "valido",
                    cadastrada,
                    camada_analise_id,
                    bool(config_ativo and status_qualidade == "valido"),
                    None,
                ),
            )
            importacao_oficial_id = int(cur.fetchone()[0])
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return {
        "ok": True,
        "importacao_oficial_id": importacao_oficial_id,
        "schema_destino": schema_destino,
        "tabela_destino": tabela_destino,
        "status_qualidade": status_qualidade,
        "pode_usar_diagnostico": status_qualidade == "valido",
        "cadastrada_em_config": cadastrada,
        "camada_analise_id": camada_analise_id,
        "config_ativo": bool(config_ativo and status_qualidade == "valido"),
        "numero_feicoes": int(len(gdf)),
        "geometrias_invalidas_antes": geometrias_invalidas_antes,
        "geometrias_invalidas_depois": geometrias_invalidas_depois,
        "corrigiu_geometrias": corrigiu,
        "metodo_correcao_geometria": metodo_correcao,
        "avisos": avisos,
        "arquivo_original": str(caminho),
    }