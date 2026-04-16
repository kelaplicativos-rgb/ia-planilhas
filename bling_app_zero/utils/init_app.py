
import streamlit as st

def init_app():
    defaults = {
        "etapa": "origem",
        "df_origem": None,
        "df_modelo": None,
        "tipo_operacao": None,
        "tipo_operacao_bling": None,
        "deposito_nome": "",
    }

    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
