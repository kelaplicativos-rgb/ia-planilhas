from __future__ import annotations

import streamlit as st
import pandas as pd


def _avancar() -> None:
    st.session_state["wizard_etapa_atual"] = "preview_final"
    st.session_state["wizard_etapa_maxima"] = "preview_final"
    st.rerun()


def _voltar() -> None:
    st.session_state["wizard_etapa_atual"] = "precificacao"
    st.rerun()


def render_origem_mapeamento() -> None:
    st.title("3. Mapeamento")

    df = st.session_state.get("df_origem")

    if df is None:
        st.warning("Nenhuma base carregada ainda. Usando exemplo temporário.")
        df = pd.DataFrame({"produto": ["Exemplo A", "Exemplo B"], "preco": [10, 20]})
        st.session_state["df_origem"] = df

    st.dataframe(df.head(), use_container_width=True)

    st.info("Mapeamento simplificado ativo (modo seguro).")

    st.session_state["df_mapeado"] = df.copy()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Voltar", use_container_width=True):
            _voltar()
    with col2:
        if st.button("Avançar para preview ➡️", use_container_width=True):
            _avancar()
