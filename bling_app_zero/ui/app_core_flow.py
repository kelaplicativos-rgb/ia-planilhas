from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug, safe_df_dados, safe_df_estrutura, sincronizar_etapa_da_url
from .app_core_config import ETAPAS_ORDEM


def etapa_valida(etapa: str) -> str:
    etapa = str(etapa or "").strip()
    return etapa if etapa in ETAPAS_ORDEM else "origem"


def indice_etapa(etapa: str) -> int:
    try:
        return ETAPAS_ORDEM.index(etapa_valida(etapa))
    except Exception:
        return 0


def etapa_maxima(a: str, b: str) -> str:
    return etapa_valida(a) if indice_etapa(a) >= indice_etapa(b) else etapa_valida(b)


def definir_query_etapa(etapa: str) -> None:
    try:
        st.query_params["etapa"] = etapa_valida(etapa)
    except Exception:
        pass


def obter_query_etapa() -> str:
    try:
        valor = st.query_params.get("etapa", "")
    except Exception:
        return ""
    if isinstance(valor, list):
        return etapa_valida(valor[0] if valor else "")
    return etapa_valida(valor)


def preview_tem_df() -> bool:
    return safe_df_estrutura(st.session_state.get("df_final"))


def atualizar_etapa_maxima_por_progresso() -> None:
    maxima = etapa_valida(st.session_state.get("wizard_etapa_maxima", "origem"))

    if safe_df_dados(st.session_state.get("df_origem")):
        maxima = etapa_maxima(maxima, "precificacao")

    if safe_df_dados(st.session_state.get("df_precificado")) and safe_df_estrutura(st.session_state.get("df_modelo")):
        maxima = etapa_maxima(maxima, "mapeamento")

    if safe_df_estrutura(st.session_state.get("df_final")):
        maxima = etapa_maxima(maxima, "preview_final")

    st.session_state["wizard_etapa_maxima"] = maxima


def pre_requisitos_etapa(etapa: str) -> tuple[bool, str]:
    etapa = etapa_valida(etapa)

    if etapa == "origem":
        return True, ""

    if etapa == "precificacao":
        if safe_df_dados(st.session_state.get("df_origem")):
            return True, ""
        return False, "Carregue uma origem de dados válida antes de seguir."

    if etapa == "mapeamento":
        if not safe_df_dados(st.session_state.get("df_precificado")):
            return False, "Conclua a precificação antes de seguir para o mapeamento."
        if not safe_df_estrutura(st.session_state.get("df_modelo")):
            return False, "Carregue o modelo padrão antes de seguir para o mapeamento."
        return True, ""

    if etapa == "preview_final":
        if safe_df_estrutura(st.session_state.get("df_final")):
            return True, ""
        return False, "Gere o resultado final antes de abrir o preview."

    return False, "Etapa inválida."


def pode_abrir_etapa(etapa: str) -> bool:
    etapa = etapa_valida(etapa)
    maxima = etapa_valida(st.session_state.get("wizard_etapa_maxima", "origem"))
    return indice_etapa(etapa) <= indice_etapa(maxima)


def set_etapa_segura(etapa: str, origem: str = "sistema") -> bool:
    etapa = etapa_valida(etapa)
    atual = etapa_valida(st.session_state.get("wizard_etapa_atual", "origem"))

    if etapa == atual:
        definir_query_etapa(etapa)
        return True

    atualizar_etapa_maxima_por_progresso()

    if not pode_abrir_etapa(etapa):
        log_debug(f"Etapa bloqueada acima do progresso atual: {etapa}", nivel="AVISO")
        return False

    ok, motivo = pre_requisitos_etapa(etapa)
    if not ok:
        st.warning(motivo)
        log_debug(f"Troca bloqueada {atual} -> {etapa}: {motivo}", nivel="AVISO")
        return False

    st.session_state["wizard_etapa_atual"] = etapa
    st.session_state["etapa"] = etapa
    st.session_state["wizard_etapa_maxima"] = etapa_maxima(st.session_state.get("wizard_etapa_maxima", "origem"), etapa)
    st.session_state["ultima_etapa_renderizada"] = etapa
    definir_query_etapa(etapa)
    log_debug(f"Etapa alterada: {atual} -> {etapa} | origem={origem}", nivel="INFO")
    return True


def sincronizar_fluxo_inicial() -> None:
    try:
        sincronizar_etapa_da_url()
    except Exception:
        pass

    atualizar_etapa_maxima_por_progresso()

    etapa_url = obter_query_etapa()
    etapa_state = etapa_valida(st.session_state.get("etapa", st.session_state.get("wizard_etapa_atual", "origem")))
    referencia = etapa_url if etapa_url in ETAPAS_ORDEM else etapa_state

    if pode_abrir_etapa(referencia):
        ok, _ = pre_requisitos_etapa(referencia)
        if ok:
            st.session_state["wizard_etapa_atual"] = referencia
            st.session_state["etapa"] = referencia
            definir_query_etapa(referencia)
            return

    atual = etapa_valida(st.session_state.get("wizard_etapa_atual", "origem"))
    st.session_state["wizard_etapa_atual"] = atual
    st.session_state["etapa"] = atual
    definir_query_etapa(atual)


def avancar_para_proxima_etapa() -> bool:
    atual = etapa_valida(st.session_state.get("wizard_etapa_atual", "origem"))
    idx = indice_etapa(atual)
    if idx >= len(ETAPAS_ORDEM) - 1:
        return False
    return set_etapa_segura(ETAPAS_ORDEM[idx + 1], origem="avancar")
