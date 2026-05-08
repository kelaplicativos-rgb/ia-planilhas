from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.clean_layout import inject_clean_home_css, render_compact_hero, render_step_title
from bling_app_zero.ui.diagnostics_panel import render_diagnostics_panel
from bling_app_zero.ui.home_flow import deactivate_panel, get_active_panel, render_flow_selector, step_to_panel_operation
from bling_app_zero.ui.home_models import render_home_bling_models
from bling_app_zero.ui.lazy_panels import render_lazy_panel


def _render_home_intro() -> None:
    render_step_title(
        'O que você quer fazer?',
        'Escolha o fluxo. Os modelos do Bling ficam salvos uma vez e são reutilizados nos próximos passos.',
    )
    render_flow_selector()
    render_home_bling_models()


def _render_back_home() -> None:
    if st.button('← Início', use_container_width=True, key='home_back_to_light_start'):
        deactivate_panel()
        st.rerun()


def render_home() -> None:
    inject_clean_home_css()
    render_compact_hero()
    render_diagnostics_panel()

    active_panel = get_active_panel()
    if not active_panel:
        _render_home_intro()
        return

    _render_back_home()
    render_lazy_panel(step_to_panel_operation(active_panel))
