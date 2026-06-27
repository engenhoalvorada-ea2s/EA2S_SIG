import argparse
from datetime import datetime
from typing import Any

from psycopg2.extras import Json, RealDictCursor

from db import get_connection


TIPO_EXECUCAO_MVP = "processamento_completo"

VIEWS_RELATORIO = (
    "resultados.vw_relatorio_contexto_projeto",
    "resultados.vw_relatorio_fisico_biotico_area_interesse",
    "resultados.vw_relatorio_fisico_biotico_buffer_1000m",
    "resultados.vw_relatorio_fisico_biotico_microbacias",
    "resultados.vw_relatorio_socio_contexto_setores",
    "resultados.vw_relatorio_socio_total_setores",
    "resultados.vw_relatorio_sintese_executiva",
)

SQL_SEQUENCIA_DRY_RUN = (
    "SELECT 1 FROM projetos.projeto WHERE id = %s;",
    "SELECT 1 FROM projetos.area_interesse WHERE id = %s AND projeto_id = %s;",
    "INSERT INTO resultados.execucao (...) VALUES (...) RETURNING id;",
    "SELECT * FROM resultados.processar_setores_intersectados(%s::bigint, %s::bigint, %s::bigint);",
    "SELECT * FROM resultados.calcular_indicadores_socioeconomicos_mvp(%s::bigint, %s::bigint, %s::bigint);",
    "SELECT * FROM resultados.processar_intersecoes_fisico_bioticas_mvp(%s::bigint, %s::bigint, %s::bigint);",
    "UPDATE resultados.execucao SET status = 'concluida', mensagem = ..., finalizado_em = now() WHERE id = %s;",
)


