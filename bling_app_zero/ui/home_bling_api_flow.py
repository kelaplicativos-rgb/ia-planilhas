from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd
import requests
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_api_contract import (
    DIRECT_OPERATION_LABELS,
    OP_ATUALIZACAO_PRECO,
    direct_api_contract_model,
    direct_operation_options,
    normalize_direct_operation,
)
from bling_app_zero.core.bling_oauth import build_authorization_url, connection_status, disconnect, required_redirect_uri
from bling_app_zero.core.bling_token_store import load_token
from bling_app_zero.ui.cadastro_wizard_state import CADASTRO_MODELO_KEY
from bling_app_zero.ui.flow_context import (
    CONTEXT_BLING_API,
    CONTEXT_BLING_CSV,
    CONTEXT_UNIVERSAL,
    FINISH_MODE_API,
    FINISH_MODE_CSV,
    FINISH_MODE_KEY,
    HOME_ENTRY_CONTEXT_KEY,
    SKIP_DIRECT_BLING_KEY,
    activate_api_finish_mode,
    clear_finish_mode,
    entry_context,
    finish_mode,
)
from bling_app_zero.ui.home_wizard_constants import STEP_ORIGEM, WIZARD_STEP_KEY
from bling_app_zero.ui.home_wizard_scroll import set_scroll_target
from bling_app_zero.universal.model_contract_detector import MODEL_CONTRACT_TYPE_KEY

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_bling_api_flow.py'
PRICE_UPDATE_OPERATION = OP_ATUALIZACAO_PRECO
DIRECT_API_CONTRACT_KEY = 'direct_bling_api_contract_df'
DIRECT_API_CONTRACT_ACTIVE_KEY = 'direct_bling_api_contract_active'
API_STOCK_DEPOSIT_KEY = 'bling_api_stock_deposit_name'
API_STOCK_DEPOSIT_ID_KEY = 'bling_api_stock_deposit_id'
API_STOCK_DEPOSIT_OPTIONS_KEY = 'bling_api_stock_deposit_options'
DEFAULT_API_BASE_URL = 'https://www.bling.com.br/Api/v3'

DIRECT_CONTRACT_SESSION_KEYS = (
    DIRECT_API_CONTRACT_KEY,
    'home_modelo_universal_df',
    'df_modelo_universal',
    'modelo_universal_df',
    'cadastro_wizard_df_modelo',
    'home_modelo_cadastro_df',
    'df_modelo_cadastro',
    'modelo_cadastro_df',
    'home_modelo_estoque_df',
    'df_modelo_estoque',
    'modelo_estoque_df',
    'cadastro_wizard_df_modelo_estoque',
    'home_modelo_atualizacao_preco_df',
    'df_modelo_atualizacao_preco',
    'modelo_atualizacao_preco_df',
)


def _secret(name: str, default: str = '') -> str:
    try:
        bling = st.secrets.get('bling', {})
        value = bling.get(name, default) if hasattr(bling, 'get') else default
        return str(value or default).strip()
    except Exception:
        return default


def _api_base_url() -> str:
    return (_secret('api_base_url', DEFAULT_API_BASE_URL) or DEFAULT_API_BASE_URL).rstrip('/')


def _direct_operation() -> str:
    choice = normalize_direct_operation(st.session_state.get('direct_bling_operation_choice'))
    if choice in DIRECT_OPERATION_LABELS:
        return choice
    return normalize_direct_operation(st.session_state.get('home_slim_flow_operation'))


def is_bling_api_entry() -> bool:
    return entry_context() == CONTEXT_BLING_API


def is_api_direct_mode() -> bool:
    return finish_mode() == FINISH_MODE_API and bool(connection_status().get('connected')) and is_bling_api_entry()


