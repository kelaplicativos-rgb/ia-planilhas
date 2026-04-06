from __future__ import annotations

from datetime import datetime
import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_dados_helpers import (
    limpar_gtin_invalido,
    validar_campos_obrigatorios,
    exportar_excel_bytes,
)

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="IA Planilhas Bling", layout="wide")

APP_VERSION = "1.0.15"

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
    except Exception:
        pass


# =========================
# HELPERS
# =========================
def _safe_df(key):
    df = st.session_state.get(key)
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df
    return None


def _get_df_fluxo():
    return _safe_df("df_final") or _safe_df("df_saida")


# =========================
# IMPORTS
# =========================
from bling_app_zero.ui.origem_dados import render_origem_dados
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
from bling_app_zero.ui.bling_panel import render_bling_panel

# =========================
# UI
# =========================
st.title("IA Planilhas → Bling")
st.caption(f"Versão: {APP_VERSION}")

# =========================
# FLUXO
# =========================
etapa = st.session_state.get("etapa_origem", "upload")

# ORIGEM
render_origem_dados()

etapa = st.session_state.get("etapa_origem", "upload")

# MAPEAMENTO
if etapa == "mapeamento":
    st.divider()
    st.subheader("Mapeamento")
    render_origem_mapeamento()

# FLUXO FINAL
df_fluxo = _get_df_fluxo()

if df_fluxo is not None:
    st.divider()
    st.subheader("Preview final")

    # 🔥 COLAPSADO
    with st.expander("📦 Ver dados finais", expanded=False):
        st.dataframe(df_fluxo.head(20), width="stretch")

    # 🔥 LIMPEZA GTIN
    df_fluxo = limpar_gtin_invalido(df_fluxo)

    # 🔥 VALIDAÇÃO
    if not validar_campos_obrigatorios(df_fluxo):
        st.error("Preencha os campos obrigatórios antes do download")
        st.stop()

    # 🔥 DOWNLOAD
    excel_bytes = exportar_excel_bytes(df_fluxo)

    st.download_button(
        "⬇️ Baixar planilha final",
        excel_bytes,
        "bling_final.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# =========================
# BLING PANEL
# =========================
if df_fluxo is not None:
    st.divider()
    st.subheader("Integração com Bling")
    render_bling_panel()

# =========================
# DEBUG
# =========================
with st.expander("🔍 Debug"):
    logs = st.session_state.get("logs", [])

    for l in reversed(logs[-50:]):
        st.text(l)

    st.download_button(
        "📥 Baixar log",
        "\n".join(logs),
        "debug.txt",
    )
