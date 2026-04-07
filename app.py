from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.app_helpers import (
    garantir_estado_base,
    log_debug,
    render_debug_panel,
    render_preview_final,from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.app_helpers import (
    garantir_estado_base,
    log_debug,
    render_debug_panel,
    render_preview_final,
    sincronizar_df_final,
)
from bling_app_zero.ui.fornecedores_panel import render_fornecedores_panel
from bling_app_zero.ui.origem_dados import render_origem_dados
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
from bling_app_zero.utils.init_app import inicializar_app


# =========================
# CONFIG
# =========================
st.set_page_config(page_title="IA Planilhas Bling", layout="wide")

APP_VERSION = "1.0.20"


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

area_app = st.radio(
    "Área do sistema",
    ["Fluxo principal", "Fornecedores adaptativos"],
    horizontal=True,
    key="area_app",
)

if area_app == "Fornecedores adaptativos":
    render_fornecedores_panel()
    render_debug_panel(
        download_key="btn_baixar_log_debug_fornecedores",
        file_name="debug_fornecedores.txt",
    )
    st.stop()


# =========================
# CONTROLE DE ETAPA
# =========================
etapa = st.session_state.get("etapa_origem")

if not etapa:
    etapa = "upload"
    st.session_state["etapa_origem"] = "upload"


# =========================
# ETAPA 1 — ORIGEM
# =========================
if etapa in ["upload", "origem"]:
    render_origem_dados()
    sincronizar_df_final()


# =========================
# ETAPA 2 — ORIGEM + MAPEAMENTO
# Regra do fluxo real:
# o módulo de anexar planilhas / escolher Cadastro ou Estoque
# precisa ficar abaixo de Origem dos dados.
# Para isso, na etapa de mapeamento mantemos a Origem primeiro
# e renderizamos o próximo módulo logo abaixo.
# =========================
elif etapa == "mapeamento":
    render_origem_dados()
    sincronizar_df_final()

    st.divider()
    st.subheader("Mapeamento")
    render_origem_mapeamento()
    sincronizar_df_final()


# =========================
# ETAPA 3 — FINAL
# =========================
elif etapa == "final":
    render_preview_final()


# =========================
# FALLBACK DE ETAPA DESCONHECIDA
# =========================
else:
    log_debug(f"Etapa desconhecida recebida: {etapa}", "ERRO")
    st.warning("Etapa do fluxo inválida. Retornando para a origem.")
    st.session_state["etapa_origem"] = "upload"
    st.rerun()


# =========================
# DEBUG
# =========================
render_debug_panel(
    download_key="btn_baixar_log_debug",
    file_name="debug.txt",
)
    sincronizar_df_final,
)
from bling_app_zero.ui.fornecedores_panel import render_fornecedores_panel
from bling_app_zero.ui.origem_dados import render_origem_dados
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
from bling_app_zero.utils.init_app import inicializar_app


# =========================
# CONFIG
# =========================
st.set_page_config(page_title="IA Planilhas Bling", layout="wide")

APP_VERSION = "1.0.20"


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

area_app = st.radio(
    "Área do sistema",
    ["Fluxo principal", "Fornecedores adaptativos"],
    horizontal=True,
    key="area_app",
)

if area_app == "Fornecedores adaptativos":
    render_fornecedores_panel()
    render_debug_panel(
        download_key="btn_baixar_log_debug_fornecedores",
        file_name="debug_fornecedores.txt",
    )
    st.stop()


# =========================
# CONTROLE DE ETAPA
# =========================
etapa = st.session_state.get("etapa_origem")

if not etapa:
    etapa = "upload"
    st.session_state["etapa_origem"] = "upload"


# =========================
# ETAPA 1 — ORIGEM
# =========================
if etapa in ["upload", "origem"]:
    render_origem_dados()
    sincronizar_df_final()


# =========================
# ETAPA 2 — MAPEAMENTO
# =========================
elif etapa == "mapeamento":
    st.divider()
    st.subheader("Mapeamento")
    render_origem_mapeamento()
    sincronizar_df_final()


# =========================
# ETAPA 3 — FINAL
# =========================
elif etapa == "final":
    render_preview_final()


# =========================
# FALLBACK DE ETAPA DESCONHECIDA
# =========================
else:
    log_debug(f"Etapa desconhecida recebida: {etapa}", "ERRO")
    st.warning("Etapa do fluxo inválida. Retornando para a origem.")
    st.session_state["etapa_origem"] = "upload"
    st.rerun()


# =========================
# DEBUG
# =========================
render_debug_panel(
    download_key="btn_baixar_log_debug",
    file_name="debug.txt",
)
