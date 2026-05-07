from __future__ import annotations

import traceback

import pandas as pd
import streamlit as st

from . import APP_REBUILD_VERSION
from .engines import get_site_engine
from .model_contract import ModelContract, read_uploaded_model
from .operations import OperationType, get_profile
from .sanitizer import sanitize_final_df, to_bling_csv_bytes


def _init_state() -> None:
    defaults = {
        "rebuild_contract": None,
        "rebuild_result_df": None,
        "rebuild_model_preview": None,
        "rebuild_logs": [],
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _log(message: str) -> None:
    logs = st.session_state.setdefault("rebuild_logs", [])
    logs.append(message)
    if len(logs) > 200:
        del logs[:-200]


def _parse_urls(raw: str) -> list[str]:
    urls: list[str] = []
    for line in raw.replace(",", "\n").splitlines():
        url = line.strip()
        if not url:
            continue
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        urls.append(url)
    return list(dict.fromkeys(urls))


def _render_header() -> None:
    st.title("IA Planilhas Bling")
    st.caption(f"Rebuild limpo {APP_REBUILD_VERSION} · planilha modelo como contrato · motores separados por operação")
    st.info(
        "Fluxo novo: anexe a planilha modelo do Bling, escolha/valide a operação e o sistema captura somente as colunas que o modelo solicita. "
        "Se não encontrar um campo no site, o valor fica vazio."
    )


def _render_model_step() -> ModelContract | None:
    st.subheader("1. Modelo Bling e operação")
    selected = st.radio(
        "Qual operação você quer executar?",
        options=("Detectar pela planilha", "Cadastro de produtos", "Atualização de estoque"),
        horizontal=True,
    )
    selected_operation = None
    if selected == "Cadastro de produtos":
        selected_operation = OperationType.CADASTRO.value
    elif selected == "Atualização de estoque":
        selected_operation = OperationType.ESTOQUE.value

    uploaded = st.file_uploader(
        "Anexe a planilha modelo do Bling",
        type=("xlsx", "xls", "csv", "xlsm", "xlsb"),
        help="As colunas desta planilha serão o contrato exato do resultado final.",
    )

    if uploaded is None:
        st.warning("Anexe o modelo do Bling para o sistema saber exatamente quais colunas precisa preencher.")
        return st.session_state.get("rebuild_contract")

    try:
        contract, preview = read_uploaded_model(uploaded, selected_operation=selected_operation)
        st.session_state["rebuild_contract"] = contract
        st.session_state["rebuild_model_preview"] = preview
        profile = get_profile(contract.operation)
        st.success(f"Operação reconhecida: {profile.title}")
        st.caption(profile.description)
        with st.expander("Colunas solicitadas pela planilha modelo", expanded=True):
            st.write(list(contract.columns))
            st.dataframe(preview.head(20), use_container_width=True)
        _log(f"Modelo carregado: {contract.source_filename} / operação={contract.operation.value} / colunas={len(contract.columns)}")
        return contract
    except Exception as exc:
        st.error(f"Não consegui ler a planilha modelo: {exc}")
        st.code(traceback.format_exc())
        return None


def _render_site_step(contract: ModelContract) -> pd.DataFrame | None:
    st.subheader("2. Captura por site")
    profile = get_profile(contract.operation)
    st.write(f"Motor ativo: **{profile.title}**")

    if contract.operation == OperationType.ESTOQUE:
        deposit_name = st.text_input("Nome do depósito", value="", placeholder="Ex.: Geral")
    else:
        deposit_name = ""

    raw_urls = st.text_area(
        "Links dos produtos",
        height=180,
        placeholder="Cole um link por linha. O sistema não busca campos extras; usa apenas o que o modelo pediu.",
    )
    urls = _parse_urls(raw_urls)
    st.caption(f"{len(urls)} link(s) detectado(s).")

    col_a, col_b = st.columns([1, 1])
    with col_a:
        run = st.button("Capturar produtos", type="primary", use_container_width=True, disabled=not urls)
    with col_b:
        clear = st.button("Limpar resultado", use_container_width=True)

    if clear:
        st.session_state["rebuild_result_df"] = None
        st.rerun()

    if run:
        progress_bar = st.progress(0)
        status = st.empty()

        def progress(index: int, total: int, url: str) -> None:
            progress_bar.progress(index / max(total, 1))
            status.info(f"Capturando {index}/{total}: {url}")

        engine = get_site_engine(contract.operation)
        try:
            if contract.operation == OperationType.ESTOQUE:
                df = engine.run(urls, contract, deposit_name=deposit_name, progress=progress)
            else:
                df = engine.run(urls, contract, progress=progress)
            df = sanitize_final_df(df)
            st.session_state["rebuild_result_df"] = df
            status.success("Captura concluída.")
            _log(f"Captura concluída: operação={contract.operation.value} / linhas={len(df)}")
        except Exception as exc:
            status.error(f"Erro na captura: {exc}")
            st.code(traceback.format_exc())

    return st.session_state.get("rebuild_result_df")


def _render_preview_download(df: pd.DataFrame | None) -> None:
    st.subheader("3. Preview final e download")
    if df is None or df.empty:
        st.warning("O preview final aparecerá depois da captura.")
        return

    clean = sanitize_final_df(df)
    st.dataframe(clean, use_container_width=True)
    st.download_button(
        "Baixar CSV para Bling",
        data=to_bling_csv_bytes(clean),
        file_name="bling_resultado_final.csv",
        mime="text/csv",
        type="primary",
        use_container_width=True,
    )


def _render_debug() -> None:
    with st.expander("Log técnico", expanded=False):
        logs = st.session_state.get("rebuild_logs", [])
        if not logs:
            st.caption("Nenhum log ainda.")
        else:
            st.code("\n".join(logs[-80:]))


def run_rebuild_app() -> None:
    _init_state()
    _render_header()
    contract = _render_model_step()
    if contract is not None:
        df = _render_site_step(contract)
        _render_preview_download(df)
    _render_debug()
