from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.ui.cadastro_wizard_state import (
    enforce_cadastro_model_columns,
    render_row_count_blocker,
    render_supplier_price_master_notice,
    valid_df,
)
from bling_app_zero.ui.home_shared import preview_df, show_mapping
from bling_app_zero.ui.preview_ai_actions import render_preview_ai_actions


def _final_preview_df(df_final: pd.DataFrame) -> pd.DataFrame:
    """Aplica no preview a mesma blindagem usada na planilha final.

    Como a etapa Regras agora fica depois do mapeamento, o preview precisa
    refletir as regras atuais antes do download.
    """
    safe = sanitize_for_bling(df_final.copy().fillna(''), operation='cadastro')
    return enforce_cadastro_model_columns(safe)


def render_cadastro_preview_step() -> None:
    st.markdown('### Preview final do cadastro')
    st.caption('Confira a planilha final antes de baixar. Esta tela já reflete as configurações do arquivo final.')

    df_final = enforce_cadastro_model_columns(st.session_state.get('df_final_cadastro'))
    mapping = st.session_state.get('mapping_cadastro', {})

    if not valid_df(df_final):
        st.warning('O preview ainda não foi gerado. Volte para o mapeamento e confirme os campos.')
        return

    df_preview = _final_preview_df(df_final)
    st.session_state['df_final_cadastro_preview_rules_applied'] = df_preview

    render_supplier_price_master_notice(df_preview)

    if render_row_count_blocker(df_preview):
        return

    show_mapping(mapping, operation='cadastro')
    preview_df('🧾 CADASTRO · Preview final', df_preview)
    render_preview_ai_actions(df_preview, 'cadastro')


__all__ = ['render_cadastro_preview_step']