def clear_direct_api_contract() -> None:
    if not st.session_state.get(DIRECT_API_CONTRACT_ACTIVE_KEY):
        return
    for key in DIRECT_CONTRACT_SESSION_KEYS:
        st.session_state.pop(key, None)
    st.session_state.pop(DIRECT_API_CONTRACT_ACTIVE_KEY, None)
    st.session_state.pop(MODEL_CONTRACT_TYPE_KEY, None)


def apply_direct_api_contract(operation: str | None = None) -> pd.DataFrame:
    op = normalize_direct_operation(operation or _direct_operation())
    model = direct_api_contract_model(op)
    st.session_state[DIRECT_API_CONTRACT_ACTIVE_KEY] = True
    st.session_state[DIRECT_API_CONTRACT_KEY] = model.copy()
    st.session_state[CADASTRO_MODELO_KEY] = model.copy()
    st.session_state['cadastro_wizard_df_modelo'] = model.copy()
    st.session_state['home_modelo_universal_df'] = model.copy()
    st.session_state['df_modelo_universal'] = model.copy()
    st.session_state['modelo_universal_df'] = model.copy()

    if op == 'cadastro':
        st.session_state['home_modelo_cadastro_df'] = model.copy()
        st.session_state['df_modelo_cadastro'] = model.copy()
        st.session_state['modelo_cadastro_df'] = model.copy()
    elif op == 'estoque':
        st.session_state['home_modelo_estoque_df'] = model.copy()
        st.session_state['df_modelo_estoque'] = model.copy()
        st.session_state['modelo_estoque_df'] = model.copy()
        st.session_state['cadastro_wizard_df_modelo_estoque'] = model.copy()
    elif op == PRICE_UPDATE_OPERATION:
        st.session_state['home_modelo_atualizacao_preco_df'] = model.copy()
        st.session_state['df_modelo_atualizacao_preco'] = model.copy()
        st.session_state['modelo_atualizacao_preco_df'] = model.copy()

    st.session_state['home_slim_flow_operation'] = op
    st.session_state['home_detected_operation'] = op
    st.session_state['operacao_final'] = op
    st.session_state['tipo_operacao_final'] = op
    st.session_state[MODEL_CONTRACT_TYPE_KEY] = op
    return model


def _deposit_paths() -> list[str]:
    configured = _secret('stock_deposits_path', '')
    paths = [configured] if configured else []
    paths.extend(['/estoques/depositos', '/depositos', '/estoque/depositos'])
    out: list[str] = []
    for path in paths:
        value = str(path or '').strip()
        if value and value not in out:
            out.append(value)
    return out


def _deposit_url(path: str) -> str:
    if path.startswith('http://') or path.startswith('https://'):
        return path
    return _api_base_url() + '/' + path.lstrip('/')


def _extract_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ('data', 'dados', 'items', 'result', 'results'):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _extract_items(value)
            if nested:
                return nested
    return []


def _normalize_deposit(item: dict[str, Any]) -> dict[str, str] | None:
    deposit_id = str(item.get('id') or item.get('idDeposito') or item.get('id_deposito') or item.get('codigo') or '').strip()
    name = str(item.get('descricao') or item.get('nome') or item.get('name') or item.get('description') or '').strip()
    nested = item.get('deposito')
    if isinstance(nested, dict):
        deposit_id = deposit_id or str(nested.get('id') or nested.get('idDeposito') or '').strip()
        name = name or str(nested.get('descricao') or nested.get('nome') or '').strip()
    if not deposit_id and not name:
        return None
    label = f'{name} · ID {deposit_id}' if name and deposit_id else name or f'ID {deposit_id}'
    return {'id': deposit_id, 'nome': name, 'label': label}


