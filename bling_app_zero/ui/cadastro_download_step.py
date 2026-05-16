from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.bling_links_panel import render_bling_links_panel
from bling_app_zero.ui.cadastro_wizard_state import (
    enforce_cadastro_model_columns,
    render_row_count_blocker,
    render_supplier_price_master_notice,
    valid_df,
)
from bling_app_zero.ui.home_shared import download_final


def render_cadastro_download_step() -> None:
    st.markdown('### Download do cadastro')
    st.caption('Última etapa: baixe somente a planilha final de cadastro pronta para importação.')

    df_final = enforce_cadastro_model_columns(st.session_state.get('df_final_cadastro'))
    if not valid_df(df_final):
        st.warning('Ainda não há planilha final de cadastro. Volte para o preview.')
        return

    render_supplier_price_master_notice(df_final)

    if render_row_count_blocker(df_final):
        return

    download_final(df_final, 'cadastro', 'cadastro_wizard')
    render_bling_links_panel()


__all__ = ['render_cadastro_download_step']
