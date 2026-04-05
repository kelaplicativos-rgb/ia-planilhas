# bling_app_zero/ui/state.py

import streamlit as st


def init_state():
    if "logs" not in st.session_state:
        st.session_state["logs"] = []

    if "df_saida" not in st.session_state:
        st.session_state["df_saida"] = None

    if "validacao_erros" not in st.session_state:
        st.session_state["validacao_erros"] = []

    if "validacao_avisos" not in st.session_state:
        st.session_state["validacao_avisos"] = []

    if "validacao_ok" not in st.session_state:
        st.session_state["validacao_ok"] = False

    if "ultima_chave_arquivo" not in st.session_state:
        st.session_state["ultima_chave_arquivo"] = None

    if "mapeamento_memoria" not in st.session_state:
        st.session_state["mapeamento_memoria"] = {}
