from __future__ import annotations

import streamlit as st

ETAPAS_VALIDAS_ORIGEM = {"origem", "mapeamento", "final", "envio", "conexao"}


def get_etapa_mapeamento() -> str:
    for chave in ["etapa_origem", "etapa", "etapa_fluxo"]:
        valor = str(st.session_state.get(chave) or "").strip().lower()
        if valor:
            return valor
    return "origem"


def set_etapa_mapeamento(etapa: str) -> None:
    etapa_normalizada = str(etapa or "").strip().lower()
    if etapa_normalizada not in ETAPAS_VALIDAS_ORIGEM:
        etapa_normalizada = "origem"

    st.session_state["etapa_origem"] = etapa_normalizada
    st.session_state["etapa"] = etapa_normalizada
    st.session_state["etapa_fluxo"] = etapa_normalizada


def garantir_estado_mapeamento() -> None:
    if "mapping_origem" not in st.session_state or not isinstance(
        st.session_state.get("mapping_origem"), dict
    ):
        st.session_state["mapping_origem"] = {}

    if "deposito_nome" not in st.session_state:
        st.session_state["deposito_nome"] = ""
