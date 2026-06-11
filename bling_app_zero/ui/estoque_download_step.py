from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.estoque_outputs import render_stock_downloads
from bling_app_zero.ui.estoque_wizard_state import build_stock_outputs_if_possible


def render_estoque_download_step() -> None:
    st.markdown('### Download')
    st.caption('Baixe o modelo mapeado usando exatamente o layout anexado.')

    if not build_stock_outputs_if_possible():
        st.warning('Ainda não há modelo mapeado. Volte para o mapeamento.')
        return
    render_stock_downloads()


__all__ = ['render_estoque_download_step']
