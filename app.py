from __future__ import annotations

from datetime import datetime
import pandas as pd
import streamlit as st

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="IA Planilhas Bling", layout="wide")

APP_VERSION = "1.0.13"

# =========================
# LOG
# =========================
if "logs" not in st.session_state:
    st.session_state["logs"] = []

def log_debug(msg: str, nivel: str = "INFO") -> None:
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linha = f"[{timestamp}] [{nivel}] {msg}"
        st.session_state["logs"].append(linha)
    except:
        pass

# =========================
# HELPERS
# =========================
def _safe_df(key):
    df = st.session_state.get(key)
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df
    return None

def _get_df_origem():
    return _safe_df("df_origem")

def _get_df_final():
    return _safe_df("df_final")

# =========================
# IMPORTS
# =========================
try:
    from bling_app_zero.ui.origem_dados import render_origem_dados
except:
    render_origem_dados = None

try:
    from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
except:
    render_origem_mapeamento = None

try:
    from bling_app_zero.ui.bling_panel import render_bling_panel
except:
    render_bling_panel = None

# =========================
# UI
# =========================
st.title("IA Planilhas → Bling")
st.caption(f"Versão: {APP_VERSION}")

# =========================
# FLUXO
# =========================
etapa = st.session_state.get("etapa_origem", "upload")

df_origem = _get_df_origem()
df_final = _get_df_final()

# =========================
# ETAPA 1 - ORIGEM
# =========================
if etapa == "upload":

    if render_origem_dados:
        render_origem_dados()
    else:
        st.error("Erro módulo origem")

# =========================
# ETAPA 2 - MAPEAMENTO
# =========================
elif etapa == "mapeamento":

    if df_origem is None:
        st.warning("Nenhum dado carregado")
        if st.button("Voltar"):
            st.session_state["etapa_origem"] = "upload"
            st.rerun()
    else:
        if render_origem_mapeamento:
            render_origem_mapeamento()
        else:
            st.error("Erro módulo mapeamento")

# =========================
# ETAPA 3 - BLING
# =========================
if df_final is not None:
    st.divider()
    st.subheader("Integração com Bling")

    if render_bling_panel:
        render_bling_panel()

# =========================
# DEBUG
# =========================
with st.expander("🔍 Debug do sistema"):
    logs = st.session_state.get("logs", [])

    for l in reversed(logs[-50:]):
        st.text(l)

    st.download_button(
        "Baixar log",
        "\n".join(logs),
        "debug.txt"
    )
