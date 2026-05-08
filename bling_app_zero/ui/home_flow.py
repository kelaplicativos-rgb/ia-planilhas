from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.lazy_panels import normalize_panel_operation

FLOW_STEP_KEY = 'home_slim_flow_step'

STEP_SITE = 'site'
STEP_PLANILHA = 'planilha'
STEP_CADASTRO = 'cadastro'
STEP_ESTOQUE = 'estoque'

STEP_LABELS = {
    STEP_SITE: '1. Buscar produtos por Scraper',
    STEP_PLANILHA: '2. Origem de dados por planilhas',
    STEP_CADASTRO: 'Cadastro de Produtos',
    STEP_ESTOQUE: 'Atualização de Estoque',
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
    if flow in {'cadastro', 'produtos'}:
        return STEP_CADASTRO
    if operation == 'estoque':
        return STEP_ESTOQUE
    if flow in {'planilha', 'planilhas', 'origem_planilha'}:
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
    try:
        if step == STEP_SITE:
            st.query_params['flow'] = 'site'
        elif step == STEP_PLANILHA:
            st.query_params['flow'] = 'planilha'
        elif step == STEP_CADASTRO:
            st.query_params['flow'] = 'cadastro'
        elif step == STEP_ESTOQUE:
            st.query_params['flow'] = 'estoque'
    except Exception:
        pass


def step_to_panel_operation(step: str) -> str:
    if step == STEP_ESTOQUE:
        return 'estoque'
    if step == STEP_CADASTRO or step == STEP_PLANILHA:
        return 'cadastro'
    return 'site'


def render_flow_selector() -> str:
    current = get_current_step()
    options = [STEP_SITE, STEP_PLANILHA, STEP_CADASTRO, STEP_ESTOQUE]
    labels = [STEP_LABELS[option] for option in options]
    current_index = options.index(current) if current in options else 0

    selected_label = st.radio(
        'Fluxo principal',
        labels,
        index=current_index,
        horizontal=False,
        key='home_slim_flow_radio',
        label_visibility='collapsed',
    )
    selected_step = options[labels.index(selected_label)]
    if selected_step != current:
        set_current_step(selected_step)
        current = selected_step

    return current


def render_flow_status(step: str) -> None:
    if step == STEP_SITE:
        st.markdown(
            """
            <div class="bling-compact-note">
                <strong>Fluxo novo:</strong> primeiro gere uma planilha origem pelo Scraper dos fornecedores.
                Depois ela alimenta automaticamente a origem por planilha e segue para mapeamento, preview e CSV final.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    if step == STEP_PLANILHA:
        st.markdown(
            """
            <div class="bling-compact-note">
                <strong>Origem por planilha:</strong> use quando já tiver a planilha do fornecedor ou quando o Scraper já gerou a origem.
                Este passo mantém o fluxo normal de cadastro, calculadora, mapeamento e preview final.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    if step == STEP_ESTOQUE:
        st.markdown(
            """
            <div class="bling-compact-note">
                <strong>Motor de estoque isolado:</strong> usa o modelo de estoque e busca/preenche somente as colunas solicitadas.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        """
        <div class="bling-compact-note">
            <strong>Motor de cadastro isolado:</strong> lê origem, aplica precificação opcional, mapeia campos e gera CSV final.
        </div>
        """,
        unsafe_allow_html=True,
    )
