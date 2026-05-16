from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.bling_links_panel import render_bling_links_panel
from bling_app_zero.ui.estoque_outputs import render_stock_downloads
from bling_app_zero.ui.estoque_wizard_state import build_stock_outputs_if_possible


def render_estoque_download_step() -> None:
    st.markdown('### Download do estoque')
    st.caption('Última etapa: baixe somente o CSV final de atualização de estoque.')

    if not build_stock_outputs_if_possible():
        st.warning('Ainda não há CSV de estoque. Volte para o mapeamento do estoque.')
        return
    render_stock_downloads()
    render_bling_links_panel()


__all__ = ['render_estoque_download_step']
