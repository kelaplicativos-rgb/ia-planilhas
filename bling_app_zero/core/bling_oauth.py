from __future__ import annotations

import base64
import json
import secrets
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import requests
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_token_store import clear_token, get_user_session_id, load_token, save_token
from bling_app_zero.core.oauth_return_snapshot import restore_download_oauth_return

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_oauth.py'
AUTH_URL_DEFAULT = 'https://www.bling.com.br/Api/v3/oauth/authorize'
TOKEN_URL_DEFAULT = 'https://www.bling.com.br/Api/v3/oauth/token'
PUBLIC_REDIRECT_URI_DEFAULT = 'https://ia-planilhas-bling.streamlit.app/'
CLIENT_ID_DEFAULT = ''
LEGACY_REDIRECT_URI_VALUES = {
    'https://ia-planilhas.streamlit.app',
    'https://ia-planilhas.streamlit.app/',
}

TOKEN_STATE_KEY = 'bling_oauth_token_response'
TOKEN_CONNECTED_AT_KEY = 'bling_oauth_connected_at'
LAST_ERROR_KEY = 'bling_oauth_last_error'
EXPECTED_STATE_KEY = 'bling_oauth_expected_state'
CALLBACK_DONE_KEY = 'bling_oauth_callback_done_for_code'
RETURN_CONTEXT_KEY = 'bling_oauth_return_context'
RESTORED_AFTER_CALLBACK_KEY = 'bling_oauth_restored_after_callback'
STATE_SOURCE = 'ia_planilhas_bling'
CONTEXT_BLING_API = 'bling_api'


def _secret(name: str, default: str = '') -> str:
    try:
        bling = st.secrets.get('bling', {})
        value = bling.get(name, default) if hasattr(bling, 'get') else default
        return str(value or default).strip()
    except Exception:
        return default


