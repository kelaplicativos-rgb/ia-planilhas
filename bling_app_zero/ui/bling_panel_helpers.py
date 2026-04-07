from __future__ import annotations

import pandas as pd
import streamlit as st


# ==========================================================
# BLOQUEIO DE FLUXO
# ==========================================================
def get_etapa_fluxo() -> str:
    try:
        return str(st.session_state.get("etapa_origem", "") or "").strip().lower()
    except Exception:
        return ""


def bloquear_painel_principal() -> bool:
    """
    Bloqueia o painel principal do Bling somente durante o mapeamento.
    Na etapa final ele deve aparecer normalmente, pois o app.py o chama
    dentro do preview final.
    """
    etapa = get_etapa_fluxo()
    return etapa == "mapeamento"


def bloquear_importacao() -> bool:
    """
    A importação do Bling deve ficar bloqueada durante o fluxo principal
    para não interferir no preparo da planilha.
    """
    etapa = get_etapa_fluxo()
    return etapa in {"mapeamento", "final"}


# ==========================================================
# HELPERS
# ==========================================================
def status_texto(status: dict) -> str:
    if not isinstance(status, dict) or not status.get("connected"):
        return "Desconectado"

    nome = status.get("company_name")
    return f"Conectado{f' • {nome}' if nome else ''}"


def has_callback_params() -> bool:
    try:
        return "code" in st.query_params or "error" in st.query_params
    except Exception:
        return False


def clear_callback_params() -> None:
    try:
        for chave in ["code", "state", "error", "error_description"]:
            if chave in st.query_params:
                del st.query_params[chave]
    except Exception:
        pass


def safe_df(df) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame):
        return df.copy()
    return pd.DataFrame()
