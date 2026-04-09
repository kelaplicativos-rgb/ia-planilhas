from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st

# ==========================================================
# BLING PANEL (BLINDADO)
# ==========================================================
try:
    from bling_app_zero.ui.bling_panel import render_bling_panel
except Exception:
    def render_bling_panel():
        st.warning("Painel do Bling indisponível no momento.")

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
    from bling_app_zero.utils.excel import (
        exportar_excel_com_modelo as _exportar_excel_com_modelo,
    )
except Exception:
    _exportar_excel_com_modelo = None

try:
    from bling_app_zero.utils.gtin import aplicar_validacao_gtin_em_colunas_automaticas
except Exception:
    aplicar_validacao_gtin_em_colunas_automaticas = None


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

        if "etapa" not in st.session_state:
            st.session_state["etapa"] = st.session_state.get("etapa_origem", "origem")

        if "etapa_fluxo" not in st.session_state:
            st.session_state["etapa_fluxo"] = st.session_state.get("etapa_origem", "origem")

        if "area_app" not in st.session_state:
            st.session_state["area_app"] = "Fluxo principal"

        if "bloquear_campos_auto" not in st.session_state:
            st.session_state["bloquear_campos_auto"] = {}

        if "gtin_modo_valor" not in st.session_state:
            st.session_state["gtin_modo_valor"] = "limpar"

        if "gtin_modo_label" not in st.session_state:
            st.session_state["gtin_modo_label"] = "Deixar vazio"

        if "preview_final_valido" not in st.session_state:
            st.session_state["preview_final_valido"] = True

        if "campos_obrigatorios_faltantes" not in st.session_state:
            st.session_state["campos_obrigatorios_faltantes"] = []

        if "campos_obrigatorios_alertas" not in st.session_state:
            st.session_state["campos_obrigatorios_alertas"] = []

    except Exception:
        st.session_state["logs"] = []
        st.session_state["etapa_origem"] = "origem"
        st.session_state["etapa"] = "origem"
        st.session_state["etapa_fluxo"] = "origem"
        st.session_state["area_app"] = "Fluxo principal"
        st.session_state["bloquear_campos_auto"] = {}
        st.session_state["gtin_modo_valor"] = "limpar"
        st.session_state["gtin_modo_label"] = "Deixar vazio"
        st.session_state["preview_final_valido"] = True
        st.session_state["campos_obrigatorios_faltantes"] = []
        st.session_state["campos_obrigatorios_alertas"] = []


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
# HELPERS
# ==========================================================
def safe_df_from_state(key: str) -> pd.DataFrame | None:
    df = st.session_state.get(key)
    if isinstance(df, pd.DataFrame) and len(df.columns) > 0:
        return df.copy()
    return None


def get_df_fluxo() -> pd.DataFrame | None:
    for key in ["df_final", "df_saida", "df_dados", "df_base"]:
        df = safe_df_from_state(key)
        if df is not None:
            return df
    return None


def sincronizar_df_final() -> None:
    df_fluxo = get_df_fluxo()
    if df_fluxo is not None:
        st.session_state["df_final"] = df_fluxo.copy()


def _safe_str(valor: Any) -> str:
    try:
        return str(valor or "").strip()
    except Exception:
        return ""


def _normalizar_coluna(nome: Any) -> str:
    return _safe_str(nome).lower()


def _tem_coluna_gtin(df: pd.DataFrame) -> bool:
    return any("gtin" in _normalizar_coluna(col) or "ean" in _normalizar_coluna(col) for col in df.columns)


# ==========================================================
# GTIN
# ==========================================================
def _aplicar_tratamento_gtin(df: pd.DataFrame) -> pd.DataFrame:
    if aplicar_validacao_gtin_em_colunas_automaticas is None:
        return df

    if not _tem_coluna_gtin(df):
        return df

    try:
        modo = _safe_str(st.session_state.get("gtin_modo_valor") or "limpar").lower()

        df_tratado, logs = aplicar_validacao_gtin_em_colunas_automaticas(
            df.copy(),
            preservar_coluna_original=False,
            modo=modo,
            tamanho_gerado=13,
        )

        for linha in logs[:50]:
            log_debug(linha, "INFO")

        return df_tratado

    except Exception as e:
        log_debug(f"Falha GTIN: {e}", "ERROR")
        return df


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
    return _exportar_excel_fallback(df)


def exportar_download_bytes(df: pd.DataFrame) -> bytes:
    try:
        df_modelo = (
            st.session_state.get("df_modelo_cadastro")
            or st.session_state.get("df_modelo_estoque")
        )

        if _exportar_excel_com_modelo and isinstance(df_modelo, pd.DataFrame):
            return _exportar_excel_com_modelo(df, df_modelo)

        return exportar_excel_bytes(df)

    except Exception:
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

    df_final = _aplicar_tratamento_gtin(df.copy())

    st.session_state["df_final"] = df_final.copy()
    st.session_state["df_saida"] = df_final.copy()

    st.subheader("Preview final")
    st.dataframe(df_final.head(20), use_container_width=True)

    col_voltar, col_download = st.columns([1, 3])

    with col_voltar:
        if st.button("⬅️ Voltar", use_container_width=True):
            st.session_state["etapa_origem"] = "mapeamento"
            st.rerun()

    excel_bytes = None

    try:
        excel_bytes = exportar_download_bytes(df_final)
        if not excel_bytes:
            raise ValueError("Arquivo vazio")
    except Exception as e:
        log_debug(f"Erro download: {e}", "ERROR")
        st.error(f"Erro ao gerar arquivo: {e}")

    with col_download:
        st.download_button(
            "⬇️ Baixar planilha",
            data=excel_bytes,
            file_name="bling_export.xlsx",
            use_container_width=True,
            disabled=(excel_bytes is None),
        )

    render_bling_panel()
