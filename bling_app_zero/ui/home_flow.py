from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.lazy_panels import normalize_panel_operation

FLOW_ORIGIN_KEY = 'home_slim_flow_origin'
FLOW_OPERATION_KEY = 'home_slim_flow_operation'
FLOW_ACTIVE_KEY = 'home_slim_active_panel'

ORIGIN_SITE = 'site'
ORIGIN_ARQUIVO = 'arquivo'

OP_CADASTRO = 'cadastro'
OP_ESTOQUE = 'estoque'

ORIGIN_LABELS = {
    ORIGIN_SITE: 'Site do fornecedor',
    ORIGIN_ARQUIVO: 'Arquivo do fornecedor',
}

OPERATION_LABELS = {
    OP_CADASTRO: 'Cadastro de produtos',
    OP_ESTOQUE: 'Atualização de estoque',
}

ORIGIN_HELP = {
    ORIGIN_SITE: 'Busca por links usando somente as colunas do modelo escolhido.',
    ORIGIN_ARQUIVO: 'Importação por planilha, PDF ou XML do fornecedor.',
}


def query_param(name: str) -> str:
    try:
        value = st.query_params.get(name, '')
        if isinstance(value, list):
            return str(value[0] if value else '')
        return str(value or '')
    except Exception:
        return ''


def _operation_from_text(value: str) -> str:
    operation = normalize_panel_operation(value)
    if operation == OP_ESTOQUE:
        return OP_ESTOQUE
    if str(value or '').lower().strip() in {'estoque_site', 'stock_site', 'atualizacao_estoque', 'atualização de estoque'}:
        return OP_ESTOQUE
    return OP_CADASTRO


def _origin_from_text(value: str) -> str:
    text = str(value or '').lower().strip()
    if text in {'planilha', 'planilhas', 'arquivo', 'arquivos', 'pdf', 'xml', 'origem_planilha'}:
        return ORIGIN_ARQUIVO
    return ORIGIN_SITE


def initial_origin_from_query() -> str:
    flow = query_param('flow').lower().strip()
    origem = query_param('origem').lower().strip()
    if origem:
        return _origin_from_text(origem)
    if flow in {'planilha', 'planilhas', 'arquivo', 'arquivos', 'pdf', 'xml', 'origem_planilha', 'cadastro'}:
        return ORIGIN_ARQUIVO
    return ORIGIN_SITE


def initial_operation_from_query() -> str:
    operation = query_param('operacao') or query_param('operation') or query_param('flow')
    return _operation_from_text(operation)


def get_current_origin() -> str:
    if FLOW_ORIGIN_KEY not in st.session_state:
        st.session_state[FLOW_ORIGIN_KEY] = initial_origin_from_query()
    current = str(st.session_state.get(FLOW_ORIGIN_KEY) or ORIGIN_SITE)
    if current not in ORIGIN_LABELS:
        current = ORIGIN_SITE
        st.session_state[FLOW_ORIGIN_KEY] = current
    return current


def get_current_operation() -> str:
    if FLOW_OPERATION_KEY not in st.session_state:
        st.session_state[FLOW_OPERATION_KEY] = initial_operation_from_query()
    current = str(st.session_state.get(FLOW_OPERATION_KEY) or OP_CADASTRO)
    if current not in OPERATION_LABELS:
        current = OP_CADASTRO
        st.session_state[FLOW_OPERATION_KEY] = current
    return current


def set_current_origin(origin: str) -> None:
    if origin not in ORIGIN_LABELS:
        origin = ORIGIN_SITE
    st.session_state[FLOW_ORIGIN_KEY] = origin
    st.session_state.pop(FLOW_ACTIVE_KEY, None)
    try:
        st.query_params['origem'] = origin
        st.query_params['flow'] = 'site' if origin == ORIGIN_SITE else 'planilha'
    except Exception:
        pass


def set_current_operation(operation: str) -> None:
    if operation not in OPERATION_LABELS:
        operation = OP_CADASTRO
    st.session_state[FLOW_OPERATION_KEY] = operation
    st.session_state['operacao_final'] = operation
    st.session_state['tipo_operacao_final'] = operation
    st.session_state.pop(FLOW_ACTIVE_KEY, None)
    try:
        st.query_params['operacao'] = operation
    except Exception:
        pass


