"""Fluxo local de importacao Inventario -> Staging do EA2S SIG.

Este modulo nao promove dados para schemas oficiais. Ele prepara uma copia
operacional em `staging` e registra o controle em `importacao.staging_importacao`.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus
import os
import shutil
import unicodedata
import re

import geopandas as gpd
import pandas as pd
from dotenv import load_dotenv
from psycopg2 import sql


SRID_STAGING_PADRAO = 31982
SCHEMA_STAGING = "staging"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PASTA_ORIGINAIS = PROJECT_ROOT / "data/importacao/originais"


def _normalizar_identificador(valor: str) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9_]+", "_", texto)
    texto = re.sub(r"_+", "_", texto).strip("_")
    if not texto:
        texto = "base"
    if texto[0].isdigit():
        texto = f"t_{texto}"
    return texto[:48].strip("_") or "base"


def gerar_nome_tabela_staging(
    schema_destino_sugerido: str | None,
    tabela_destino_sugerida: str | None,
    inventario_arquivo_id: int,
) -> str:
    """Gera nome seguro e rastreavel para tabela no schema staging."""
    del schema_destino_sugerido  # schema oficial sugerido nunca e usado como destino nesta etapa.
    base = _normalizar_identificador(tabela_destino_sugerida or "base")
    sufixo = f"__inv_{int(inventario_arquivo_id)}"
    limite_base = max(8, 63 - len(sufixo))
    return f"{base[:limite_base].strip('_')}{sufixo}"


def pasta_persistente_inventario(lote_id: int, inventario_arquivo_id: int) -> Path:
    return PASTA_ORIGINAIS / f"lote_{int(lote_id)}" / f"inventario_{int(inventario_arquivo_id)}"


def copiar_arquivo_original_para_persistente(
    caminho_origem: str | Path | None,
    lote_id: int,
    inventario_arquivo_id: int,
    nome_original: str | None = None,
) -> Path | None:
    """Copia arquivo inventariado para pasta persistente local, quando houver origem local."""
    if not caminho_origem:
        return None
    origem = Path(caminho_origem)
    if not origem.exists() or not origem.is_file():
        return None
    destino_dir = pasta_persistente_inventario(lote_id, inventario_arquivo_id)
    destino_dir.mkdir(parents=True, exist_ok=True)
    nome = Path(nome_original or origem.name).name
    destino = destino_dir / nome
    if origem.resolve() != destino.resolve():
        shutil.copy2(origem, destino)
    return destino


def localizar_arquivo_original(inventario: dict[str, Any]) -> Path | None:
    """Localiza arquivo persistido ou caminho temporario ainda disponivel."""
    lote_id = inventario.get("lote_id")
    inv_id = inventario.get("inventario_arquivo_id") or inventario.get("id")
    nomes = [
        inventario.get("nome_original_upload"),
        inventario.get("nome_arquivo"),
    ]
    if lote_id and inv_id:
        pasta = pasta_persistente_inventario(int(lote_id), int(inv_id))
        for nome in nomes:
            if nome:
                candidato = pasta / Path(str(nome)).name
                if candidato.exists():
                    return candidato
        if pasta.exists():
            arquivos = [p for p in pasta.iterdir() if p.is_file()]
            if arquivos:
                return arquivos[0]
    caminho_temporario = inventario.get("caminho_temporario")
    if caminho_temporario and Path(str(caminho_temporario)).exists():
        return Path(str(caminho_temporario))
    return None


def _ler_arquivo_geografico(caminho: Path, layer_name: str | None) -> gpd.GeoDataFrame:
    tentativas: list[tuple[Any, dict[str, Any]]] = []
    if caminho.suffix.lower() == ".zip":
        zip_uri = f"zip://{caminho}"
        if layer_name:
            tentativas.append((zip_uri, {"layer": Path(str(layer_name)).stem}))
            tentativas.append((zip_uri, {"layer": str(layer_name)}))
        tentativas.append((zip_uri, {}))
    if layer_name:
        tentativas.append((caminho, {"layer": Path(str(layer_name)).stem}))
        tentativas.append((caminho, {"layer": str(layer_name)}))
    tentativas.append((caminho, {}))

    ultimo_erro: Exception | None = None
    for alvo, kwargs in tentativas:
        try:
            return gpd.read_file(alvo, **kwargs)
        except Exception as exc:  # pragma: no cover - depende do arquivo real
            ultimo_erro = exc
    raise RuntimeError(f"Nao foi possivel ler o arquivo geográfico: {ultimo_erro}")


def _valor_para_numero(valor: Any) -> float | None:
    """Converte numeros em texto sem transformar ausencias em zero."""
    if pd.isna(valor):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip()
    if not texto:
        return None
    texto = texto.replace("R$", "").replace("%", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def _serie_para_numero(serie: pd.Series) -> pd.Series:
    return serie.map(_valor_para_numero).astype("float64")

def _converter_booleano(serie: pd.Series) -> pd.Series:
    mapa = {
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
    }
    return serie.astype(str).str.strip().str.lower().map(mapa).astype("boolean")


def aplicar_perfil_confirmado(gdf: gpd.GeoDataFrame, perfil_df: pd.DataFrame | None) -> gpd.GeoDataFrame:
    """Aplica conversoes somente na copia que sera importada para staging."""
    if perfil_df is None or perfil_df.empty:
        return gdf.copy()
    data = gdf.copy()
    geom_col = data.geometry.name if data.geometry is not None else None
    for _, perfil in perfil_df.iterrows():
        coluna = perfil.get("nome_campo")
        if coluna not in data.columns or coluna == geom_col:
            continue
        tipo = str(perfil.get("tipo_confirmado") or perfil.get("tipo_sugerido") or "texto").strip()
        if tipo == "ignorar":
            data = data.drop(columns=[coluna])
        elif tipo in {"codigo", "categoria", "texto"}:
            data[coluna] = data[coluna].where(data[coluna].isna(), data[coluna].astype(str))
        elif tipo == "inteiro":
            data[coluna] = _serie_para_numero(data[coluna]).round().astype("Int64")
        elif tipo in {"decimal", "monetario", "percentual"}:
            data[coluna] = _serie_para_numero(data[coluna])
        elif tipo == "data":
            data[coluna] = pd.to_datetime(data[coluna], errors="coerce", dayfirst=True)
        elif tipo == "booleano":
            data[coluna] = _converter_booleano(data[coluna])
    return data


def _criar_engine_sqlalchemy():
    try:
        from sqlalchemy import create_engine
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise RuntimeError("Dependência ausente para to_postgis: sqlalchemy.") from exc

    load_dotenv()
    obrigatorias = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")
    faltantes = [nome for nome in obrigatorias if not os.getenv(nome)]
    if faltantes:
        raise RuntimeError(f"Variáveis ausentes no .env: {', '.join(faltantes)}")
    user = quote_plus(os.environ["DB_USER"])
    password = quote_plus(os.environ["DB_PASSWORD"])
    host = os.environ["DB_HOST"]
    port = os.environ["DB_PORT"]
    database = os.environ["DB_NAME"]
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"
    return create_engine(url)


def _carregar_metadados_inventario(conn: Any, inventario_arquivo_id: int) -> dict[str, Any]:
    query = """
        SELECT *
        FROM importacao.vw_inventario_bases_geograficas
        WHERE inventario_arquivo_id = %s
        LIMIT 1;
    """
    data = pd.read_sql_query(query, conn, params=(int(inventario_arquivo_id),))
    if data.empty:
        raise RuntimeError(f"Inventario {inventario_arquivo_id} nao encontrado na view importacao.vw_inventario_bases_geograficas.")
    return data.iloc[0].to_dict()


def _carregar_perfil(conn: Any, inventario_arquivo_id: int) -> pd.DataFrame:
    try:
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
    except Exception:
        return pd.DataFrame()


def _buscar_importacao_existente(conn: Any, inventario_arquivo_id: int) -> pd.DataFrame:
    try:
        return pd.read_sql_query(
            """
            SELECT *
            FROM importacao.staging_importacao
            WHERE inventario_arquivo_id = %s
            ORDER BY criado_em DESC;
            """,
            conn,
            params=(int(inventario_arquivo_id),),
        )
    except Exception:
        return pd.DataFrame()


def importar_inventario_para_staging(
    inventario_arquivo_id: int,
    conn: Any,
    reimportar: bool = False,
) -> dict[str, Any]:
    """Importa inventario para schema staging e registra controle operacional."""
    try:
        import geoalchemy2  # noqa: F401
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise RuntimeError("Dependência ausente para to_postgis: geoalchemy2.") from exc

    inventario = _carregar_metadados_inventario(conn, inventario_arquivo_id)
    existentes = _buscar_importacao_existente(conn, inventario_arquivo_id)
    if not existentes.empty and not reimportar:
        return {
            "ok": False,
            "ja_importado": True,
            "mensagem": "Este inventário já foi importado para staging.",
            "importacoes_existentes": existentes.to_dict(orient="records"),
        }

    caminho = localizar_arquivo_original(inventario)
    if caminho is None:
        raise RuntimeError(
            "Arquivo original persistente nao encontrado. Copie o arquivo para "
            f"{pasta_persistente_inventario(int(inventario['lote_id']), int(inventario_arquivo_id))}."
        )

    gdf = _ler_arquivo_geografico(caminho, inventario.get("layer_name"))
    if gdf.empty:
        raise RuntimeError("Arquivo lido sem feicoes para importar.")
    if gdf.geometry.name != "geom":
        gdf = gdf.rename_geometry("geom")
    srid_origem = inventario.get("srid_detectado") or (gdf.crs.to_epsg() if gdf.crs else None)
    if srid_origem and gdf.crs is None:
        gdf = gdf.set_crs(int(srid_origem), allow_override=True)
    invalidas_origem = int((~gdf.geometry.is_valid).sum()) if gdf.geometry is not None else 0
    if gdf.crs is not None and gdf.crs.to_epsg() != SRID_STAGING_PADRAO:
        gdf = gdf.to_crs(epsg=SRID_STAGING_PADRAO)
    elif gdf.crs is None:
        gdf = gdf.set_crs(epsg=SRID_STAGING_PADRAO, allow_override=True)

    perfil = _carregar_perfil(conn, inventario_arquivo_id)
    gdf = aplicar_perfil_confirmado(gdf, perfil)
    gdf["_ea2s_inventario_arquivo_id"] = int(inventario_arquivo_id)
    gdf["_ea2s_lote_id"] = int(inventario["lote_id"])
    gdf["_ea2s_hash_arquivo"] = inventario.get("hash_arquivo")
    gdf["_ea2s_importado_em"] = datetime.now()
    status_validacao = "geometria_invalida" if invalidas_origem else "valido"
    gdf["_ea2s_status_validacao"] = status_validacao

    tabela = gerar_nome_tabela_staging(
        inventario.get("schema_destino_sugerido"),
        inventario.get("tabela_destino_sugerida"),
        inventario_arquivo_id,
    )
    if reimportar:
        tabela = f"{tabela}__r{datetime.now().strftime('%Y%m%d%H%M%S')}"

    engine = _criar_engine_sqlalchemy()
    gdf.to_postgis(tabela, engine, schema=SCHEMA_STAGING, if_exists="fail", index=False)
    invalidas_staging = int((~gdf.geometry.is_valid).sum()) if gdf.geometry is not None else 0

    status_importacao = "importado"
    mensagem = "Importacao para staging concluida."
    if invalidas_staging:
        mensagem = "A camada foi importada para staging com geometrias invalidas. Corrija antes de promover para schema oficial."

    with conn.cursor() as cur:
        cur.execute(
            sql.SQL(
                """
                INSERT INTO importacao.staging_importacao (
                    inventario_arquivo_id, lote_id, schema_staging, tabela_staging,
                    nome_original, layer_name, hash_arquivo, srid_origem, srid_destino,
                    tipo_geometria, numero_feicoes_origem, numero_feicoes_staging,
                    geometrias_invalidas_origem, geometrias_invalidas_staging,
                    status_importacao, status_validacao, mensagem, atualizado_em
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                RETURNING id;
                """
            ),
            (
                int(inventario_arquivo_id),
                int(inventario["lote_id"]),
                SCHEMA_STAGING,
                tabela,
                inventario.get("nome_original_upload") or inventario.get("nome_arquivo"),
                inventario.get("layer_name"),
                inventario.get("hash_arquivo"),
                int(srid_origem) if srid_origem else None,
                SRID_STAGING_PADRAO,
                inventario.get("tipo_geometria"),
                int(inventario.get("numero_feicoes") or len(gdf)),
                int(len(gdf)),
                invalidas_origem,
                invalidas_staging,
                status_importacao,
                status_validacao,
                mensagem,
            ),
        )
        staging_importacao_id = int(cur.fetchone()[0])
    conn.commit()
    return {
        "ok": True,
        "staging_importacao_id": staging_importacao_id,
        "schema_staging": SCHEMA_STAGING,
        "tabela_staging": tabela,
        "numero_feicoes_staging": int(len(gdf)),
        "geometrias_invalidas_origem": invalidas_origem,
        "geometrias_invalidas_staging": invalidas_staging,
        "status_validacao": status_validacao,
        "mensagem": mensagem,
        "caminho_original": str(caminho),
    }