def _fetch_stock_deposits() -> tuple[list[dict[str, str]], str]:
    token, _meta = load_token()
    if not isinstance(token, dict) or not token.get('access_token'):
        return [], 'Bling não conectado.'
    headers = {'Accept': 'application/json', 'Authorization': f"Bearer {token.get('access_token')}"}
    errors: list[str] = []
    for path in _deposit_paths():
        try:
            response = requests.get(_deposit_url(path), headers=headers, timeout=30)
            if response.status_code >= 400:
                errors.append(f'{path}: HTTP {response.status_code}')
                continue
            normalized: list[dict[str, str]] = []
            seen: set[tuple[str, str]] = set()
            for item in _extract_items(response.json()):
                deposit = _normalize_deposit(item)
                if not deposit:
                    continue
                key = (deposit.get('id', ''), deposit.get('nome', ''))
                if key in seen:
                    continue
                seen.add(key)
                normalized.append(deposit)
            if normalized:
                st.session_state[API_STOCK_DEPOSIT_OPTIONS_KEY] = normalized
                add_audit_event('bling_api_stock_deposits_loaded', area='BLING_API', status='OK', details={'path': path, 'count': len(normalized), 'responsible_file': RESPONSIBLE_FILE})
                return normalized, ''
            errors.append(f'{path}: sem depósitos reconhecidos')
        except Exception as exc:
            errors.append(f'{path}: {exc}')
    return [], 'Não consegui buscar depósitos automaticamente. ' + ' | '.join(errors[:4])


def _render_stock_deposit_field(operation: str) -> None:
    op = normalize_direct_operation(operation)
    if op != 'estoque':
        return
    st.markdown('##### Depósito do estoque')
    st.caption('Use somente depósitos reais retornados pela API do Bling. O campo manual foi removido para evitar erro de envio.')

    if st.button('🔎 Buscar depósitos do Bling', use_container_width=True, key='bling_scan_stock_deposits'):
        st.session_state.pop(API_STOCK_DEPOSIT_ID_KEY, None)
        st.session_state.pop(API_STOCK_DEPOSIT_KEY, None)
        deposits, error = _fetch_stock_deposits()
        if error:
            st.warning(error)
        elif deposits:
            st.success(f'{len(deposits)} depósito(s) encontrado(s).')

    deposits = st.session_state.get(API_STOCK_DEPOSIT_OPTIONS_KEY)
    if isinstance(deposits, list) and deposits:
        labels = [str(item.get('label') or item.get('nome') or item.get('id') or '') for item in deposits]
        current_id = str(st.session_state.get(API_STOCK_DEPOSIT_ID_KEY) or '').strip()
        default_index = 0
        for index, item in enumerate(deposits):
            if current_id and str(item.get('id') or '').strip() == current_id:
                default_index = index
                break
        selected_label = st.selectbox('Selecione o depósito do Bling', labels, index=default_index, key='bling_stock_deposit_select')
        selected = deposits[labels.index(selected_label)]
        st.session_state[API_STOCK_DEPOSIT_ID_KEY] = str(selected.get('id') or '').strip()
        st.session_state[API_STOCK_DEPOSIT_KEY] = str(selected.get('nome') or selected_label).strip()
        st.success(f'Depósito selecionado: {selected_label}')
        return

    st.warning('Nenhum depósito selecionado. Clique em “Buscar depósitos do Bling” e selecione um depósito real antes de continuar.')


def render_same_tab_connect_button(auth_url: str) -> None:
    safe_url = escape(str(auth_url or ''), quote=True)
    if not safe_url:
        st.warning('Não consegui gerar o link de conexão com o Bling agora. Confira Client ID, Client Secret e Redirect URI nos secrets do Streamlit.')
        return
    st.markdown(
        f'''
<a href="{safe_url}" target="_self" style="
    display:block;
    width:100%;
    box-sizing:border-box;
    text-align:center;
    text-decoration:none;
    font-weight:900;
    padding:0.78rem 1rem;
    border-radius:0.78rem;
    border:1px solid rgba(37,99,235,.28);
    color:#ffffff;
    background:#2563eb;
    box-shadow:0 10px 22px rgba(37,99,235,.18);
">
    Conectar ao Bling
</a>
''',
        unsafe_allow_html=True,
    )


