from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.cadastro_wizard_state import (
    enforce_cadastro_model_columns,
    render_row_count_blocker,
    valid_df,
)
from bling_app_zero.ui.home_shared import download_final


def render_cadastro_download_step() -> None:
    st.markdown('### Download da planilha final')
    st.caption('Baixe o arquivo final no mesmo modelo anexado no início.')

    df_final = enforce_cadastro_model_columns(st.session_state.get('df_final_cadastro'))
    if not valid_df(df_final):
        st.warning('A planilha final ainda não foi gerada. Volte ao preview.')
        return

    if render_row_count_blocker(df_final):
        return

    download_final(df_final, 'modelo', 'modelo_anexado')


__all__ = ['render_cadastro_download_step']
