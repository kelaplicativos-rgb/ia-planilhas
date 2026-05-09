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
    origem = query_param('origem').lower().strip()
    flow = query_param('flow').lower().strip()
    if origem:
        return _origin_from_text(origem)
    if flow in {'planilha', 'planilhas', 'arquivo', 'arquivos', 'pdf', 'xml', 'origem_planilha'}:
        return ORIGIN_ARQUIVO
    return ORIGIN_SITE


def initial_operation_from_query() -> str:
    operation = query_param('operacao') or query_param('operation') or query_param('flow')
    return _operation_from_text(operation)


def get_current_origin() -> str:
    current = str(st.session_state.get(FLOW_ORIGIN_KEY) or initial_origin_from_query() or ORIGIN_SITE)
    if current not in {ORIGIN_SITE, ORIGIN_ARQUIVO}:
        current = ORIGIN_SITE
    st.session_state[FLOW_ORIGIN_KEY] = current
    return current


def get_current_operation() -> str:
    current = str(st.session_state.get(FLOW_OPERATION_KEY) or initial_operation_from_query() or OP_CADASTRO)
    if current not in {OP_CADASTRO, OP_ESTOQUE}:
        current = OP_CADASTRO
    st.session_state[FLOW_OPERATION_KEY] = current
    return current


def set_current_origin(origin: str) -> None:
    if origin not in {ORIGIN_SITE, ORIGIN_ARQUIVO}:
        origin = ORIGIN_SITE
    st.session_state[FLOW_ORIGIN_KEY] = origin
    st.session_state.pop(FLOW_ACTIVE_KEY, None)
    try:
        st.query_params['origem'] = origin
        st.query_params['flow'] = 'site' if origin == ORIGIN_SITE else 'planilha'
    except Exception:
        pass


def set_current_operation(operation: str) -> None:
    if operation not in {OP_CADASTRO, OP_ESTOQUE}:
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
    current_origin = origin if origin in {ORIGIN_SITE, ORIGIN_ARQUIVO} else get_current_origin()
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


def render_flow_selector() -> str:
    """Compatibilidade sem UI: nunca renderiza o seletor antigo."""
    origin = get_current_origin()
    operation = get_current_operation()
    return _active_panel_id(origin, operation)