def _normalize_redirect_uri(value: str) -> str:
    configured = str(value or '').strip()
    if not configured:
        return PUBLIC_REDIRECT_URI_DEFAULT

    if configured.rstrip('/') in {item.rstrip('/') for item in LEGACY_REDIRECT_URI_VALUES}:
        add_audit_event(
            'bling_oauth_legacy_redirect_uri_overridden',
            area='BLING_OAUTH',
            status='CORRIGIDO',
            details={
                'configured_redirect_uri': configured,
                'forced_redirect_uri': PUBLIC_REDIRECT_URI_DEFAULT,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return PUBLIC_REDIRECT_URI_DEFAULT

    return configured


def client_id() -> str:
    return _secret('client_id', CLIENT_ID_DEFAULT)


def client_secret() -> str:
    return _secret('client_secret', '')


def redirect_uri() -> str:
    return _normalize_redirect_uri(_secret('redirect_uri', ''))


def authorize_url() -> str:
    return _secret('authorize_url', AUTH_URL_DEFAULT)


def token_url() -> str:
    return _secret('token_url', TOKEN_URL_DEFAULT)


def _encode_state_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')


def _decode_state_payload(state: str) -> dict[str, Any]:
    if not state:
        return {}
    try:
        padded = state + '=' * (-len(state) % 4)
        raw = base64.urlsafe_b64decode(padded.encode('ascii'))
        data = json.loads(raw.decode('utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _new_state(extra_context: dict[str, Any] | None = None) -> str:
    payload: dict[str, Any] = {
        'nonce': secrets.token_urlsafe(24),
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'source': STATE_SOURCE,
        'session_id': get_user_session_id(),
    }
    if isinstance(extra_context, dict):
        payload.update({k: v for k, v in extra_context.items() if isinstance(k, str)})
    return _encode_state_payload(payload)


def build_authorization_url(extra_context: dict[str, Any] | None = None) -> str:
    cid = client_id()
    if not cid:
        return ''
    state = _new_state(extra_context)
    st.session_state[EXPECTED_STATE_KEY] = state
    if isinstance(extra_context, dict):
        st.session_state[RETURN_CONTEXT_KEY] = dict(extra_context)
    params = {
        'response_type': 'code',
        'client_id': cid,
        'redirect_uri': redirect_uri(),
        'state': state,
    }
    return f'{authorize_url()}?{urlencode(params)}'


def required_redirect_uri() -> str:
    return redirect_uri()


def is_connected() -> bool:
    try:
        token, _meta = load_token()
        return isinstance(token, dict) and bool(token.get('access_token'))
    except Exception:
        return False


def connection_status() -> dict[str, Any]:
    try:
        token, meta = load_token()
    except Exception as exc:
        return {'connected': False, 'message': 'Bling não conectado.', 'error': str(exc)}
    if not isinstance(token, dict):
        return {'connected': False, 'message': 'Bling não conectado.', **meta}
    return {
        'connected': bool(token.get('access_token')),
        'connected_at': meta.get('connected_at', ''),
        'expires_at': meta.get('expires_at', ''),
        'expires_in': token.get('expires_in'),
        'store_mode': meta.get('store_mode', ''),
        'user_session_id': meta.get('user_session_id', ''),
        'message': 'Bling conectado.' if token.get('access_token') else 'Bling não conectado.',
    }


def _query_param(name: str) -> str:
    try:
        value = st.query_params.get(name)
    except Exception:
        return ''
    if isinstance(value, list):
        return str(value[0] if value else '').strip()
    return str(value or '').strip()


def _basic_auth_header(cid: str, secret: str) -> str:
    raw = f'{cid}:{secret}'.encode('utf-8')
    return 'Basic ' + base64.b64encode(raw).decode('ascii')


def exchange_code_for_token(code: str) -> tuple[bool, str]:
    cid = client_id()
    secret = client_secret()
    uri = redirect_uri()
    if not cid:
        return False, 'Client ID do Bling não configurado nos secrets do app.'
    if not secret:
        return False, 'Client Secret do Bling ainda não está configurado nos secrets do app.'

    payload: dict[str, str] = {'grant_type': 'authorization_code', 'code': code, 'redirect_uri': uri}

    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': _basic_auth_header(cid, secret),
    }

    try:
        response = requests.post(token_url(), data=payload, headers=headers, timeout=30)
        if response.status_code >= 400:
            text = response.text[:500]
            st.session_state[LAST_ERROR_KEY] = text
            add_audit_event(
                'bling_oauth_token_error',
                area='BLING_OAUTH',
                status='ERRO',
                details={'status_code': response.status_code, 'response_preview': text, 'redirect_uri': uri, 'responsible_file': RESPONSIBLE_FILE},
            )
            return False, f'Falha ao conectar ao Bling. Status {response.status_code}.'
        data = response.json()
        save_token(data)
        st.session_state.pop(LAST_ERROR_KEY, None)
        add_audit_event(
            'bling_oauth_connected',
            area='BLING_OAUTH',
            status='OK',
            details={'expires_in': data.get('expires_in'), 'user_session_id': get_user_session_id(), 'redirect_uri': uri, 'responsible_file': RESPONSIBLE_FILE},
        )
        return True, 'Bling conectado com sucesso.'
    except Exception as exc:
        st.session_state[LAST_ERROR_KEY] = str(exc)
        add_audit_event(
            'bling_oauth_exception',
            area='BLING_OAUTH',
            status='ERRO',
            details={'error': str(exc), 'redirect_uri': uri, 'responsible_file': RESPONSIBLE_FILE},
        )
        return False, f'Falha ao conectar ao Bling: {exc}'


def _state_is_trusted(state: str, expected: str, payload: dict[str, Any]) -> bool:
    if expected and state and state == expected:
        return True
    if payload.get('source') == STATE_SOURCE and payload.get('session_id'):
        return True
    return not expected


def _clear_legacy_query_params() -> None:
    for key in ('operation', 'flow', 'origem', 'operacao'):
        try:
            st.query_params.pop(key, None)
        except Exception:
            pass


def _clear_non_api_flow_state() -> None:
    st.session_state.pop('bling_finish_mode', None)
    st.session_state.pop('skip_direct_bling_connection_this_flow', None)
    for key in ('home_modelo_universal_df', 'df_modelo_universal', 'modelo_universal_df'):
        st.session_state.pop(key, None)


def _force_start_query_params() -> None:
    try:
        st.query_params['operation_v2'] = 'wizard_cadastro_estoque'
        st.query_params.pop('step', None)
        _clear_legacy_query_params()
    except Exception:
        pass


def _force_download_query_params() -> None:
    try:
        st.query_params['operation_v2'] = 'wizard_cadastro_estoque'
        st.query_params['step'] = 'download'
        _clear_legacy_query_params()
    except Exception:
        pass


def _restore_oauth_return_context(state_payload: dict[str, Any]) -> None:
    return_to = str(state_payload.get('return_to') or '').strip().lower()
    session_id = str(state_payload.get('session_id') or get_user_session_id()).strip()

    # Impede o boot lock da Home de apagar o retorno do OAuth no primeiro render após conectar.
    st.session_state['home_boot_landing_rendered_once'] = True
    st.session_state['home_active_operation_v2'] = 'wizard_cadastro_estoque'
    st.session_state['home_allow_operation_v2_session'] = True
    st.session_state['home_single_page_flow_active'] = True
    st.session_state['home_entry_context'] = CONTEXT_BLING_API

    if return_to == 'download':
        restored = restore_download_oauth_return(session_id)
        st.session_state[RESTORED_AFTER_CALLBACK_KEY] = bool(restored)
        st.session_state['bling_wizard_step'] = 'download'
        _force_download_query_params()
        return

    _clear_non_api_flow_state()
    st.session_state.pop('bling_wizard_step', None)
    _force_start_query_params()


def process_oauth_callback() -> None:
    code = _query_param('code')
    if not code:
        _clear_legacy_query_params()
        return
    if st.session_state.get(CALLBACK_DONE_KEY) == code:
        _clear_legacy_query_params()
        return

    state = _query_param('state')
    expected = str(st.session_state.get(EXPECTED_STATE_KEY) or '')
    state_payload = _decode_state_payload(state)
    if not _state_is_trusted(state, expected, state_payload):
        st.session_state[LAST_ERROR_KEY] = 'Retorno OAuth com state inválido.'
        add_audit_event(
            'bling_oauth_state_invalid',
            area='BLING_OAUTH',
            status='ERRO',
            details={'has_expected': bool(expected), 'has_state': bool(state), 'decoded': bool(state_payload), 'responsible_file': RESPONSIBLE_FILE},
        )
        _clear_legacy_query_params()
        return

    ok, message = exchange_code_for_token(code)
    st.session_state[CALLBACK_DONE_KEY] = code
    if ok:
        _restore_oauth_return_context(state_payload)
        st.success(message)
        try:
            st.query_params.pop('code', None)
            st.query_params.pop('state', None)
            _restore_oauth_return_context(state_payload)
        except Exception:
            pass
    else:
        st.warning(message)
        _clear_legacy_query_params()


def disconnect() -> None:
    clear_token()
    for key in (TOKEN_STATE_KEY, TOKEN_CONNECTED_AT_KEY, LAST_ERROR_KEY, EXPECTED_STATE_KEY, CALLBACK_DONE_KEY, RETURN_CONTEXT_KEY, RESTORED_AFTER_CALLBACK_KEY):
        st.session_state.pop(key, None)
    add_audit_event('bling_oauth_disconnected', area='BLING_OAUTH', status='OK', details={'user_session_id': get_user_session_id(), 'responsible_file': RESPONSIBLE_FILE})


__all__ = ['build_authorization_url', 'connection_status', 'disconnect', 'is_connected', 'process_oauth_callback', 'required_redirect_uri']