def _active_panel_id(origin: str, operation: str) -> str:
    if origin == ORIGIN_SITE:
        return f'{operation}_site'
    return operation


def activate_current_step(origin: str | None = None) -> None:
    current_origin = origin if origin in ORIGIN_LABELS else get_current_origin()
    current_operation = get_current_operation()
    panel_id = _active_panel_id(current_origin, current_operation)
    st.session_state[FLOW_ACTIVE_KEY] = panel_id
    st.session_state[FLOW_ORIGIN_KEY] = current_origin
    st.session_state[FLOW_OPERATION_KEY] = current_operation
    st.session_state['operacao_final'] = current_operation
    st.session_state['origem_final'] = current_origin
    st.session_state['tipo_operacao_site'] = current_operation if current_origin == ORIGIN_SITE else ''


def deactivate_panel() -> None:
    st.session_state.pop(FLOW_ACTIVE_KEY, None)


def get_active_panel() -> str | None:
    active = str(st.session_state.get(FLOW_ACTIVE_KEY) or '')
    if active in {'cadastro_site', 'estoque_site', OP_CADASTRO, OP_ESTOQUE}:
        return active
    return None


def step_to_panel_operation(step: str) -> str:
    text = str(step or '').strip().lower()
    if text == 'estoque_site':
        st.session_state['tipo_operacao_site'] = OP_ESTOQUE
        return 'site'
    if text == 'cadastro_site':
        st.session_state['tipo_operacao_site'] = OP_CADASTRO
        return 'site'
    if text == OP_ESTOQUE:
        return OP_ESTOQUE
    if text == OP_CADASTRO:
        return OP_CADASTRO
    origin = get_current_origin()
    operation = get_current_operation()
    if origin == ORIGIN_SITE:
        st.session_state['tipo_operacao_site'] = operation
        return 'site'
    return operation


def _choice_button(label: str, caption: str, selected: bool, key: str) -> bool:
    prefix = '✓ ' if selected else ''
    button_label = f'{prefix}{label}\n{caption}'
    return st.button(button_label, use_container_width=True, key=key)


def _render_operation_cards(current_operation: str) -> str:
    col_a, col_b = st.columns(2)
    selected = current_operation
    with col_a:
        if _choice_button('Cadastro', 'Produtos novos no Bling', current_operation == OP_CADASTRO, 'home_pick_cadastro'):
            selected = OP_CADASTRO
    with col_b:
        if _choice_button('Estoque', 'Atualizar saldos existentes', current_operation == OP_ESTOQUE, 'home_pick_estoque'):
            selected = OP_ESTOQUE
    return selected


def _render_origin_cards(current_origin: str) -> str:
    col_a, col_b = st.columns(2)
    selected = current_origin
    with col_a:
        if _choice_button('Site', 'Buscar por links', current_origin == ORIGIN_SITE, 'home_pick_site'):
            selected = ORIGIN_SITE
    with col_b:
        if _choice_button('Arquivo', 'Planilha, PDF ou XML', current_origin == ORIGIN_ARQUIVO, 'home_pick_arquivo'):
            selected = ORIGIN_ARQUIVO
    return selected


def render_flow_selector() -> str:
    current_operation = get_current_operation()
    current_origin = get_current_origin()

    st.markdown('#### Escolha o fluxo')
    selected_operation = _render_operation_cards(current_operation)
    if selected_operation != current_operation:
        set_current_operation(selected_operation)
        current_operation = selected_operation

    st.markdown('#### Origem dos dados')
    selected_origin = _render_origin_cards(current_origin)
    if selected_origin != current_origin:
        set_current_origin(selected_origin)
        current_origin = selected_origin

    st.caption(ORIGIN_HELP.get(current_origin, ''))

    action = 'Abrir captura por site' if current_origin == ORIGIN_SITE else 'Abrir importação por arquivo'
    if st.button(action, use_container_width=True, key='home_open_selected_flow'):
        activate_current_step(current_origin)
        st.rerun()

    return _active_panel_id(current_origin, current_operation)
