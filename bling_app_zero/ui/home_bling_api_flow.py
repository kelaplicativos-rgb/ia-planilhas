from __future__ import annotations

import os
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
from bling_app_zero.ui.bling_backend_bridge import (
    backend_auth_url as configured_backend_auth_url,
    backend_connection_status,
    sync_backend_token_to_streamlit,
)
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
from bling_app_zero.ui.home_wizard_rerun import safe_rerun, set_step_without_rerun
from bling_app_zero.ui.home_wizard_scroll import set_scroll_target
from bling_app_zero.universal.model_contract_detector import MODEL_CONTRACT_TYPE_KEY

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_bling_api_flow.py'
PRICE_UPDATE_OPERATION = OP_ATUALIZACAO_PRECO
DIRECT_API_CONTRACT_KEY = 'direct_bling_api_contract_df'
DIRECT_API_CONTRACT_ACTIVE_KEY = 'direct_bling_api_contract_active'
DIRECT_OPERATION_APPLIED_KEY = 'direct_bling_operation_applied'
API_STOCK_DEPOSIT_KEY = 'bling_api_stock_deposit_name'
API_STOCK_DEPOSIT_ID_KEY = 'bling_api_stock_deposit_id'
API_STOCK_DEPOSIT_OPTIONS_KEY = 'bling_api_stock_deposit_options'
API_STOCK_DEPOSIT_AUTOLOAD_KEY = 'bling_api_stock_deposit_autoload_attempted'
API_STOCK_DEPOSIT_CONTEXT_KEY = 'bling_api_stock_deposit_context_operation'
API_STOCK_DEPOSIT_LAST_ERROR_KEY = 'bling_api_stock_deposit_last_error'
DEFAULT_API_BASE_URL = 'https://www.bling.com.br/Api/v3'

