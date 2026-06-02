from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.estoque_outputs import render_stock_preview
from bling_app_zero.ui.estoque_wizard_state import build_stock_outputs_if_possible
from bling_app_zero.ui.flow_guard import render_flow_blocker


def render_estoque_preview_step() -> None:
    st.markdown('### Preview final do estoque')
    st.caption('Confira os dados antes de baixar. O download fica na próxima etapa.')

    if not build_stock_outputs_if_possible():
        render_flow_blocker(
            'O preview de estoque ainda não foi gerado. Volte para o mapeamento do estoque e confirme a origem, quantidade e depósito.',
            title='Preview de estoque bloqueado',
            action_label='Continuar',
        )
        return
    render_stock_preview()


__all__ = ['render_estoque_preview_step']
