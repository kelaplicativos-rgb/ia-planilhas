from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.app_helpers import (
    garantir_estado_base,
    log_debug,
    render_debug_panel,
    render_preview_final,
)
from bling_app_zero.ui.origem_dados import render_origem_dados
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
from bling_app_zero.utils.init_app import inicializar_app


# =========================
# CONFIG
# =========================
st.set_page_config(page_title="IA Planilhas Bling", layout="wide")

APP_VERSION = "1.0.22"


# =========================
# INICIALIZAÇÃO
# =========================
inicializar_app()
garantir_estado_base()


# =========================
# HELPERS DE ETAPA
# =========================
ETAPAS_VALIDAS = {"origem", "mapeamento", "final"}


def _normalizar_etapa(valor: object) -> str:
    try:
        etapa_normalizada = str(valor or "origem").strip().lower()
    except Exception:
        etapa_normalizada = "origem"

    if etapa_normalizada not in ETAPAS_VALIDAS:
        return "origem"

    return etapa_normalizada


def _obter_etapa_atual() -> str:
    """
    Lê a etapa atual com compatibilidade entre chaves antigas e novas.
    Isso evita travar fluxo quando algum módulo grava em `etapa`
    e outro lê `etapa_origem`.
    """
    candidatos = [
        st.session_state.get("etapa_origem"),
        st.session_state.get("etapa"),
        st.session_state.get("etapa_fluxo"),
    ]

    for valor in candidatos:
        etapa_lida = _normalizar_etapa(valor)
        if etapa_lida in ETAPAS_VALIDAS:
            return etapa_lida

    return "origem"


def _sincronizar_etapa_global(etapa_destino: str) -> str:
    """
    Mantém as chaves de etapa sincronizadas para blindar o fluxo
    contra perda de estado entre módulos.
    """
    etapa_ok = _normalizar_etapa(etapa_destino)

    st.session_state["etapa_origem"] = etapa_ok
    st.session_state["etapa"] = etapa_ok
    st.session_state["etapa_fluxo"] = etapa_ok

    return etapa_ok


# =========================
# UI
# =========================
st.title("IA Planilhas → Bling")
st.caption(f"Versão: {APP_VERSION}")

if st.session_state.get("_cache_log"):
    st.info(st.session_state.get("_cache_log"))


# =========================
# BLINDAGEM GLOBAL DE ETAPA
# =========================
etapa = _sincronizar_etapa_global(_obter_etapa_atual())

if etapa not in ETAPAS_VALIDAS:
    log_debug(f"Etapa inválida detectada no app.py: {etapa}", "ERROR")
    _sincronizar_etapa_global("origem")
    st.rerun()


# =========================
# ETAPA 1 — ORIGEM
# =========================
if etapa == "origem":
    render_origem_dados()


# =========================
# ETAPA 2 — MAPEAMENTO
# =========================
elif etapa == "mapeamento":
    render_origem_mapeamento()


# =========================
# ETAPA 3 — FINAL / DOWNLOAD
# =========================
elif etapa == "final":
    render_preview_final()


# =========================
# FALLBACK DE SEGURANÇA
# =========================
else:
    log_debug(f"Fallback acionado no app.py para etapa inesperada: {etapa}", "ERROR")
    _sincronizar_etapa_global("origem")
    st.rerun()


# =========================
# DEBUG
# =========================
render_debug_panel()
