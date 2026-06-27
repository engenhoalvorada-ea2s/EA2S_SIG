import argparse
from pathlib import Path
from typing import NamedTuple

import pandas as pd

from db import get_connection


class Exportacao(NamedTuple):
    nome_arquivo: str
    view_name: str
    order_by: str | None = None


EXPORTACOES = (
    Exportacao(
        "01_sintese_executiva.xlsx",
        "resultados.vw_relatorio_sintese_executiva",
    ),
    Exportacao(
        "02_fisico_biotico_area_interesse.xlsx",
        "resultados.vw_relatorio_fisico_biotico_area_interesse",
        "tema, area_ha DESC NULLS LAST",
    ),
    Exportacao(
        "03_fisico_biotico_buffer_1000m.xlsx",
        "resultados.vw_relatorio_fisico_biotico_buffer_1000m",
        "tema, area_ha DESC NULLS LAST",
    ),
    Exportacao(
        "04_fisico_biotico_microbacias.xlsx",
        "resultados.vw_relatorio_fisico_biotico_microbacias",
        "nm_micro, tema, area_ha DESC NULLS LAST",
    ),
    Exportacao(
        "05_microbacias_identificacao.xlsx",
        "resultados.vw_relatorio_microbacias_identificacao",
        "nm_micro",
    ),
    Exportacao(
        "06_socio_contexto_setores.xlsx",
        "resultados.vw_relatorio_socio_contexto_setores",
        "percentual_area_interesse DESC NULLS LAST, cd_setor",
    ),
    Exportacao(
        "07_socio_total_setores.xlsx",
        "resultados.vw_relatorio_socio_total_setores",
    ),
)


class ExportacaoMvpError(RuntimeError):
    """Erro esperado de validacao da exportacao do MVP."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Exporta views finais do MVP EA2S SIG para arquivos Excel."
    )
    parser.add_argument("--execucao-id", type=int, required=True)
    parser.add_argument("--projeto-id", type=int, required=True)
    parser.add_argument("--area-interesse-id", type=int, required=True)
    parser.add_argument(
        "--projeto-sig-dir",
        required=True,
        help="Pasta SIG existente do projeto que recebera resultados_mvp/execucao_<id>.",
    )
    parser.add_argument(
        "--output-dir",
        help=(
            "Opcao avancada/de compatibilidade. Quando --projeto-sig-dir e informado, "
            "a saida padrao continua sendo resultados_mvp/execucao_<id> dentro da pasta SIG."
        ),
    )
    return parser.parse_args()


def resolver_pasta_saida(args: argparse.Namespace) -> Path:
    projeto_sig_dir = Path(args.projeto_sig_dir).expanduser().resolve()
    if not projeto_sig_dir.exists():
        raise ExportacaoMvpError(
            "Pasta SIG do projeto nao encontrada. Confira --projeto-sig-dir: "
            f"{projeto_sig_dir}"
        )
    if not projeto_sig_dir.is_dir():
        raise ExportacaoMvpError(
            "O caminho informado em --projeto-sig-dir nao e uma pasta: "
            f"{projeto_sig_dir}"
        )

    if args.output_dir:
        print(
            "Aviso: --output-dir foi informado, mas --projeto-sig-dir tem prioridade "
            "na arquitetura atual de exportacao."
        )

    pasta_saida = projeto_sig_dir / "resultados_mvp" / f"execucao_{args.execucao_id}"
    pasta_saida.mkdir(parents=True, exist_ok=True)
    return pasta_saida


def montar_sql(exportacao: Exportacao) -> str:
    sql = f"""
        SELECT *
        FROM {exportacao.view_name}
        WHERE execucao_id = %s
          AND projeto_id = %s
          AND area_interesse_id = %s
    """
    if exportacao.order_by:
        sql += f"\n        ORDER BY {exportacao.order_by}"
    return sql


def exportar_view(
    conn,
    exportacao: Exportacao,
    pasta_saida: Path,
    execucao_id: int,
    projeto_id: int,
    area_interesse_id: int,
) -> Path:
    sql = montar_sql(exportacao)
    df = pd.read_sql_query(
        sql,
        conn,
        params=(execucao_id, projeto_id, area_interesse_id),
    )

    caminho_arquivo = pasta_saida / exportacao.nome_arquivo
    df.to_excel(caminho_arquivo, index=False)
    return caminho_arquivo


def exportar_resultados(args: argparse.Namespace) -> list[Path]:
    pasta_saida = resolver_pasta_saida(args)
    arquivos_gerados: list[Path] = []

    with get_connection() as conn:
        conn.autocommit = True
        for exportacao in EXPORTACOES:
            print(f"Exportando {exportacao.view_name}...")
            caminho_arquivo = exportar_view(
                conn,
                exportacao,
                pasta_saida,
                args.execucao_id,
                args.projeto_id,
                args.area_interesse_id,
            )
            arquivos_gerados.append(caminho_arquivo)

    return arquivos_gerados


def imprimir_resultado(pasta_saida: Path, arquivos_gerados: list[Path]) -> None:
    print("\nResultados exportados em:")
    print(str(pasta_saida))
    print("\nArquivos gerados:")
    for caminho in arquivos_gerados:
        print(f"- {caminho}")


def main() -> None:
    args = parse_args()
    try:
        pasta_saida = resolver_pasta_saida(args)
        arquivos_gerados: list[Path] = []
        with get_connection() as conn:
            conn.autocommit = True
            for exportacao in EXPORTACOES:
                print(f"Exportando {exportacao.view_name}...")
                caminho_arquivo = exportar_view(
                    conn,
                    exportacao,
                    pasta_saida,
                    args.execucao_id,
                    args.projeto_id,
                    args.area_interesse_id,
                )
                arquivos_gerados.append(caminho_arquivo)
        imprimir_resultado(pasta_saida, arquivos_gerados)
    except ExportacaoMvpError as exc:
        raise SystemExit(f"Erro de validacao: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"Erro ao exportar resultados do MVP: {exc}") from exc


if __name__ == "__main__":
    main()