class MvpExecutionError(RuntimeError):
    """Erro operacional esperado durante a execucao do MVP."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Orquestra a execucao controlada do MVP EA2S SIG."
    )
    parser.add_argument("--projeto-id", type=int, required=True)
    parser.add_argument("--area-interesse-id", type=int, required=True)
    parser.add_argument("--nome-execucao")
    parser.add_argument("--usuario")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida projeto/area e mostra a sequencia prevista sem inserir execucao nem processar funcoes.",
    )
    return parser.parse_args()


def fetch_one_value(cur: RealDictCursor, sql: str, params: tuple[Any, ...]) -> Any:
    cur.execute(sql, params)
    row = cur.fetchone()
    if not row:
        return None
    return next(iter(row.values()))


def validar_projeto_area(cur: RealDictCursor, projeto_id: int, area_interesse_id: int) -> None:
    projeto_existe = fetch_one_value(
        cur,
        "SELECT 1 FROM projetos.projeto WHERE id = %s;",
        (projeto_id,),
    )
    if projeto_existe is None:
        raise MvpExecutionError(f"Projeto nao encontrado: projeto_id={projeto_id}")

    area_existe = fetch_one_value(
        cur,
        """
        SELECT 1
        FROM projetos.area_interesse
        WHERE id = %s
          AND projeto_id = %s;
        """,
        (area_interesse_id, projeto_id),
    )
    if area_existe is None:
        raise MvpExecutionError(
            "Area de interesse nao encontrada para o projeto: "
            f"projeto_id={projeto_id}, area_interesse_id={area_interesse_id}"
        )


def obter_usuario(cur: RealDictCursor, usuario_arg: str | None) -> str:
    if usuario_arg:
        return usuario_arg
    return fetch_one_value(cur, "SELECT current_user;", ())


def criar_execucao(
    cur: RealDictCursor,
    projeto_id: int,
    area_interesse_id: int,
    nome_execucao: str | None,
    usuario: str,
) -> int:
    nome = nome_execucao or (
        f"Execucao MVP - projeto {projeto_id} area {area_interesse_id}"
    )
    parametros = {
        "projeto_id": projeto_id,
        "area_interesse_id": area_interesse_id,
        "criado_por": "src/executar_mvp.py",
        "criado_em": datetime.now().isoformat(timespec="seconds"),
    }

    cur.execute(
        """
        INSERT INTO resultados.execucao (
            projeto_id,
            nome,
            tipo_execucao,
            status,
            parametros,
            mensagem,
            iniciado_em,
            usuario
        )
        VALUES (
            %s,
            %s,
            %s,
            'em_processamento',
            %s,
            'Execucao iniciada pelo orquestrador MVP',
            now(),
            %s
        )
        RETURNING id;
        """,
        (projeto_id, nome, TIPO_EXECUCAO_MVP, Json(parametros), usuario),
    )
    execucao_id = fetch_returning_id(cur)
    if execucao_id is None:
        raise MvpExecutionError("Nao foi possivel criar registro em resultados.execucao.")
    return int(execucao_id)


def fetch_returning_id(cur: RealDictCursor) -> Any:
    row = cur.fetchone()
    if not row:
        return None
    return row.get("id")


def executar_etapa(cur: RealDictCursor, titulo: str, sql: str, params: tuple[Any, ...]) -> dict[str, Any]:
    print(f"- {titulo}...")
    cur.execute(sql, params)
    row = cur.fetchone()
    resultado = dict(row or {})
    print(f"  retorno: {resultado}")
    return resultado


def atualizar_status_execucao(
    cur: RealDictCursor,
    execucao_id: int,
    status: str,
    mensagem: str,
) -> None:
    cur.execute(
        """
        UPDATE resultados.execucao
        SET status = %s,
            mensagem = %s,
            finalizado_em = now()
        WHERE id = %s;
        """,
        (status, mensagem[:1000], execucao_id),
    )


def imprimir_dry_run(projeto_id: int, area_interesse_id: int) -> None:
    print("Dry run habilitado. Nenhuma execucao sera criada e nenhuma funcao sera chamada.")
    print(f"projeto_id: {projeto_id}")
    print(f"area_interesse_id: {area_interesse_id}")
    print("\nSequencia SQL prevista:")
    for sql in SQL_SEQUENCIA_DRY_RUN:
        print(f"- {sql}")


def imprimir_saida_final(execucao_id: int, projeto_id: int, area_interesse_id: int) -> None:
    print("\nExecucao MVP concluida.")
    print(f"execucao_id: {execucao_id}")
    print(f"projeto_id: {projeto_id}")
    print(f"area_interesse_id: {area_interesse_id}")

    print("\nViews finais para consulta:")
    for view_name in VIEWS_RELATORIO:
        print(f"- {view_name}")

    print("\nConsulta principal sugerida:")
    print(
        "SELECT *\n"
        "FROM resultados.vw_relatorio_sintese_executiva\n"
        f"WHERE execucao_id = {execucao_id}\n"
        f"  AND projeto_id = {projeto_id}\n"
        f"  AND area_interesse_id = {area_interesse_id};"
    )


def executar_mvp(args: argparse.Namespace) -> int | None:
    projeto_id = args.projeto_id
    area_interesse_id = args.area_interesse_id
    execucao_id: int | None = None

    with get_connection() as conn:
        conn.autocommit = False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            print("Validando projeto e area de interesse...")
            validar_projeto_area(cur, projeto_id, area_interesse_id)
            conn.commit()

            if args.dry_run:
                imprimir_dry_run(projeto_id, area_interesse_id)
                return None

            usuario = obter_usuario(cur, args.usuario)
            print("Criando registro de execucao...")
            execucao_id = criar_execucao(
                cur,
                projeto_id,
                area_interesse_id,
                args.nome_execucao,
                usuario,
            )
            conn.commit()
            print(f"execucao_id criado: {execucao_id}")

            try:
                executar_etapa(
                    cur,
                    "Processando setores censitarios intersectados",
                    """
                    SELECT *
                    FROM resultados.processar_setores_intersectados(
                        %s::bigint,
                        %s::bigint,
                        %s::bigint
                    );
                    """,
                    (projeto_id, area_interesse_id, execucao_id),
                )
                conn.commit()

                executar_etapa(
                    cur,
                    "Calculando indicadores socioeconomicos",
                    """
                    SELECT *
                    FROM resultados.calcular_indicadores_socioeconomicos_mvp(
                        %s::bigint,
                        %s::bigint,
                        %s::bigint
                    );
                    """,
                    (execucao_id, projeto_id, area_interesse_id),
                )
                conn.commit()

                executar_etapa(
                    cur,
                    "Processando intersecoes fisico-bioticas",
                    """
                    SELECT *
                    FROM resultados.processar_intersecoes_fisico_bioticas_mvp(
                        %s::bigint,
                        %s::bigint,
                        %s::bigint
                    );
                    """,
                    (execucao_id, projeto_id, area_interesse_id),
                )
                conn.commit()

                atualizar_status_execucao(
                    cur,
                    execucao_id,
                    "concluida",
                    "Execucao MVP concluida com sucesso",
                )
                conn.commit()
            except Exception as exc:
                conn.rollback()
                atualizar_status_execucao(cur, execucao_id, "erro", str(exc))
                conn.commit()
                raise

    imprimir_saida_final(execucao_id, projeto_id, area_interesse_id)
    return execucao_id


def main() -> None:
    args = parse_args()
    try:
        executar_mvp(args)
    except MvpExecutionError as exc:
        raise SystemExit(f"Erro de validacao: {exc}") from exc
    except Exception as exc:
        raise SystemExit(f"Erro na execucao do MVP: {exc}") from exc


if __name__ == "__main__":
    main()