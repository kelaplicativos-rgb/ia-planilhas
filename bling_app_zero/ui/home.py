from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.clean_layout import inject_clean_home_css, render_compact_hero, render_step_title
from bling_app_zero.ui.diagnostics_panel import render_diagnostics_panel
from bling_app_zero.ui.home_flow import render_flow_selector, render_flow_status, step_to_panel_operation
from bling_app_zero.ui.lazy_panels import render_lazy_panel


def render_home() -> None:
    inject_clean_home_css()
    render_compact_hero()
    render_diagnostics_panel()

    render_step_title(
        'Arquitetura Slim Tech',
        'Primeiro busque produtos por Scraper nos fornecedores. Depois use a origem gerada como planilha e siga o fluxo normal.',
    )

    step = render_flow_selector()
    render_flow_status(step)

    operation = step_to_panel_operation(step)
    render_lazy_panel(operation)
