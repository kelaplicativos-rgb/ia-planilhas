from __future__ import annotations

from typing import Any

import streamlit as st

ETAPAS_VALIDAS_ORIGEM = {"origem", "mapeamento", "final", "envio", "conexao"}


def safe_str(valor: Any) -> str:
    try:
        if valor is None:
            return ""
        texto = str(valor).strip()
        if texto.lower() in {"none", "nan", "nat"}:
            return ""
        return texto
    except Exception:
        return ""


def _normalizar_etapa(valor: Any, default: str = "origem") -> str:
    etapa = safe_str(valor or default).lower()
    if etapa not in ETAPAS_VALIDAS_ORIGEM:
        return default
    return etapa


def _safe_dict(valor: Any) -> dict:
    try:
        return dict(valor or {})
    except Exception:
        return {}


def get_etapa_mapeamento() -> str:
    for chave in ["etapa_origem", "etapa", "etapa_fluxo"]:
        etapa = _normalizar_etapa(st.session_state.get(chave), "")
        if etapa:
            return etapa
    return "origem"


def set_etapa_mapeamento(etapa: str) -> None:
    etapa_normalizada = _normalizar_etapa(etapa, "origem")
    st.session_state["etapa_origem"] = etapa_normalizada
    st.session_state["etapa"] = etapa_normalizada
    st.session_state["etapa_fluxo"] = etapa_normalizada


def garantir_estado_mapeamento() -> None:
    defaults = {
        "mapping_origem": {},
        "mapping_origem_rascunho": {},
        "mapeamento_retorno_preservado": False,
        "deposito_nome": "",
        "df_preview_mapeamento": None,
    }

    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor

    st.session_state["mapping_origem"] = _safe_dict(
        st.session_state.get("mapping_origem")
    )
    st.session_state["mapping_origem_rascunho"] = _safe_dict(
        st.session_state.get("mapping_origem_rascunho")
    )

    etapa_atual = get_etapa_mapeamento()
    set_etapa_mapeamento(etapa_atual)
