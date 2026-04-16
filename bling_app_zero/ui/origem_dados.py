
from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug, safe_df_dados
from bling_app_zero.ui.ia_panel import render_ia_panel


def _sincronizar_etapa(etapa: str) -> None:
    st.session_state["etapa"] = etapa
    st.session_state["etapa_origem"] = etapa
    st.session_state["etapa_fluxo"] = etapa


def _get_df_origem() -> pd.DataFrame:
    df = st.session_state.get("df_origem")
    if safe_df_dados(df):
        return df.copy()
    return pd.DataFrame()


def render_origem_dados() -> pd.DataFrame | None:
    """
    Compatibilidade com imports antigos.

    O fluxo manual foi removido do projeto.
    Esta tela agora apenas encaminha para o IA Orquestrador.
    """
    st.markdown("### Origem dos dados")
    st.info(
        "O fluxo manual foi removido. "
        "Agora a entrada do sistema acontece somente pelo IA Orquestrador."
    )

    st.session_state["modo_execucao"] = "ia_orquestrador"
    _sincronizar_etapa("ia")

    render_ia_panel()

    df = _get_df_origem()
    if safe_df_dados(df):
        log_debug(
            f"Origem preparada via IA com {len(df)} linha(s).",
            "INFO",
        )
        return df

    return None