def render_callback_hint(callback_url: str) -> None:
    safe_callback = escape(str(callback_url or '').strip())
    if not safe_callback:
        return
    st.markdown(
        f'''
<div style="
    margin:.75rem 0 0 0;
    padding:.78rem .9rem;
    border-radius:.8rem;
    border:1px solid rgba(234,88,12,.30);
    background:rgba(255,237,213,.82);
    color:#7c2d12;
    font-weight:650;
    line-height:1.35;
">
    Callback URL obrigatório no app v3 do Bling:<br>
    <code style="word-break:break-all;color:#7c2d12;background:rgba(255,255,255,.55);padding:.12rem .25rem;border-radius:.35rem;">{safe_callback}</code>
</div>
''',
        unsafe_allow_html=True,
    )


def render_bling_connection_step(section_title) -> None:
    section_title(1, 'Bling API')
    with st.container(border=True):
        st.caption('Conecte ao Bling para enviar cadastro, estoque ou preços direto pela API. Este caminho não usa modelo de planilha nem gera CSV Bling.')
        status = connection_status()
        connected = bool(status.get('connected'))
        callback_url = str(status.get('required_redirect_uri') or required_redirect_uri()).strip()

        if connected:
            st.success('Bling conectado. Escolha o tipo de envio direto.')
            operation = st.radio(
                'O que deseja fazer no Bling?',
                options=direct_operation_options(),
                format_func=lambda value: DIRECT_OPERATION_LABELS.get(value, value),
                horizontal=True,
                key='direct_bling_operation_choice',
            )
            _render_stock_deposit_field(operation)
            if finish_mode() == FINISH_MODE_API:
                apply_direct_api_contract(operation)

            if st.button('Usar envio direto pela API', use_container_width=True, key='use_direct_bling_mode'):
                activate_api_finish_mode()
                apply_direct_api_contract(operation)
                st.session_state[WIZARD_STEP_KEY] = STEP_ORIGEM
                set_scroll_target(STEP_ORIGEM)
                st.rerun()

            st.caption('Para gerar arquivo manual, volte para a Home e use modelo de destino.')
            if st.button('Desconectar Bling', use_container_width=True, key='entry_disconnect_bling'):
                disconnect()
                clear_direct_api_contract()
                clear_finish_mode()
                st.rerun()
            return

        st.warning('Bling não conectado. Conecte para liberar o envio direto pela API.')
        render_callback_hint(callback_url)
        try:
            auth_url = build_authorization_url({'return_to': 'start', 'source_step': 'bling_connection_entry'})
        except Exception as exc:
            auth_url = ''
            add_audit_event('bling_api_authorization_url_error', area='BLING_API', status='ERRO', details={'error': str(exc), 'responsible_file': RESPONSIBLE_FILE})
        render_same_tab_connect_button(auth_url)
        st.markdown('<div style="height:.55rem"></div>', unsafe_allow_html=True)
        st.caption('Sem conexão com o Bling, este caminho fica bloqueado. Para gerar arquivo manual, volte para a Home e use modelo de destino.')
        add_audit_event('bling_api_connection_required', area='BLING_API', status='AGUARDANDO_CONEXAO', details={'required_redirect_uri': callback_url, 'responsible_file': RESPONSIBLE_FILE})


__all__ = [
    'CONTEXT_BLING_API',
    'CONTEXT_BLING_CSV',
    'CONTEXT_UNIVERSAL',
    'FINISH_MODE_API',
    'FINISH_MODE_CSV',
    'FINISH_MODE_KEY',
    'HOME_ENTRY_CONTEXT_KEY',
    'PRICE_UPDATE_OPERATION',
    'SKIP_DIRECT_BLING_KEY',
    'apply_direct_api_contract',
    'clear_direct_api_contract',
    'is_api_direct_mode',
    'is_bling_api_entry',
    'render_bling_connection_step',
]
