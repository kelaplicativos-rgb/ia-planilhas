from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_dados_helpers import (
    exportar_excel_bytes,
    limpar_gtin_invalido,
    validar_campos_obrigatorios,
)

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="IA Planilhas Bling", layout="wide")

APP_VERSION = "1.0.21"

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
def _safe_df(key: str) -> pd.DataFrame | None:
    df = st.session_state.get(key)
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df
    return None


def _get_df_fluxo() -> pd.DataFrame | None:
    for key in ["df_saida", "df_precificado", "df_origem"]:
        df = _safe_df(key)
        if df is not None:
            return df
    return None


# =========================
# IMPORTS
# =========================
from bling_app_zero.ui.bling_panel import render_bling_panel
from bling_app_zero.ui.origem_dados import render_origem_dados
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento

# =========================
# UI
# =========================
st.title("IA Planilhas → Bling")
st.caption(f"Versão: {APP_VERSION}")

etapa = st.session_state.get("etapa_origem", "upload")

# =========================
# ETAPA 1
# =========================
if etapa in ["upload", None]:
    render_origem_dados()

# =========================
# ETAPA 2
# =========================
elif etapa == "mapeamento":
    st.subheader("Mapeamento")
    render_origem_mapeamento()

    st.divider()

    # 🔥 BOTÃO REAL PARA IR PRO FINAL
    if st.button("➡️ Ir para revisão final", use_container_width=True):
        st.session_state["etapa_origem"] = "final"
        st.rerun()

# =========================
# ETAPA 3 (FINAL REAL)
# =========================
elif etapa == "final":

    df_fluxo = _get_df_fluxo()

    if df_fluxo is not None:

        st.subheader("Preview final")

        with st.expander("📦 Ver dados finais", expanded=True):
            st.dataframe(df_fluxo.head(20), width="stretch")

        df_download = limpar_gtin_invalido(df_fluxo.copy())

        if not validar_campos_obrigatorios(df_download):
            st.error("Preencha os campos obrigatórios antes do download")
            st.stop()

        excel_bytes = exportar_excel_bytes(df_download)

        st.download_button(
            "⬇️ Baixar planilha final",
            excel_bytes,
            "bling_final.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

        st.divider()

        if st.button("⬅️ Voltar para mapeamento"):
            st.session_state["etapa_origem"] = "mapeamento"
            st.rerun()

        st.subheader("Integração com Bling")
        render_bling_panel()

    else:
        st.warning("Nenhum dado disponível para o preview final.")

# =========================
# DEBUG
# =========================
with st.expander("🔍 Debug"):
    logs = st.session_state.get("logs", [])

    for linha in reversed(logs[-50:]):
        st.text(linha)

    st.download_button(
        "📥 Baixar log",
        "\n".join(logs),
        "debug.txt",
        use_container_width=True,
    )
