from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.rules_resources_tab import render_resources_tab
from bling_app_zero.ui.rules_user_tab import render_user_rules_tab


def _current_flow_step() -> str:
    return str(
        st.session_state.get('bling_wizard_step')
        or st.session_state.get('etapa_fluxo')
        or st.session_state.get('etapa')
        or 'inicio'
    ).strip().lower()


def _render_status_summary() -> None:
    step = _current_flow_step()
    st.caption(f'Etapa atual: `{step}`')
    st.caption('CSV final: separador `;`, UTF-8-SIG, imagens por `|`, GTIN invalido limpo')


def render_rules_panel() -> None:
    """Orquestra Regras e Recursos do CSV final."""
    with st.sidebar:
        with st.expander('Regras e recursos do CSV final', expanded=False):
            _render_status_summary()
            st.divider()

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
