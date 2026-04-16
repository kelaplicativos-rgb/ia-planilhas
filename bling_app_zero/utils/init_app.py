import streamlit as st


def init_app():
    defaults = {
        "etapa": "origem",
        "historico_etapas": ["origem"],
        "df_origem": None,
        "df_modelo": None,
        "df_precificado": None,
        "df_final": None,
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
        "pricing_coluna_custo": "",
        "pricing_custo_fixo": 0.0,
        "pricing_frete_fixo": 0.0,
        "pricing_taxa_extra": 0.0,
        "pricing_impostos_percent": 0.0,
        "pricing_margem_percent": 0.0,
        "pricing_outros_percent": 0.0,
        "pricing_df_preview": None,
        "mapping_manual": {},
        "mapping_sugerido": {},
    }

    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
