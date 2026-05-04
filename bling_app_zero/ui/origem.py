from __future__ import annotations

import traceback

import streamlit as st

from bling_app_zero.core.file_reader import read_uploaded_table
from bling_app_zero.ui.debug_panel import add_debug_log, render_debug_panel


def _registrar_erro_origem(exc: Exception) -> None:
    add_debug_log("Erro ao ler origem", str(exc))
    st.error("Não foi possível ler a origem.")
    st.warning("Detalhe técnico do erro real:")
    st.code(str(exc))
    with st.expander("Ver traceback completo", expanded=False):
        st.code(traceback.format_exc())


def render_origem_dados() -> None:
    render_debug_panel()

    st.title("1. Origem dos dados")

    st.subheader("Upload de planilha")
    uploaded = st.file_uploader(
        "Envie seu arquivo CSV ou Excel",
        type=["csv", "xlsx", "xlsm", "xls"],
    )

    if uploaded is not None:
        try:
            add_debug_log("Arquivo recebido", getattr(uploaded, "name", "sem_nome"))

            result = read_uploaded_table(uploaded)
            df = result.dataframe

            if df is None or df.empty:
                raise ValueError("A planilha foi lida, mas não possui linhas válidas.")

            st.session_state["df_origem"] = df

            add_debug_log("Arquivo lido com sucesso", f"linhas={len(df)} colunas={len(df.columns)}")

            st.success(f"Arquivo carregado com sucesso ({result.file_type}) | {result.detail}")
            st.caption(f"Linhas: {len(df)} | Colunas: {len(df.columns)}")
            st.dataframe(df.head(20), use_container_width=True)

        except Exception as exc:
            _registrar_erro_origem(exc)
            return

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📦 Cadastro de produtos", use_container_width=True):
            add_debug_log("Fluxo", "Cadastro selecionado")
            st.session_state["tipo_operacao"] = "cadastro"
            st.session_state["wizard_etapa_atual"] = "precificacao"
            st.session_state["wizard_etapa_maxima"] = "precificacao"
            st.rerun()
    with col2:
        if st.button("📊 Atualização de estoque", use_container_width=True):
            add_debug_log("Fluxo", "Estoque selecionado")
            st.session_state["tipo_operacao"] = "estoque"
            st.session_state["wizard_etapa_atual"] = "precificacao"
            st.session_state["wizard_etapa_maxima"] = "precificacao"
            st.rerun()
