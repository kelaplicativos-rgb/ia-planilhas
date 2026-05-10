from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.rules_resources_tab import render_resources_tab
from bling_app_zero.ui.rules_user_tab import render_user_rules_tab
from bling_app_zero.ui.sidebar_skin import sidebar_header


def render_rules_panel() -> None:
    """Orquestra Regras e Recursos do CSV final com sidebar padronizada."""
    with st.sidebar:
        with st.expander('⚙️ Regras e recursos', expanded=False):
            sidebar_header(
                'CSV final padronizado',
                'Controle os preenchimentos, tratamentos automáticos e regras personalizadas sem alterar o fluxo principal.',
            )
            section = st.radio(
                'Área',
                ['Regras', 'Recursos'],
                horizontal=True,
                label_visibility='collapsed',
                key='rules_panel_section_selector',
            )

            if section == 'Recursos':
                render_resources_tab()
            else:
                render_user_rules_tab()
