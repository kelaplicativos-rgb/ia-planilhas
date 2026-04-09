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
# UI
# =========================
st.title("IA Planilhas → Bling")
st.caption(f"Versão: {APP_VERSION}")

if st.session_state.get("_cache_log"):
    st.info(st.session_state.get("_cache_log"))


# =========================
# BLINDAGEM GLOBAL DE ETAPA
# =========================
ETAPAS_VALIDAS = {"origem", "mapeamento", "final"}

if "etapa_origem" not in st.session_state:
    st.session_state["etapa_origem"] = "origem"

etapa = str(st.session_state.get("etapa_origem", "origem") or "origem").strip().lower()

if etapa not in ETAPAS_VALIDAS:
    log_debug(f"Etapa inválida detectada no app.py: {etapa}", "ERROR")
    st.session_state["etapa_origem"] = "origem"
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
# DEBUG
# =========================
render_debug_panel(
    download_key="btn_baixar_log_debug",
    file_name="debug.txt",
)
