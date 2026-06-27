import argparse
import re
import textwrap
import unicodedata
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from db import get_connection


TEMAS_FISICO_BIOTICOS = (
    "geologia",
    "geomorfologia",
    "hidrogeologia",
    "pedologia",
    "vegetacao",
)

TITULOS_TEMAS = {
    "geologia": "Geologia",
    "geomorfologia": "Geomorfologia",
    "hidrogeologia": "Hidrogeologia",
    "pedologia": "Pedologia",
    "vegetacao": "Vegetacao",
}


class GraficosMvpError(RuntimeError):
    """Erro esperado de validacao da geracao de graficos."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera graficos PNG do MVP EA2S SIG a partir das views integradas."
    )
    parser.add_argument("--execucao-id", type=int, required=True)
    parser.add_argument("--projeto-id", type=int, required=True)
    parser.add_argument("--area-interesse-id", type=int, required=True)
    parser.add_argument(
        "--projeto-sig-dir",
        required=True,
        help="Pasta SIG existente do projeto que recebera resultados_mvp/execucao_<id>/graficos.",
    )
    return parser.parse_args()


def resolver_pasta_graficos(args: argparse.Namespace) -> Path:
    projeto_sig_dir = Path(args.projeto_sig_dir).expanduser().resolve()
    if not projeto_sig_dir.exists():
        raise GraficosMvpError(
            "Pasta SIG do projeto nao encontrada. Confira --projeto-sig-dir: "
            f"{projeto_sig_dir}"
        )
    if not projeto_sig_dir.is_dir():
        raise GraficosMvpError(
            "O caminho informado em --projeto-sig-dir nao e uma pasta: "
            f"{projeto_sig_dir}"
        )

    pasta_graficos = (
        projeto_sig_dir
        / "resultados_mvp"
        / f"execucao_{args.execucao_id}"
        / "graficos"
    )
    for subdir in (
        pasta_graficos / "fisico_biotico" / "area_interesse",
        pasta_graficos / "fisico_biotico" / "buffer_1000m",
        pasta_graficos / "fisico_biotico" / "microbacias",
        pasta_graficos / "socioeconomico" / "setores_censitarios",
        pasta_graficos / "sintese",
    ):
        subdir.mkdir(parents=True, exist_ok=True)
    return pasta_graficos


def limpar_nome_arquivo(valor: object) -> str:
    texto = str(valor or "sem_nome").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-z0-9]+", "_", texto)
    texto = texto.strip("_")
    return texto or "sem_nome"


def quebrar_rotulo(valor: object, largura: int = 42) -> str:
    texto = str(valor if valor not in (None, "") else "Sem classificacao informada")
    return "\n".join(textwrap.wrap(texto, width=largura)) or texto


def consultar_dataframe(conn, sql: str, params: tuple[object, ...]) -> pd.DataFrame:
    return pd.read_sql_query(sql, conn, params=params)


def avisar_sem_dados(nome: str, motivo: str) -> None:
    print(f"Aviso: grafico nao gerado ({nome}). {motivo}")


def salvar_figura(caminho: Path) -> Path:
    plt.tight_layout()
    plt.savefig(caminho, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Grafico gerado: {caminho}")
    return caminho


def grafico_barras_horizontais(
    df: pd.DataFrame,
    categoria: str,
    valor: str,
    titulo: str,
    xlabel: str,
    caminho: Path,
) -> Path | None:
    if df.empty:
        avisar_sem_dados(caminho.name, "A consulta retornou zero linhas.")
        return None

    dados = df[[categoria, valor]].copy()
    dados[valor] = pd.to_numeric(dados[valor], errors="coerce")
    nulos = int(dados[valor].isna().sum())
    dados = dados.dropna(subset=[valor])
    if dados.empty:
        avisar_sem_dados(caminho.name, "Todos os valores numericos estao nulos.")
        return None
    if nulos:
        print(
            f"Aviso: {caminho.name} omitiu {nulos} registro(s) com valor nulo."
        )

    dados[categoria] = dados[categoria].fillna("Sem classificacao informada")
    dados = dados.sort_values(valor, ascending=True)
    labels = [quebrar_rotulo(v) for v in dados[categoria]]
    valores = dados[valor].to_numpy()

    altura = max(4.0, 0.45 * len(dados) + 1.8)
    plt.figure(figsize=(10, altura))
    plt.barh(labels, valores, color="#4C78A8")
    plt.title(titulo)
    plt.xlabel(xlabel)
    plt.grid(axis="x", alpha=0.25)
    return salvar_figura(caminho)


def grafico_barras_agrupadas_horizontais(
    df: pd.DataFrame,
    categoria: str,
    series: list[tuple[str, str]],
    titulo: str,
    xlabel: str,
    caminho: Path,
) -> Path | None:
    if df.empty:
        avisar_sem_dados(caminho.name, "A consulta retornou zero linhas.")
        return None

    colunas = [col for col, _ in series]
    dados = df[[categoria, *colunas]].copy()
    for col in colunas:
        dados[col] = pd.to_numeric(dados[col], errors="coerce")
    dados = dados.dropna(subset=colunas, how="all")
    if dados.empty:
        avisar_sem_dados(caminho.name, "Todos os valores numericos estao nulos.")
        return None

    total_nulos = int(dados[colunas].isna().sum().sum())
    if total_nulos:
        print(
            f"Aviso: {caminho.name} possui {total_nulos} valor(es) nulo(s); "
            "foram desenhados como zero apenas para visualizacao."
        )
    dados[colunas] = dados[colunas].fillna(0)
    dados[categoria] = dados[categoria].fillna("Sem identificacao")
    dados = dados.iloc[::-1]

    labels = [quebrar_rotulo(v, largura=28) for v in dados[categoria]]
    y = np.arange(len(dados))
    largura_barra = 0.8 / max(1, len(series))
    offsets = np.linspace(-0.4 + largura_barra / 2, 0.4 - largura_barra / 2, len(series))

    altura = max(4.5, 0.55 * len(dados) + 2.0)
    plt.figure(figsize=(11, altura))
    for offset, (col, label) in zip(offsets, series):
        plt.barh(y + offset, dados[col].to_numpy(), height=largura_barra, label=label)
    plt.yticks(y, labels)
    plt.title(titulo)
    plt.xlabel(xlabel)
    plt.grid(axis="x", alpha=0.25)
    plt.legend(loc="best")
    return salvar_figura(caminho)


def grafico_barras_verticais(
    df: pd.DataFrame,
    categoria: str,
    valor: str,
    titulo: str,
    ylabel: str,
    caminho: Path,
) -> Path | None:
    if df.empty:
        avisar_sem_dados(caminho.name, "A consulta retornou zero linhas.")
        return None

    dados = df[[categoria, valor]].copy()
    dados[valor] = pd.to_numeric(dados[valor], errors="coerce")
    dados = dados.dropna(subset=[valor])
    if dados.empty:
        avisar_sem_dados(caminho.name, "Todos os valores numericos estao nulos.")
        return None

    labels = [quebrar_rotulo(v, largura=20) for v in dados[categoria]]
    plt.figure(figsize=(max(7, len(dados) * 1.1), 5))
    plt.bar(labels, dados[valor].to_numpy(), color="#72B7B2")
    plt.title(titulo)
    plt.ylabel(ylabel)
    plt.xticks(rotation=20, ha="right")
    plt.grid(axis="y", alpha=0.25)
    return salvar_figura(caminho)


def grafico_sintese(df: pd.DataFrame, caminho: Path) -> Path | None:
    if df.empty:
        avisar_sem_dados(caminho.name, "A consulta retornou zero linhas.")
        return None

    linha = df.iloc[0]
    dados = pd.DataFrame(
        {
            "indicador": [
                "Setores interceptados",
                "Populacao total",
                "Total de domicilios",
                "Domicilios particulares permanentes ocupados",
                "Setores com dados completos",
                "Setores com dados parciais",
                "Microbacias interceptadas",
            ],
            "valor": [
                linha.get("numero_setores_intersectados"),
                linha.get("populacao_total_setores"),
                linha.get("total_domicilios_setores"),
                linha.get("domicilios_particulares_permanentes_ocupados_setores"),
                linha.get("setores_com_dados_completos"),
                linha.get("setores_com_dados_parciais"),
                linha.get("numero_microbacias_interceptadas"),
            ],
        }
    )
    return grafico_barras_verticais(
        dados,
        "indicador",
        "valor",
        "Sintese executiva - indicadores principais",
        "Valor",
        caminho,
    )


def gerar_fisico_biotico_unidade(
    conn,
    pasta: Path,
    view_name: str,
    sufixo_arquivo: str,
    titulo_unidade: str,
    xlabel: str,
    params_base: tuple[int, int, int],
) -> list[Path]:
    gerados: list[Path] = []
    sql = f"""
        SELECT
            tema,
            valor_principal,
            area_ha,
            percentual_unidade_analise
        FROM {view_name}
        WHERE execucao_id = %s
          AND projeto_id = %s
          AND area_interesse_id = %s
          AND tema = %s
        ORDER BY area_ha DESC;
    """
    for tema in TEMAS_FISICO_BIOTICOS:
        df = consultar_dataframe(conn, sql, (*params_base, tema))
        caminho = pasta / f"{tema}_{sufixo_arquivo}.png"
        gerado = grafico_barras_horizontais(
            df,
            "valor_principal",
            "percentual_unidade_analise",
            f"{TITULOS_TEMAS[tema]} - {titulo_unidade}",
            xlabel,
            caminho,
        )
        if gerado:
            gerados.append(gerado)
    return gerados


def gerar_fisico_biotico_microbacias(conn, pasta: Path, params_base: tuple[int, int, int]) -> list[Path]:
    gerados: list[Path] = []
    sql_microbacias = """
        SELECT DISTINCT
            cd_micro,
            nm_micro
        FROM resultados.vw_relatorio_fisico_biotico_microbacias
        WHERE execucao_id = %s
          AND projeto_id = %s
          AND area_interesse_id = %s
        ORDER BY nm_micro;
    """
    microbacias = consultar_dataframe(conn, sql_microbacias, params_base)
    if microbacias.empty:
        print("Aviso: nenhuma microbacia encontrada para gerar graficos.")
        return gerados

    sql = """
        SELECT
            cd_micro,
            nm_micro,
            tema,
            valor_principal,
            area_ha,
            percentual_unidade_analise
        FROM resultados.vw_relatorio_fisico_biotico_microbacias
        WHERE execucao_id = %s
          AND projeto_id = %s
          AND area_interesse_id = %s
          AND cd_micro = %s
          AND tema = %s
        ORDER BY area_ha DESC;
    """
    for _, microbacia in microbacias.iterrows():
        cd_micro = microbacia["cd_micro"]
        nm_micro = microbacia["nm_micro"]
        nome_limpo = limpar_nome_arquivo(nm_micro)
        for tema in TEMAS_FISICO_BIOTICOS:
            df = consultar_dataframe(conn, sql, (*params_base, cd_micro, tema))
            caminho = pasta / f"microbacia_{nome_limpo}_{tema}.png"
            gerado = grafico_barras_horizontais(
                df,
                "valor_principal",
                "percentual_unidade_analise",
                f"{TITULOS_TEMAS[tema]} - Microbacia {nm_micro}",
                "% da microbacia",
                caminho,
            )
            if gerado:
                gerados.append(gerado)
    return gerados


def gerar_socioeconomicos(conn, pasta: Path, params_base: tuple[int, int, int]) -> list[Path]:
    gerados: list[Path] = []

    sql_populacao = """
        SELECT cd_setor, populacao_total_setor
        FROM resultados.vw_relatorio_socio_contexto_setores
        WHERE execucao_id = %s
          AND projeto_id = %s
          AND area_interesse_id = %s
        ORDER BY populacao_total_setor DESC NULLS LAST;
    """
    gerado = grafico_barras_horizontais(
        consultar_dataframe(conn, sql_populacao, params_base),
        "cd_setor",
        "populacao_total_setor",
        "Populacao por setor censitario interceptado",
        "Populacao total do setor",
        pasta / "populacao_por_setor.png",
    )
    if gerado:
        gerados.append(gerado)

    sql_domicilios = """
        SELECT
            cd_setor,
            total_domicilios_setor,
            domicilios_particulares_permanentes_ocupados_setor
        FROM resultados.vw_relatorio_socio_contexto_setores
        WHERE execucao_id = %s
          AND projeto_id = %s
          AND area_interesse_id = %s
        ORDER BY total_domicilios_setor DESC NULLS LAST;
    """
    gerado = grafico_barras_agrupadas_horizontais(
        consultar_dataframe(conn, sql_domicilios, params_base),
        "cd_setor",
        [
            ("total_domicilios_setor", "Total de domicilios"),
            (
                "domicilios_particulares_permanentes_ocupados_setor",
                "Domicilios particulares permanentes ocupados",
            ),
        ],
        "Domicilios por setor censitario interceptado",
        "Domicilios",
        pasta / "domicilios_por_setor.png",
    )
    if gerado:
        gerados.append(gerado)

    sql_renda = """
        SELECT
            cd_setor,
            renda_media_responsavel_setor,
            renda_mediana_responsavel_setor,
            status_dados_setor
        FROM resultados.vw_relatorio_socio_contexto_setores
        WHERE execucao_id = %s
          AND projeto_id = %s
          AND area_interesse_id = %s
        ORDER BY renda_media_responsavel_setor DESC NULLS LAST;
    """
    gerado = grafico_barras_horizontais(
        consultar_dataframe(conn, sql_renda, params_base),
        "cd_setor",
        "renda_media_responsavel_setor",
        "Renda media dos responsaveis por setor",
        "R$",
        pasta / "renda_media_por_setor.png",
    )
    if gerado:
        gerados.append(gerado)

    sql_saneamento = """
        SELECT
            cd_setor,
            agua_rede_geral_setor,
            lixo_coletado_domicilio_setor,
            esgoto_fossa_septica_nao_ligada_rede_setor,
            status_dados_setor
        FROM resultados.vw_relatorio_socio_contexto_setores
        WHERE execucao_id = %s
          AND projeto_id = %s
          AND area_interesse_id = %s
        ORDER BY cd_setor;
    """
    gerado = grafico_barras_agrupadas_horizontais(
        consultar_dataframe(conn, sql_saneamento, params_base),
        "cd_setor",
        [
            ("agua_rede_geral_setor", "Agua por rede geral"),
            ("lixo_coletado_domicilio_setor", "Lixo coletado no domicilio"),
            (
                "esgoto_fossa_septica_nao_ligada_rede_setor",
                "Esgoto por fossa septica nao ligada a rede",
            ),
        ],
        "Indicadores de saneamento por setor censitario",
        "Domicilios",
        pasta / "saneamento_por_setor.png",
    )
    if gerado:
        gerados.append(gerado)

    sql_participacao = """
        SELECT cd_setor, percentual_area_interesse, area_intersecao_ha
        FROM resultados.vw_relatorio_socio_contexto_setores
        WHERE execucao_id = %s
          AND projeto_id = %s
          AND area_interesse_id = %s
        ORDER BY percentual_area_interesse DESC;
    """
    gerado = grafico_barras_horizontais(
        consultar_dataframe(conn, sql_participacao, params_base),
        "cd_setor",
        "percentual_area_interesse",
        "Participacao dos setores censitarios na area de interesse",
        "% da area de interesse",
        pasta / "participacao_setores_area_interesse.png",
    )
    if gerado:
        gerados.append(gerado)

    sql_status = """
        SELECT
            status_dados_setor,
            count(*) AS total_setores
        FROM resultados.vw_relatorio_socio_contexto_setores
        WHERE execucao_id = %s
          AND projeto_id = %s
          AND area_interesse_id = %s
        GROUP BY status_dados_setor
        ORDER BY status_dados_setor;
    """
    gerado = grafico_barras_verticais(
        consultar_dataframe(conn, sql_status, params_base),
        "status_dados_setor",
        "total_setores",
        "Status dos dados socioeconomicos por setor",
        "Numero de setores",
        pasta / "status_dados_setores.png",
    )
    if gerado:
        gerados.append(gerado)

    return gerados


def gerar_sintese(conn, pasta: Path, params_base: tuple[int, int, int]) -> list[Path]:
    sql = """
        SELECT
            numero_setores_intersectados,
            populacao_total_setores,
            total_domicilios_setores,
            domicilios_particulares_permanentes_ocupados_setores,
            setores_com_dados_completos,
            setores_com_dados_parciais,
            numero_microbacias_interceptadas
        FROM resultados.vw_relatorio_sintese_executiva
        WHERE execucao_id = %s
          AND projeto_id = %s
          AND area_interesse_id = %s;
    """
    gerado = grafico_sintese(
        consultar_dataframe(conn, sql, params_base),
        pasta / "sintese_executiva_indicadores.png",
    )
    return [gerado] if gerado else []


def gerar_graficos(args: argparse.Namespace) -> list[Path]:
    pasta_graficos = resolver_pasta_graficos(args)
    params_base = (args.execucao_id, args.projeto_id, args.area_interesse_id)
    gerados: list[Path] = []

    with get_connection() as conn:
        conn.autocommit = True
        gerados.extend(
            gerar_fisico_biotico_unidade(
                conn,
                pasta_graficos / "fisico_biotico" / "area_interesse",
                "resultados.vw_relatorio_fisico_biotico_area_interesse",
                "area_interesse",
                "Area de Interesse",
                "% da area de interesse",
                params_base,
            )
        )
        gerados.extend(
            gerar_fisico_biotico_unidade(
                conn,
                pasta_graficos / "fisico_biotico" / "buffer_1000m",
                "resultados.vw_relatorio_fisico_biotico_buffer_1000m",
                "buffer_1000m",
                "Buffer de 1000 m",
                "% do buffer de 1000 m",
                params_base,
            )
        )
        gerados.extend(
            gerar_fisico_biotico_microbacias(
                conn,
                pasta_graficos / "fisico_biotico" / "microbacias",
                params_base,
            )
        )
        gerados.extend(
            gerar_socioeconomicos(
                conn,
                pasta_graficos / "socioeconomico" / "setores_censitarios",
                params_base,
            )
        )
        gerados.extend(gerar_sintese(conn, pasta_graficos / "sintese", params_base))

    print("\nPasta de graficos:")
    print(pasta_graficos)
    print(f"Total de graficos gerados: {len(gerados)}")
    return gerados


def main() -> None:
    args = parse_args()
    try:
        gerar_graficos(args)
    except GraficosMvpError as exc:
        raise SystemExit(f"Erro de validacao: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"Erro ao gerar graficos do MVP: {exc}") from exc


if __name__ == "__main__":
    main()