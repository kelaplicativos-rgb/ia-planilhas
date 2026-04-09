from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.ui.bling_panel import render_bling_panel

# ==========================================================
# IMPORTS OPCIONAIS / BLINDAGEM
# ==========================================================
try:
    from bling_app_zero.utils.excel import (
        exportar_dataframe_para_excel as _exportar_excel_robusto,
    )
except Exception:
    _exportar_excel_robusto = None

try:
    from bling_app_zero.utils.excel import (
        df_to_excel_bytes as _df_to_excel_bytes_utils,
    )
except Exception:
    _df_to_excel_bytes_utils = None

try:
    from bling_app_zero.utils.gtin import aplicar_validacao_gtin_df
except Exception:
    aplicar_validacao_gtin_df = None


ETAPAS_VALIDAS_ORIGEM = {"origem", "mapeamento", "final"}


# ==========================================================
# ESTADO / LOG
# ==========================================================
def garantir_estado_base() -> None:
    try:
        if "logs" not in st.session_state or not isinstance(
            st.session_state.get("logs"), list
        ):
            st.session_state["logs"] = []

        etapa_atual = str(st.session_state.get("etapa_origem", "") or "").strip().lower()

        if etapa_atual not in ETAPAS_VALIDAS_ORIGEM:
            st.session_state["etapa_origem"] = "origem"

        if "area_app" not in st.session_state:
            st.session_state["area_app"] = "Fluxo principal"

        if "bloquear_campos_auto" not in st.session_state:
            st.session_state["bloquear_campos_auto"] = {}

    except Exception:
        st.session_state["logs"] = []
        st.session_state["etapa_origem"] = "origem"
        st.session_state["area_app"] = "Fluxo principal"
        st.session_state["bloquear_campos_auto"] = {}


def log_debug(msg: str, nivel: str = "INFO") -> None:
    try:
        if "logs" not in st.session_state:
            st.session_state["logs"] = []

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linha = f"[{timestamp}] [{nivel}] {msg}"
        st.session_state["logs"].append(linha)
    except Exception:
        pass


# ==========================================================
# DEBUG PANEL (🔥 AGORA COM DOWNLOAD)
# ==========================================================
def render_debug_panel() -> None:
    try:
        logs = st.session_state.get("logs", [])

        with st.expander("🧠 Debug / Logs", expanded=False):

            if not logs:
                st.caption("Nenhum log disponível.")
            else:
                texto = "\n".join(logs[-500:])
                st.text_area(
                    "Logs do sistema",
                    value=texto,
                    height=220,
                )

            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("🔄 Atualizar logs", use_container_width=True):
                    st.rerun()

            with col2:
                if st.button("🧹 Limpar logs", use_container_width=True):
                    st.session_state["logs"] = []
                    st.rerun()

            with col3:
                if logs:
                    log_bytes = "\n".join(logs).encode("utf-8")

                    st.download_button(
                        "📥 Baixar log",
                        data=log_bytes,
                        file_name="log_processamento.txt",
                        mime="text/plain",
                        use_container_width=True,
                    )

    except Exception as e:
        st.warning(f"Erro no debug panel: {e}")


# ==========================================================
# HELPERS
# ==========================================================
def safe_df_from_state(key: str) -> pd.DataFrame | None:
    df = st.session_state.get(key)
    if isinstance(df, pd.DataFrame) and len(df.columns) > 0:
        return df.copy()
    return None


def get_df_fluxo() -> pd.DataFrame | None:
    # 🔥 PRIORIDADE CORRETA
    prioridade = ["df_final", "df_saida", "df_dados", "df_base"]

    for key in prioridade:
        df = safe_df_from_state(key)
        if df is not None:
            return df

    return None


def sincronizar_df_final() -> None:
    df_fluxo = get_df_fluxo()
    if df_fluxo is not None:
        st.session_state["df_final"] = df_fluxo.copy()


# ==========================================================
# EXPORTAÇÃO
# ==========================================================
def _exportar_excel_fallback(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    return output.getvalue()


def exportar_excel_bytes(df: pd.DataFrame) -> bytes:
    if _df_to_excel_bytes_utils:
        try:
            return _df_to_excel_bytes_utils(df)
        except Exception:
            pass

    if _exportar_excel_robusto:
        try:
            return _exportar_excel_robusto(df)
        except Exception:
            pass

    return _exportar_excel_fallback(df)


def exportar_download_bytes(df: pd.DataFrame) -> bytes:
    return exportar_excel_bytes(df)


# ==========================================================
# PREVIEW FINAL
# ==========================================================
def render_preview_final() -> None:
    sincronizar_df_final()
    df = get_df_fluxo()

    if df is None:
        st.warning("Nenhum dado disponível.")
        return

    st.subheader("Preview final")

    st.dataframe(df.head(20), use_container_width=True)

    if st.button("⬅️ Voltar"):
        st.session_state["etapa_origem"] = "mapeamento"
        st.rerun()

    excel_bytes = exportar_download_bytes(df)

    st.download_button(
        "⬇️ Baixar planilha",
        data=excel_bytes,
        file_name="bling_final.xlsx",
        use_container_width=True,
    )

    # 🔥 CORREÇÃO: evitar duplicação
    if not st.session_state.get("_bling_renderizado"):
        st.session_state["_bling_renderizado"] = True

        st.subheader("Integração com Bling")
        render_bling_panel()
