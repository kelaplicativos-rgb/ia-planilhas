from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.estoque_outputs import render_stock_downloads
from bling_app_zero.ui.estoque_wizard_state import BLING_IMPORTADOR_ESTOQUE_URL, build_stock_outputs_if_possible


def render_estoque_download_step() -> None:
    st.markdown('### Download do estoque')
    st.caption('Última etapa: baixe somente o CSV final de atualização de estoque.')

    if not build_stock_outputs_if_possible():
        st.warning('Ainda não há CSV de estoque. Volte para o mapeamento do estoque.')
        return
    render_stock_downloads()

    st.markdown('#### Próximo passo no Bling')
    st.caption('Depois de baixar o CSV, abra direto o importador de saldos de estoque do Bling e envie o arquivo gerado.')
    st.link_button(
        '🔗 Abrir importador de estoque no Bling',
        BLING_IMPORTADOR_ESTOQUE_URL,
        use_container_width=True,
    )


__all__ = ['render_estoque_download_step']
