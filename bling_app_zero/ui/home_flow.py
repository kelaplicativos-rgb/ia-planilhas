from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.lazy_panels import normalize_panel_operation

FLOW_STEP_KEY = 'home_slim_flow_step'
FLOW_ACTIVE_KEY = 'home_slim_active_panel'

STEP_SITE = 'site'
STEP_PLANILHA = 'planilha'

STEP_LABELS = {
    STEP_SITE: 'Buscar no site',
    STEP_PLANILHA: 'Enviar planilha',
}

STEP_HELP = {
    STEP_SITE: 'Busca produtos nos links e cria uma planilha.',
    STEP_PLANILHA: 'Use uma planilha pronta do fornecedor.',
}


def query_param(name: str) -> str:
    try:
        value = st.query_params.get(name, '')
        if isinstance(value, list):
            return str(value[0] if value else '')
        return str(value or '')
    except Exception:
        return ''


def initial_step_from_query() -> str:
    flow = query_param('flow').lower().strip()
    operation = normalize_panel_operation(flow)
    if operation == 'estoque':
        return STEP_PLANILHA
    if flow in {'planilha', 'planilhas', 'origem_planilha', 'cadastro', 'produtos'}:
        return STEP_PLANILHA
    return STEP_SITE


def get_current_step() -> str:
    if FLOW_STEP_KEY not in st.session_state:
        st.session_state[FLOW_STEP_KEY] = initial_step_from_query()
    current = str(st.session_state.get(FLOW_STEP_KEY) or STEP_SITE)
    if current not in STEP_LABELS:
        current = STEP_SITE
        st.session_state[FLOW_STEP_KEY] = current
    return current


def set_current_step(step: str) -> None:
    if step not in STEP_LABELS:
        step = STEP_SITE
    st.session_state[FLOW_STEP_KEY] = step
    st.session_state.pop(FLOW_ACTIVE_KEY, None)
    try:
        if step == STEP_SITE:
            st.query_params['flow'] = 'site'
        elif step == STEP_PLANILHA:
            st.query_params['flow'] = 'planilha'
    except Exception:
        pass


def activate_current_step(step: str) -> None:
    if step not in STEP_LABELS:
        step = STEP_SITE
    st.session_state[FLOW_ACTIVE_KEY] = step
    st.session_state[FLOW_STEP_KEY] = step


def deactivate_panel() -> None:
    st.session_state.pop(FLOW_ACTIVE_KEY, None)


def get_active_panel() -> str | None:
    active = st.session_state.get(FLOW_ACTIVE_KEY)
    return str(active) if active in STEP_LABELS else None


def step_to_panel_operation(step: str) -> str:
    if step == STEP_PLANILHA:
        return 'cadastro'
    return 'site'


def render_flow_selector() -> str:
    current = get_current_step()
    options = [STEP_SITE, STEP_PLANILHA]
    labels = [STEP_LABELS[option] for option in options]
    current_index = options.index(current) if current in options else 0

    selected_label = st.radio(
        'Escolha',
        labels,
        index=current_index,
        horizontal=True,
        key='home_slim_flow_radio',
        label_visibility='collapsed',
    )
    selected_step = options[labels.index(selected_label)]
    if selected_step != current:
        set_current_step(selected_step)
        current = selected_step

    st.caption(STEP_HELP.get(current, ''))

    button_label = 'Abrir busca' if current == STEP_SITE else 'Enviar planilha'
    if st.button(button_label, use_container_width=True, key='home_open_selected_flow'):
        activate_current_step(current)
        st.rerun()

    return current
