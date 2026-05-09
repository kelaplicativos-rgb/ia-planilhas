from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.clean_layout import inject_clean_home_css, render_compact_hero, render_step_title
from bling_app_zero.ui.diagnostics_panel import render_diagnostics_panel
from bling_app_zero.ui.home_flow import deactivate_panel, get_active_panel, render_flow_selector, step_to_panel_operation
from bling_app_zero.ui.home_models import has_home_models, render_home_bling_models
from bling_app_zero.ui.lazy_panels import render_lazy_panel

HOME_STAGE_KEY = 'home_stage'
STAGE_START = 'inicio'
STAGE_MODELOS = 'modelos'
STAGE_ORIGEM = 'origem'


def _current_home_stage() -> str:
    stage = str(st.session_state.get(HOME_STAGE_KEY) or '')
    if stage in {STAGE_START, STAGE_MODELOS, STAGE_ORIGEM}:
        return stage
    if has_home_models():
        return STAGE_ORIGEM
    return STAGE_START


def _set_home_stage(stage: str) -> None:
    if stage not in {STAGE_START, STAGE_MODELOS, STAGE_ORIGEM}:
        stage = STAGE_START
    st.session_state[HOME_STAGE_KEY] = stage


def _inject_compact_middle_selector_css() -> None:
    st.markdown(
        """
        <style>
        div[data-testid="stRadio"] {
            margin-bottom: 0.08rem !important;
        }
        div[data-testid="stRadio"] > label {
            display: none !important;
        }
        div[data-testid="stRadio"] div[role="radiogroup"] {
            gap: 0.22rem !important;
            margin-bottom: 0.04rem !important;
        }
        div[data-testid="stRadio"] div[role="radiogroup"] label {
            min-height: 34px !important;
            padding: 5px 8px !important;
            margin-bottom: 2px !important;
            border-radius: 10px !important;
            background: rgba(240, 242, 246, 0.62) !important;
        }
        div[data-testid="stRadio"] div[role="radiogroup"] label p,
        div[data-testid="stRadio"] div[role="radiogroup"] label span,
        div[data-testid="stRadio"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
            font-size: 0.84rem !important;
            line-height: 1.12 !important;
            margin: 0 !important;
        }
        div[data-testid="stRadio"] + div,
        div[data-testid="stRadio"] + div[data-testid="stElementContainer"] {
            margin-top: 0 !important;
            padding-top: 0 !important;
        }
        div[data-testid="stExpander"] {
            margin-top: 0.12rem !important;
        }
        div[data-testid="stExpander"] details summary {
            padding-top: 0.38rem !important;
            padding-bottom: 0.38rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_home_start() -> None:
    render_step_title(
        'Comece pelos modelos do Bling',
        'Anexe os modelos uma vez. Depois eles serão usados nos fluxos de site, planilha, PDF, XML, cadastro e estoque.',
    )
    if st.button('Anexar modelos do Bling', use_container_width=True, key='home_start_open_models'):
        _set_home_stage(STAGE_MODELOS)
        st.rerun()


def _render_home_models_step() -> None:
    render_step_title(
        'Modelos do Bling',
        'Anexe o modelo de cadastro, o modelo de estoque ou os dois.',
    )
    render_home_bling_models()

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button('← Voltar', use_container_width=True, key='home_models_back'):
            _set_home_stage(STAGE_START)
            st.rerun()
    with col_b:
        disabled = not has_home_models()
        if st.button('Continuar', use_container_width=True, disabled=disabled, key='home_models_continue'):
            _set_home_stage(STAGE_ORIGEM)
            st.rerun()

    if not has_home_models():
        st.info('Anexe pelo menos um modelo para continuar.')


def _render_home_origin_step() -> None:
    render_step_title(
        'O que você quer fazer?',
        'Escolha a origem dos produtos. Os modelos anexados serão reutilizados nos próximos passos.',
    )
    _inject_compact_middle_selector_css()
    render_flow_selector()

    if st.button('Trocar modelos do Bling', use_container_width=True, key='home_origin_change_models'):
        _set_home_stage(STAGE_MODELOS)
        st.rerun()


def _render_home_intro() -> None:
    stage = _current_home_stage()
    if stage == STAGE_MODELOS:
        _render_home_models_step()
        return
    if stage == STAGE_ORIGEM:
        _render_home_origin_step()
        return
    _render_home_start()


def _render_back_home() -> None:
    if st.button('← Início', use_container_width=True, key='home_back_to_light_start'):
        deactivate_panel()
        _set_home_stage(STAGE_ORIGEM if has_home_models() else STAGE_START)
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
