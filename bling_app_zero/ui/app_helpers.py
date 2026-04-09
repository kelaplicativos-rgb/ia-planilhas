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


# 🔥 CORREÇÃO PRINCIPAL
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

        # 🔥 NÃO RESETAR FINAL
        if etapa_atual not in ETAPAS_VALIDAS_ORIGEM:
            st.session_state["etapa_origem"] = "origem"

        if "area_app" not in st.session_state or not st.session_state.get("area_app"):
            st.session_state["area_app"] = "Fluxo principal"

        if "bloquear_campos_auto" not in st.session_state or not isinstance(
            st.session_state.get("bloquear_campos_auto"), dict
        ):
            st.session_state["bloquear_campos_auto"] = {}

    except Exception:
        try:
            st.session_state["logs"] = st.session_state.get("logs", [])
            st.session_state["etapa_origem"] = "origem"
            st.session_state["area_app"] = "Fluxo principal"
            st.session_state["bloquear_campos_auto"] = st.session_state.get(
                "bloquear_campos_auto", {}
            )
        except Exception:
            pass


def log_debug(msg: str, nivel: str = "INFO") -> None:
    try:
        if "logs" not in st.session_state or not isinstance(
            st.session_state.get("logs"), list
        ):
            st.session_state["logs"] = []

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linha = f"[{timestamp}] [{nivel}] {msg}"
        st.session_state["logs"].append(linha)
    except Exception:
        pass


# ==========================================================
# HELPERS GERAIS
# ==========================================================
def _safe_text(value: Any) -> str:
    try:
        if value is None:
            return ""
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def safe_df_from_state(key: str) -> pd.DataFrame | None:
    df = st.session_state.get(key)
    if isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0:
        return df.copy()
    return None


def get_df_fluxo() -> pd.DataFrame | None:
    for key in ["df_saida", "df_final", "df_precificado", "df_origem"]:
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
    df_saida = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_saida.to_excel(writer, sheet_name="Planilha", index=False)

    output.seek(0)
    return output.getvalue()


def exportar_excel_bytes(df: pd.DataFrame) -> bytes:
    if _df_to_excel_bytes_utils is not None:
        try:
            retorno = _df_to_excel_bytes_utils(df)
            if isinstance(retorno, bytes):
                return retorno
            if hasattr(retorno, "getvalue"):
                return retorno.getvalue()
        except Exception:
            pass

    if _exportar_excel_robusto is not None:
        try:
            retorno = _exportar_excel_robusto(df)
            if isinstance(retorno, bytes):
                return retorno
            if hasattr(retorno, "getvalue"):
                return retorno.getvalue()
        except Exception:
            pass

    return _exportar_excel_fallback(df)


def exportar_download_bytes(df: pd.DataFrame) -> bytes:
    return exportar_excel_bytes(df)


# ==========================================================
# PREVIEW FINAL (JÁ FUNCIONANDO)
# ==========================================================
def render_preview_final() -> None:
    sincronizar_df_final()
    df_fluxo = get_df_fluxo()

    if df_fluxo is None:
        st.warning("Nenhum dado disponível para o preview final.")
        return

    st.divider()
    st.subheader("Preview final")

    with st.expander("📦 Ver dados finais", expanded=False):
        st.dataframe(df_fluxo.head(20), use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("⬅️ Voltar para mapeamento", use_container_width=True):
            st.session_state["etapa_origem"] = "mapeamento"
            st.rerun()

    with col2:
        if st.button("🔄 Atualizar preview", use_container_width=True):
            st.session_state["df_final"] = df_fluxo.copy()
            st.rerun()

    excel_bytes = exportar_download_bytes(df_fluxo)

    if excel_bytes:
        st.download_button(
            "⬇️ Baixar planilha final",
            data=excel_bytes,
            file_name="bling_final.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    st.divider()
    st.subheader("Integração com Bling")
    render_bling_panel()
