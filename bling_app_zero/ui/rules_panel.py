from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.rules_resources_tab import render_resources_tab
from bling_app_zero.ui.rules_user_tab import render_user_rules_tab


def render_rules_panel() -> None:
    """Orquestra Regras e Recursos do CSV final sem duplicar textos."""
    with st.sidebar:
        with st.expander('Regras e recursos do CSV final', expanded=False):
            section = st.radio(
                'Area',
                ['Regras', 'Recursos'],
                horizontal=True,
                label_visibility='collapsed',
                key='rules_panel_section_selector',
            )

            if section == 'Recursos':
                render_resources_tab()
            else:
                render_user_rules_tab()
