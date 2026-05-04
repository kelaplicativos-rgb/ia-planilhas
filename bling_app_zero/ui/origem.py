from __future__ import annotations

import streamlit as st

from bling_app_zero.core.csv_reader import read_csv_robusto


def render_origem_dados() -> None:
    st.title("1. Origem dos dados")

    st.subheader("Upload de planilha (CSV)")
    uploaded = st.file_uploader("Envie seu CSV", type=["csv"])

    if uploaded is not None:
        try:
            result = read_csv_robusto(uploaded)
            df = result.dataframe

            st.session_state["df_origem"] = df

            st.success(f"CSV carregado com sucesso | Encoding: {result.encoding} | Separador: '{result.separator}'")
            st.dataframe(df.head(), use_container_width=True)

        except Exception as e:
            st.error(f"Não foi possível ler a origem: {e}")
            return

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📦 Cadastro de produtos", use_container_width=True):
            st.session_state["tipo_operacao"] = "cadastro"
            st.session_state["wizard_etapa_atual"] = "precificacao"
            st.session_state["wizard_etapa_maxima"] = "precificacao"
            st.rerun()
    with col2:
        if st.button("📊 Atualização de estoque", use_container_width=True):
            st.session_state["tipo_operacao"] = "estoque"
            st.session_state["wizard_etapa_atual"] = "precificacao"
            st.session_state["wizard_etapa_maxima"] = "precificacao"
            st.rerun()
