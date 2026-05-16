from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.cadastro_wizard_state import BLING_IMPORTADOR_PRODUTOS_URL
from bling_app_zero.ui.estoque_wizard_state import BLING_IMPORTADOR_ESTOQUE_URL

BLING_LINKS = [
    ('🧾 Importador de produtos no Bling', BLING_IMPORTADOR_PRODUTOS_URL),
    ('📦 Importador de estoque no Bling', BLING_IMPORTADOR_ESTOQUE_URL),
]


def render_bling_links_panel() -> None:
    st.markdown('#### Próximo passo no Bling')
    st.caption('Como o modelo anexado pode variar, deixamos os principais caminhos do Bling disponíveis na tela final.')
    for label, url in BLING_LINKS:
        st.link_button(label, url, use_container_width=True)


__all__ = ['BLING_LINKS', 'render_bling_links_panel']
