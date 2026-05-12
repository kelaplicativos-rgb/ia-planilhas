from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.estoque_outputs import render_stock_preview
from bling_app_zero.ui.estoque_wizard_state import build_stock_outputs_if_possible


def render_estoque_preview_step() -> None:
    st.markdown('### Preview final do estoque')
    st.caption('Confira os dados antes de baixar. O download fica na próxima etapa.')

    if not build_stock_outputs_if_possible():
        st.warning('O preview de estoque ainda não foi gerado. Volte para o mapeamento do estoque.')
        return
    render_stock_preview()


__all__ = ['render_estoque_preview_step']
