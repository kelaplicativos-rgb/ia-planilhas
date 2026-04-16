import streamlit as st


def init_app():
    """Inicializa estados globais do app"""
    defaults = {
        "etapa": "origem",
        "df_origem": None,
        "df_precificado": None,
        "df_mapeado": None,
        "df_final": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
