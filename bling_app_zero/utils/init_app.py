
from __future__ import annotations

import streamlit as st

APP_VERSION = "2.0.0"


def init_app_state() -> None:
    defaults = {
        "app_version": APP_VERSION,
        "etapa": "origem",
        "etapa_origem": "origem",
        "tipo_operacao": "Cadastro de Produtos",
        "tipo_operacao_bling": "cadastro",
        "df_origem": None,
        "df_saida": None,
        "df_precificado": None,
        "df_calc_precificado": None,
        "df_mapeado": None,
        "df_final": None,
        "df_preview_mapeamento": None,
        "df_modelo_operacao": None,
        "deposito_nome": "",
        "origem_tipo": "",
        "origem_site_url": "",
        "padrao_disponivel_site": 10,
        "usar_calculadora_precificacao": True,
        "precificacao_margem": 30.0,
        "precificacao_impostos": 10.0,
        "precificacao_custo_fixo": 0.0,
        "precificacao_taxa_extra": 0.0,
        "mapping_origem": {},
        "mapping_origem_rascunho": {},
        "mapping_origem_defaults": {},
        "debug_logs": [],
    }

    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def reset_fluxo_principal() -> None:
    for chave in [
        "df_origem",
        "df_saida",
        "df_precificado",
        "df_calc_precificado",
        "df_mapeado",
        "df_final",
        "df_preview_mapeamento",
        "df_modelo_operacao",
    ]:
        st.session_state[chave] = None

    for chave in [
        "mapping_origem",
        "mapping_origem_rascunho",
        "mapping_origem_defaults",
    ]:
        st.session_state[chave] = {}

    st.session_state["etapa"] = "origem"
    st.session_state["etapa_origem"] = "origem"


def reset_app_completo() -> None:
    chaves = list(st.session_state.keys())
    for chave in chaves:
        del st.session_state[chave]
    init_app_state()
