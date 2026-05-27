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

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_oauth.py'
AUTH_URL_DEFAULT = 'https://www.bling.com.br/Api/v3/oauth/authorize'
TOKEN_URL_DEFAULT = 'https://www.bling.com.br/Api/v3/oauth/token'
PUBLIC_REDIRECT_URI_DEFAULT = 'https://ia-planilhas-bling.streamlit.app'
CLIENT_ID_DEFAULT = ''

TOKEN_STATE_KEY = 'bling_oauth_token_response'
TOKEN_CONNECTED_AT_KEY = 'bling_oauth_connected_at'
LAST_ERROR_KEY = 'bling_oauth_last_error'
EXPECTED_STATE_KEY = 'bling_oauth_expected_state'
CALLBACK_DONE_KEY = 'bling_oauth_callback_done_for_code'


def _secret(name: str, default: str = '') -> str:
    try:
        bling = st.secrets.get('bling', {})
        value = bling.get(name, default) if hasattr(bling, 'get') else default
        return str(value or default).strip()
    except Exception:
        return default


def client_id() -> str:
    return _secret('client_id', CLIENT_ID_DEFAULT)


def client_secret() -> str:
    return _secret('client_secret', '')


def redirect_uri() -> str:
    configured = _secret('redirect_uri', '')
    if configured:
        return configured.rstrip('/')
    return PUBLIC_REDIRECT_URI_DEFAULT


def authorize_url() -> str:
    return _secret('authorize_url', AUTH_URL_DEFAULT)


def token_url() -> str:
    return _secret('token_url', TOKEN_URL_DEFAULT)


def _new_state() -> str:
    payload = {
        'nonce': secrets.token_urlsafe(24),
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'source': 'ia_planilhas_bling',
        'session_id': get_user_session_id(),
    }
    raw = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')


def build_authorization_url() -> str:
    cid = client_id()
    if not cid:
        return ''
    state = _new_state()
    st.session_state[EXPECTED_STATE_KEY] = state
    params = {
        'response_type': 'code',
        'client_id': cid,
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
                details={'status_code': response.status_code, 'response_preview': text, 'responsible_file': RESPONSIBLE_FILE},
            )
            return False, f'Falha ao conectar ao Bling. Status {response.status_code}.'
        data = response.json()
        save_token(data)
        st.session_state.pop(LAST_ERROR_KEY, None)
        add_audit_event(
            'bling_oauth_connected',
            area='BLING_OAUTH',
            status='OK',
            details={'expires_in': data.get('expires_in'), 'user_session_id': get_user_session_id(), 'responsible_file': RESPONSIBLE_FILE},
        )
        return True, 'Bling conectado com sucesso.'
    except Exception as exc:
        st.session_state[LAST_ERROR_KEY] = str(exc)
        add_audit_event(
            'bling_oauth_exception',
            area='BLING_OAUTH',
            status='ERRO',
            details={'error': str(exc), 'responsible_file': RESPONSIBLE_FILE},
        )
        return False, f'Falha ao conectar ao Bling: {exc}'


def process_oauth_callback() -> None:
    code = _query_param('code')
    if not code:
        return
    if st.session_state.get(CALLBACK_DONE_KEY) == code:
        return

    state = _query_param('state')
    expected = str(st.session_state.get(EXPECTED_STATE_KEY) or '')
    if expected and state and state != expected:
        st.session_state[LAST_ERROR_KEY] = 'Retorno OAuth com state diferente do esperado.'
        add_audit_event('bling_oauth_state_mismatch', area='BLING_OAUTH', status='ERRO', details={'responsible_file': RESPONSIBLE_FILE})
        return

    ok, message = exchange_code_for_token(code)
    st.session_state[CALLBACK_DONE_KEY] = code
    if ok:
        st.success(message)
        try:
            st.query_params.pop('code', None)
            st.query_params.pop('state', None)
        except Exception:
            pass
    else:
        st.warning(message)


def disconnect() -> None:
    clear_token()
    for key in (TOKEN_STATE_KEY, TOKEN_CONNECTED_AT_KEY, LAST_ERROR_KEY, EXPECTED_STATE_KEY, CALLBACK_DONE_KEY):
        st.session_state.pop(key, None)
    add_audit_event('bling_oauth_disconnected', area='BLING_OAUTH', status='OK', details={'user_session_id': get_user_session_id(), 'responsible_file': RESPONSIBLE_FILE})


__all__ = ['build_authorization_url', 'connection_status', 'disconnect', 'is_connected', 'process_oauth_callback', 'required_redirect_uri']
