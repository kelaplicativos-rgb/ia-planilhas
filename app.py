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

APP_VERSION = "1.0.21"  # 🔥 atualizei versão


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
# CONTROLE DE ETAPA (PADRONIZADO)
# =========================
if "etapa_origem" not in st.session_state:
    st.session_state["etapa_origem"] = "origem"

etapa = st.session_state.get("etapa_origem", "origem")


# =========================
# ETAPA 1 — ORIGEM
# =========================
if etapa == "origem":
    render_origem_dados()


# =========================
# ETAPA 2 — MAPEAMENTO
# =========================
elif etapa == "mapeamento":

    st.subheader("📦 Origem dos dados (resumo)")

    # 🔥 aqui NÃO chamamos origem completa
    if st.session_state.get("df_origem") is not None:
        st.dataframe(
            st.session_state["df_origem"].head(5),
            use_container_width=True,
        )

    st.divider()

    st.subheader("🔗 Mapeamento")
    render_origem_mapeamento()


# =========================
# ETAPA 3 — FINAL
# =========================
elif etapa == "final":
    render_preview_final()


# =========================
# FALLBACK
# =========================
else:
    log_debug(f"Etapa desconhecida: {etapa}", "ERRO")
    st.session_state["etapa_origem"] = "origem"
    st.rerun()


# =========================
# DEBUG
# =========================
render_debug_panel(
    download_key="btn_baixar_log_debug",
    file_name="debug.txt",
)