DIRECT_CONTRACT_SESSION_KEYS = (
    DIRECT_API_CONTRACT_KEY,
    DIRECT_OPERATION_APPLIED_KEY,
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
        if value not in (None, ''):
            return str(value).strip()
    except Exception:
        pass
    return str(os.getenv(name) or os.getenv(name.upper()) or default or '').strip()


def _api_base_url() -> str:
    return (_secret('api_base_url', DEFAULT_API_BASE_URL) or DEFAULT_API_BASE_URL).rstrip('/')


def _direct_operation() -> str:
    choice = normalize_direct_operation(st.session_state.get('direct_bling_operation_choice'))
    if choice in DIRECT_OPERATION_LABELS:
        return choice
    applied = normalize_direct_operation(st.session_state.get(DIRECT_OPERATION_APPLIED_KEY))
    if applied in DIRECT_OPERATION_LABELS:
        return applied
    return normalize_direct_operation(st.session_state.get('home_slim_flow_operation'))


def _local_token_connected() -> bool:
    token, _meta = load_token()
    return isinstance(token, dict) and bool(token.get('access_token'))


def _connected_via_backend() -> bool:
    backend_status = backend_connection_status()
    if not backend_status.get('enabled') or not backend_status.get('connected'):
        return False
    sync_backend_token_to_streamlit()
    return _local_token_connected() or bool(backend_status.get('connected'))


def is_bling_api_entry() -> bool:
    return entry_context() == CONTEXT_BLING_API


def is_api_direct_mode() -> bool:
    return finish_mode() == FINISH_MODE_API and (bool(connection_status().get('connected')) or _connected_via_backend()) and is_bling_api_entry()


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

    st.session_state[DIRECT_OPERATION_APPLIED_KEY] = op
    st.session_state[DIRECT_API_CONTRACT_ACTIVE_KEY] = True
    st.session_state[DIRECT_API_CONTRACT_KEY] = model.copy()
    st.session_state[CADASTRO_MODELO_KEY] = model.copy()
    st.session_state['cadastro_wizard_df_modelo'] = model.copy()

    # BLINGFIX: contrato direto da API não é modelo universal.
    # Antes estas chaves eram preenchidas com modelo de cadastro/estoque/preço e
    # o diagnóstico passava a enxergar um falso `df_modelo_universal`.
    for key in ('home_modelo_universal_df', 'df_modelo_universal', 'modelo_universal_df'):
        st.session_state.pop(key, None)

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


def reset_stock_deposit_cache(*, clear_selection: bool = False, reason: str = '') -> None:
    for key in (API_STOCK_DEPOSIT_OPTIONS_KEY, API_STOCK_DEPOSIT_AUTOLOAD_KEY, API_STOCK_DEPOSIT_LAST_ERROR_KEY, API_STOCK_DEPOSIT_CONTEXT_KEY):
        st.session_state.pop(key, None)
    if clear_selection:
        st.session_state.pop(API_STOCK_DEPOSIT_ID_KEY, None)
        st.session_state.pop(API_STOCK_DEPOSIT_KEY, None)
    add_audit_event(
        'bling_api_stock_deposit_cache_reset',
        area='BLING_API',
        status='OK',
        details={'clear_selection': clear_selection, 'reason': reason, 'responsible_file': RESPONSIBLE_FILE},
    )


def _deposit_paths() -> list[str]:
    configured = _secret('stock_deposits_path', '')
    paths = [configured] if configured else []
    # BLINGFIX: o diagnóstico confirmou /depositos OK e /estoques/depositos 404.
    paths.extend(['/depositos', '/estoques/depositos', '/estoque/depositos'])
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
    sync_backend_token_to_streamlit()
    token, meta = load_token()
    if not isinstance(token, dict) or not token.get('access_token'):
        error = 'Bling não conectado ou token indisponível para consultar depósitos.'
        st.session_state[API_STOCK_DEPOSIT_LAST_ERROR_KEY] = error
        add_audit_event(
            'bling_api_stock_deposits_not_loaded',
            area='BLING_API',
            status='BLOQUEADO',
            details={'reason': 'missing_access_token', 'token_meta': meta, 'responsible_file': RESPONSIBLE_FILE},
        )
        return [], error
    headers = {'Accept': 'application/json', 'Authorization': f"Bearer {token.get('access_token')}"}
    errors: list[str] = []
    for path in _deposit_paths():
        url = _deposit_url(path)
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code >= 400:
                errors.append(f'{path}: HTTP {response.status_code}')
                add_audit_event('bling_api_stock_deposits_path_failed', area='BLING_API', status='ERRO', details={'path': path, 'http_status': response.status_code, 'responsible_file': RESPONSIBLE_FILE})
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
                st.session_state.pop(API_STOCK_DEPOSIT_LAST_ERROR_KEY, None)
                add_audit_event('bling_api_stock_deposits_loaded', area='BLING_API', status='OK', details={'path': path, 'count': len(normalized), 'responsible_file': RESPONSIBLE_FILE})
                return normalized, ''
            errors.append(f'{path}: sem depósitos reconhecidos')
        except Exception as exc:
            errors.append(f'{path}: {exc}')
            add_audit_event('bling_api_stock_deposits_path_exception', area='BLING_API', status='ERRO', details={'path': path, 'error': str(exc), 'responsible_file': RESPONSIBLE_FILE})
    error = 'Não consegui buscar depósitos automaticamente. ' + ' | '.join(errors[:4])
    st.session_state[API_STOCK_DEPOSIT_LAST_ERROR_KEY] = error
    add_audit_event('bling_api_stock_deposits_not_loaded', area='BLING_API', status='ERRO', details={'errors': errors[:6], 'responsible_file': RESPONSIBLE_FILE})
    return [], error


def _ensure_stock_deposits_loaded(*, force: bool = False) -> None:
    deposits = st.session_state.get(API_STOCK_DEPOSIT_OPTIONS_KEY)
    if not force and isinstance(deposits, list) and deposits:
        return
    if not force and st.session_state.get(API_STOCK_DEPOSIT_AUTOLOAD_KEY):
        return
    st.session_state[API_STOCK_DEPOSIT_AUTOLOAD_KEY] = True
    deposits, error = _fetch_stock_deposits()
    if error:
        st.caption(error)
    elif deposits:
        st.success(f'{len(deposits)} depósito(s) encontrado(s) automaticamente.')


def _render_stock_deposit_field(operation: str) -> None:
    op = normalize_direct_operation(operation)
    if op != 'estoque':
        return
    st.markdown('##### Depósito do estoque')
    st.caption('O sistema tenta buscar automaticamente os depósitos reais do Bling. Se houver mais de um, selecione o correto.')

    if st.session_state.get(API_STOCK_DEPOSIT_CONTEXT_KEY) != op:
        reset_stock_deposit_cache(clear_selection=False, reason='operation_context_changed_to_stock')
        st.session_state[API_STOCK_DEPOSIT_CONTEXT_KEY] = op

    _ensure_stock_deposits_loaded()

    if st.button('🔄 Atualizar depósitos do Bling', use_container_width=True, key='bling_scan_stock_deposits'):
        st.session_state.pop(API_STOCK_DEPOSIT_ID_KEY, None)
        st.session_state.pop(API_STOCK_DEPOSIT_KEY, None)
        st.session_state.pop(API_STOCK_DEPOSIT_AUTOLOAD_KEY, None)
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
        selected_label = st.selectbox('Depósito do Bling', labels, index=default_index, key='bling_stock_deposit_select')
        selected = deposits[labels.index(selected_label)]
        st.session_state[API_STOCK_DEPOSIT_ID_KEY] = str(selected.get('id') or '').strip()
        st.session_state[API_STOCK_DEPOSIT_KEY] = str(selected.get('nome') or selected_label).strip()
        st.success(f'Depósito selecionado: {selected_label}')
        return

    st.warning('Nenhum depósito selecionado. Atualize os depósitos do Bling antes de enviar estoque.')


def render_new_tab_connect_button(auth_url: str) -> None:
    raw_url = str(auth_url or '').strip()
    safe_url = escape(raw_url, quote=True)
    if not raw_url:
        st.warning('Não consegui gerar o link de conexão com o Bling agora. Confira Client ID, Client Secret e Redirect URI nos secrets do Streamlit ou configure BLING_BACKEND_AUTH_URL.')
        return

    st.info('No Android, alguns navegadores internos do Streamlit bloqueiam nova aba e abrem uma tela vazia. Use a primeira opção; se falhar, use o botão de compatibilidade.')

    try:
        st.link_button('Conectar ao Bling', raw_url, use_container_width=True)
    except Exception:
        pass

    st.markdown(
        f'''
<a href="{safe_url}" target="_top" style="
    display:block;
    width:100%;
    box-sizing:border-box;
    text-align:center;
    text-decoration:none;
    font-weight:900;
    margin-top:.45rem;
    padding:0.78rem 1rem;
    border-radius:0.78rem;
    border:1px solid rgba(37,99,235,.28);
    color:#ffffff;
    background:#2563eb;
    box-shadow:0 10px 22px rgba(37,99,235,.18);
">
    Abrir conexão nesta aba se o Android bloquear
</a>
''',
        unsafe_allow_html=True,
    )

    st.caption('Depois de autorizar no Bling, o callback retorna para o app. Se voltar manualmente para esta tela, toque em verificar conexão.')
    with st.expander('Link direto de autorização', expanded=False):
        st.text_input('Copie e cole no navegador externo se a aba interna falhar', value=raw_url, key='bling_oauth_direct_url_copy')

    if st.button('Já autorizei no Bling, verificar conexão', use_container_width=True, key='bling_check_connection_after_new_tab'):
        add_audit_event('bling_api_manual_connection_check_clicked', area='BLING_API', status='OK', details={'responsible_file': RESPONSIBLE_FILE})
        safe_rerun('bling_api_manual_connection_check', target_step=STEP_ORIGEM)


def render_same_tab_connect_button(auth_url: str) -> None:
    # Compatibilidade: chamadas antigas agora usam a versão com fallback Android.
    render_new_tab_connect_button(auth_url)


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


def _activate_short_api_flow(operation: str) -> None:
    previous = normalize_direct_operation(st.session_state.get(DIRECT_OPERATION_APPLIED_KEY))
    activate_api_finish_mode()
    apply_direct_api_contract(operation)
    if not st.session_state.get(WIZARD_STEP_KEY):
        set_step_without_rerun(STEP_ORIGEM)
    if previous and previous != operation:
        set_step_without_rerun(STEP_ORIGEM)
        set_scroll_target(STEP_ORIGEM)


def render_bling_connection_step(section_title) -> None:
    section_title(1, 'Bling API')
    with st.container(border=True):
        st.caption('Fluxo curto: conecte ao Bling, carregue a origem e escolha a operação somente na etapa Operação. Não usa modelo de planilha.')
        local_status = connection_status()
        backend_status = backend_connection_status()
        connected = bool(local_status.get('connected')) or _connected_via_backend()
        callback_url = str(local_status.get('required_redirect_uri') or required_redirect_uri()).strip()

        if connected:
            activate_api_finish_mode()
            source = 'backend externo' if backend_status.get('enabled') and backend_status.get('connected') else 'Streamlit'
            st.success(f'Bling conectado via {source}.')
            st.info('A operação não é escolhida aqui para evitar conflito. Use a etapa Operação para confirmar Cadastro, Estoque por Depósito ou Preços.')
            add_audit_event('bling_api_connected_source_first_ready', area='BLING_API', status='OK', details={'source': source, 'operation_chosen_in': 'source_first_operation_gate', 'responsible_file': RESPONSIBLE_FILE})

            if st.button('Desconectar Bling', use_container_width=True, key='entry_disconnect_bling'):
                disconnect()
                clear_direct_api_contract()
                reset_stock_deposit_cache(clear_selection=True, reason='bling_disconnected')
                clear_finish_mode()
                safe_rerun('bling_api_disconnected', target_step=STEP_ORIGEM)
            return

        st.warning('Bling não conectado. Conecte para liberar o envio direto pela API.')
        auth_url = configured_backend_auth_url()
        if not auth_url:
            render_callback_hint(callback_url)
        try:
            auth_url = auth_url or build_authorization_url({'return_to': 'start', 'source_step': 'bling_connection_entry', 'open_mode': 'android_safe'})
        except Exception as exc:
            auth_url = ''
            add_audit_event('bling_api_authorization_url_error', area='BLING_API', status='ERRO', details={'error': str(exc), 'responsible_file': RESPONSIBLE_FILE})
        if configured_backend_auth_url():
            if backend_status.get('error'):
                st.warning(f'Backend Bling configurado, mas status falhou: {backend_status.get("error")}')
            else:
                st.info('Conexão do Bling será feita pelo backend externo. O Streamlit não processa o OAuth neste caminho.')
            add_audit_event('bling_api_external_backend_auth_enabled', area='BLING_API', status='OK', details={'responsible_file': RESPONSIBLE_FILE})
        render_new_tab_connect_button(auth_url)
        st.markdown('<div style="height:.55rem"></div>', unsafe_allow_html=True)
        st.caption('Sem conexão com o Bling, este caminho fica bloqueado. Para gerar arquivo manual, volte para a Home e use modelo de destino.')
        add_audit_event('bling_api_connection_required', area='BLING_API', status='AGUARDANDO_CONEXAO', details={'required_redirect_uri': callback_url, 'external_backend': bool(configured_backend_auth_url()), 'open_mode': 'android_safe', 'responsible_file': RESPONSIBLE_FILE})


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
    'reset_stock_deposit_cache',
]
