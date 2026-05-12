from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.cadastro_wizard_state import (
    enforce_cadastro_model_columns,
    render_row_count_blocker,
    render_supplier_price_master_notice,
    valid_df,
)
from bling_app_zero.ui.home_shared import preview_df, show_mapping
from bling_app_zero.ui.preview_ai_actions import render_preview_ai_actions


def render_cadastro_preview_step() -> None:
    st.markdown('### Preview final do cadastro')
    st.caption('Confira o CSV final antes de baixar. Esta tela não reabre o mapeamento para evitar carga desnecessária.')

    df_final = enforce_cadastro_model_columns(st.session_state.get('df_final_cadastro'))
    mapping = st.session_state.get('mapping_cadastro', {})

    if not valid_df(df_final):
        st.warning('O preview ainda não foi gerado. Volte para o mapeamento e confirme os campos.')
        return

    render_supplier_price_master_notice(df_final)

    if render_row_count_blocker(df_final):
        return

    show_mapping(mapping, operation='cadastro')
    preview_df('🧾 CADASTRO · Preview final', df_final)
    render_preview_ai_actions(df_final, 'cadastro')


__all__ = ['render_cadastro_preview_step']
