from __future__ import annotations

from datetime import datetime
import pandas as pd
import streamlit as st


# ==========================================================
# HELPERS
# ==========================================================
def _safe_dataframe_preview(df: pd.DataFrame, rows: int = 20):
    if df is None or df.empty:
        return pd.DataFrame()
    return df.head(rows)


# ==========================================================
# LOG
# ==========================================================
def _build_log():
    logs = st.session_state.get("logs", [])
    texto = "\n".join(logs) if logs else "Sem logs"
    return texto


# ==========================================================
# MAIN
# ==========================================================
def render_origem_mapeamento():

    # 🔥 PUXAR DO SESSION STATE (ESSA É A CORREÇÃO)
    df = st.session_state.get("df_final")

    if df is None or df.empty:
        st.warning("Nenhum dado disponível para mapeamento.")
        return

    st.markdown("### Preview da saída")
    st.dataframe(_safe_dataframe_preview(df), width="stretch")

    st.divider()

    col1, col2 = st.columns(2)

    # =========================
    # DOWNLOAD
    # =========================
    with col1:
        try:
            from io import BytesIO

            buffer = BytesIO()
            df.to_excel(buffer, index=False)
            buffer.seek(0)

            st.download_button(
                "Baixar planilha",
                buffer,
                "saida.xlsx",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"Erro ao gerar Excel: {e}")

    # =========================
    # LOG DOWNLOAD
    # =========================
    with col2:
        log_texto = _build_log()

        st.download_button(
            "Baixar log",
            log_texto,
            "log.txt",
            use_container_width=True,
        )
