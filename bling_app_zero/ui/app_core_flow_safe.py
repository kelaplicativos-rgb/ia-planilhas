from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.app_helpers import safe_df_dados, safe_df_estrutura
from .app_core_config import ETAPAS_ORDEM


def etapa_valida(etapa: str) -> str:
    etapa = str(etapa or "").strip()
    return etapa if etapa in ETAPAS_ORDEM else "origem"


def indice(etapa: str) -> int:
    return ETAPAS_ORDEM.index(etapa_valida(etapa))


def maxima(a: str, b: str) -> str:
    return etapa_valida(a) if indice(a) >= indice(b) else etapa_valida(b)


def query_set(etapa: str) -> None:
    try:
        st.query_params["etapa"] = etapa_valida(etapa)
    except Exception:
        pass


def query_get() -> str:
    try:
        valor = st.query_params.get("etapa", "")
    except Exception:
        return ""
    if isinstance(valor, list):
        valor = valor[0] if valor else ""
    return etapa_valida(valor)


def atualizar_maxima() -> None:
    atual = etapa_valida(st.session_state.get("wizard_etapa_maxima", "origem"))
    if safe_df_dados(st.session_state.get("df_origem")):
        atual = maxima(atual, "precificacao")
    if safe_df_dados(st.session_state.get("df_precificado")) and safe_df_estrutura(st.session_state.get("df_modelo")):
        atual = maxima(atual, "mapeamento")
    if safe_df_estrutura(st.session_state.get("df_final")):
        atual = maxima(atual, "preview_final")
    st.session_state["wizard_etapa_maxima"] = atual


def requisitos_ok(etapa: str) -> bool:
    etapa = etapa_valida(etapa)
    if etapa == "origem":
        return True
    if etapa == "precificacao":
        return safe_df_dados(st.session_state.get("df_origem"))
    if etapa == "mapeamento":
        return safe_df_dados(st.session_state.get("df_precificado")) and safe_df_estrutura(st.session_state.get("df_modelo"))
    if etapa == "preview_final":
        return safe_df_estrutura(st.session_state.get("df_final"))
    return False


def set_etapa_segura(etapa: str, origem: str = "sistema") -> bool:
    etapa = etapa_valida(etapa)
    atualizar_maxima()
    if indice(etapa) > indice(st.session_state.get("wizard_etapa_maxima", "origem")):
        return False
    if not requisitos_ok(etapa):
        return False
    st.session_state["wizard_etapa_atual"] = etapa
    st.session_state["etapa"] = etapa
    st.session_state["wizard_etapa_maxima"] = maxima(st.session_state.get("wizard_etapa_maxima", "origem"), etapa)
    query_set(etapa)
    return True


def sincronizar_fluxo_inicial() -> None:
    atualizar_maxima()
    etapa_url = query_get()
    etapa_legacy = etapa_valida(st.session_state.get("etapa", ""))
    etapa_wizard = etapa_valida(st.session_state.get("wizard_etapa_atual", "origem"))
    alvo = etapa_url if etapa_url in ETAPAS_ORDEM else etapa_legacy if etapa_legacy in ETAPAS_ORDEM else etapa_wizard
    if indice(alvo) <= indice(st.session_state.get("wizard_etapa_maxima", "origem")) and requisitos_ok(alvo):
        st.session_state["wizard_etapa_atual"] = alvo
        st.session_state["etapa"] = alvo
        query_set(alvo)
    else:
        st.session_state["wizard_etapa_atual"] = etapa_wizard
        st.session_state["etapa"] = etapa_wizard
        query_set(etapa_wizard)
