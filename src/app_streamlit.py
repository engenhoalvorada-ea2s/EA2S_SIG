"""Interface Streamlit inicial do MVP EA2S SIG.

Esta primeira versao e uma camada de leitura, selecao e montagem de comandos.
Ela nao cria, altera ou apaga dados no banco e nao executa scripts automaticamente.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from db import get_connection


APP_TITLE = "EA2S SIG - Agente de Geoprocessamento"
PAGE_OPTIONS = (
    "Início",
    "Projetos e áreas",
    "Configurar diagnóstico",
    "Executar processamento",
    "Resultados",
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


if __name__ == "__main__":
    main()
