from __future__ import annotations

import streamlit as st

FLOW_ORIGIN_KEY = 'home_slim_flow_origin'
FLOW_OPERATION_KEY = 'home_slim_flow_operation'
FLOW_ACTIVE_KEY = 'home_slim_active_panel'

ORIGIN_SITE = 'site'
ORIGIN_ARQUIVO = 'arquivo'
OP_CADASTRO = 'cadastro'
OP_ESTOQUE = 'estoque'

_FILE_ORIGINS = {'planilha', 'planilhas', 'arquivo', 'arquivos', 'pdf', 'xml', 'origem_planilha'}
_SITE_ORIGINS = {'site', 'sites', 'link', 'links', 'url', 'urls', 'scraper', 'fornecedores'}
_STOCK_VALUES = {'estoque', 'stock', 'estoque_site', 'atualizacao_estoque', 'atualização de estoque'}
_CADASTRO_VALUES = {'cadastro', 'produto', 'produtos', 'cadastro_site', 'planilha', 'arquivo'}


def query_param(name: str) -> str:
    try:
        value = st.query_params.get(name, '')
        if isinstance(value, list):
            return str(value[0] if value else '')
        return str(value or '')
    except Exception:
        return ''


def _operation_from_text(value: str) -> str:
    text = str(value or '').lower().strip()
    if text in _STOCK_VALUES:
        return OP_ESTOQUE
    if text in _CADASTRO_VALUES:
        return OP_CADASTRO
    return OP_CADASTRO


def _origin_from_text(value: str) -> str:
    text = str(value or '').lower().strip()
    if text in _FILE_ORIGINS:
        return ORIGIN_ARQUIVO
    if text in _SITE_ORIGINS:
        return ORIGIN_SITE
    return ORIGIN_SITE


def _sync_query_params(origin: str, operation: str) -> None:
    """Corrige URL contraditoria para evitar estado misturado.

    Exemplo corrigido:
    ?flow=site&origem=arquivo&operacao=cadastro
    vira semanticamente arquivo/cadastro, pois origem e mais especifica.
    """
    try:
        st.query_params['origem'] = origin
        st.query_params['operacao'] = operation
        st.query_params['flow'] = 'site' if origin == ORIGIN_SITE else 'planilha'
    except Exception:
        pass


def initial_origin_from_query() -> str:
    origem = query_param('origem').lower().strip()
    flow = query_param('flow').lower().strip()

    if origem:
        return _origin_from_text(origem)
    if flow in _FILE_ORIGINS:
        return ORIGIN_ARQUIVO
    if flow in _SITE_ORIGINS:
        return ORIGIN_SITE
    return ORIGIN_SITE


def initial_operation_from_query() -> str:
    operation = query_param('operacao') or query_param('operation')
    if operation:
        return _operation_from_text(operation)
    flow = query_param('flow')
    if flow in {'estoque_site', 'stock', 'atualizacao_estoque', 'atualização de estoque'}:
        return OP_ESTOQUE
    return OP_CADASTRO


def get_current_origin() -> str:
    query_origin = initial_origin_from_query()
    current = str(st.session_state.get(FLOW_ORIGIN_KEY) or query_origin or ORIGIN_SITE)
    if current not in {ORIGIN_SITE, ORIGIN_ARQUIVO}:
        current = query_origin
    st.session_state[FLOW_ORIGIN_KEY] = current
    _sync_query_params(current, get_current_operation())
    return current


def get_current_operation() -> str:
    query_operation = initial_operation_from_query()
    current = str(st.session_state.get(FLOW_OPERATION_KEY) or query_operation or OP_CADASTRO)
    if current not in {OP_CADASTRO, OP_ESTOQUE}:
        current = query_operation
    st.session_state[FLOW_OPERATION_KEY] = current
    return current


def set_current_origin(origin: str) -> None:
    if origin not in {ORIGIN_SITE, ORIGIN_ARQUIVO}:
        origin = ORIGIN_SITE
    operation = get_current_operation()
    st.session_state[FLOW_ORIGIN_KEY] = origin
    st.session_state.pop(FLOW_ACTIVE_KEY, None)
    _sync_query_params(origin, operation)


def set_current_operation(operation: str) -> None:
    if operation not in {OP_CADASTRO, OP_ESTOQUE}:
        operation = OP_CADASTRO
    origin = get_current_origin()
    st.session_state[FLOW_OPERATION_KEY] = operation
    st.session_state['operacao_final'] = operation
    st.session_state['tipo_operacao_final'] = operation
    st.session_state.pop(FLOW_ACTIVE_KEY, None)
    _sync_query_params(origin, operation)


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
    _sync_query_params(current_origin, current_operation)


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
        st.session_state['origem_final'] = ORIGIN_SITE
        return 'site'
    if text == 'cadastro_site':
        st.session_state['tipo_operacao_site'] = OP_CADASTRO
        st.session_state['origem_final'] = ORIGIN_SITE
        return 'site'
    if text == OP_ESTOQUE:
        st.session_state['origem_final'] = ORIGIN_ARQUIVO
        return OP_ESTOQUE
    if text == OP_CADASTRO:
        st.session_state['origem_final'] = ORIGIN_ARQUIVO
        return OP_CADASTRO
    origin = get_current_origin()
    operation = get_current_operation()
    if origin == ORIGIN_SITE:
        st.session_state['tipo_operacao_site'] = operation
        st.session_state['origem_final'] = ORIGIN_SITE
        return 'site'
    st.session_state['origem_final'] = ORIGIN_ARQUIVO
    return operation


def render_flow_selector() -> str:
    """Compatibilidade sem UI: nunca renderiza o seletor antigo."""
    origin = get_current_origin()
    operation = get_current_operation()
    return _active_panel_id(origin, operation)
