
from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_dados_handlers import (
    aplicar_bloco_estoque,
    aplicar_precificacao,
    nome_coluna_preco_saida,
)


# =========================================================
# HELPERS LOCAIS
# =========================================================
def _safe_str(valor) -> str:
    try:
        if valor is None:
            return ""
        texto = str(valor).strip()
        if texto.lower() in {"none", "nan", "nat"}:
            return ""
        return texto
    except Exception:
        return ""


def _safe_df_dados(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def _safe_copy_df(df):
    try:
        return df.copy()
    except Exception:
        return df


def _float_state(key: str, default: float = 0.0) -> float:
    try:
        return float(st.session_state.get(key, default) or default)
    except Exception:
        return default


def _bool_state(key: str, default: bool = False) -> bool:
    try:
        return bool(st.session_state.get(key, default))
    except Exception:
        return default


def _set_etapa(destino: str) -> None:
    st.session_state["etapa_origem"] = destino
    st.session_state["etapa"] = destino
    st.session_state["etapa_fluxo"] = destino


def _navegar(destino: str) -> None:
    _set_etapa(destino)
    st.rerun()


def _tipo_operacao_estoque() -> bool:
    return
