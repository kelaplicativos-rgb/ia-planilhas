from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.ui.cadastro_wizard_state import (
    enforce_cadastro_model_columns,
    render_row_count_blocker,
    valid_df,
)
from bling_app_zero.ui.home_shared import preview_df


def _final_preview_df(df_final: pd.DataFrame) -> pd.DataFrame:
    """Aplica no preview a mesma blindagem usada na planilha final."""
    safe = sanitize_for_bling(df_final.copy().fillna(''), operation='cadastro')
    return enforce_cadastro_model_columns(safe)


def render_cadastro_preview_step() -> None:
    st.markdown('### Preview da planilha final')
    st.caption('Confira se o arquivo final segue o modelo anexado no início.')

    df_final = enforce_cadastro_model_columns(st.session_state.get('df_final_cadastro'))

    if not valid_df(df_final):
        st.warning('O preview ainda não foi gerado. Volte para o mapeamento e confirme os campos.')
        return

    df_preview = _final_preview_df(df_final)
    st.session_state['df_final_cadastro_preview_rules_applied'] = df_preview

    if render_row_count_blocker(df_preview):
        return

    preview_df('Planilha final', df_preview)


__all__ = ['render_cadastro_preview_step']
