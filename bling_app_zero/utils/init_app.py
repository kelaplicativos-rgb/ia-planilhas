
import streamlit as st


def init_app():
    defaults = {
        "etapa": "origem",
        "historico_etapas": ["origem"],
        "df_origem": None,
        "df_modelo": None,
        "tipo_operacao": None,
        "tipo_operacao_bling": None,
        "deposito_nome": "",
        "origem_upload_nome": "",
        "origem_upload_bytes": None,
        "origem_upload_tipo": "",
        "origem_upload_ext": "",
        "modelo_upload_nome": "",
        "modelo_upload_bytes": None,
        "modelo_upload_tipo": "",
        "modelo_upload_ext": "",
    }

    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
