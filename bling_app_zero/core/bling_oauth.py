from __future__ import annotations

import base64
import json
import secrets
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import requests
import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_oauth.py'
AUTH_URL_DEFAULT = 'https://www.bling.com.br/OAuth2/views/authorization.php'
TOKEN_URL_DEFAULT = 'https://www.bling.com.br/Api/v3/oauth/token'
CLIENT_ID_DEFAULT = '4ef4b0753ae8a4c319f7f8d5e0a7abce08954be2'
DEFAULT_SCOPES = [
    '98308', '98309', '98310', '98313', '98314', '104142', '104163', '107041',
    '507943', '575904', '5990556', '6631498', '106168710', '182224097',
    '199272829', '220621674', '318257555', '318257556', '318257562',
    '318257563', '318257564', '318257565', '318257570', '318257576',
    '318257577', '318257578', '333936575', '363921590', '363921591',
    '363921593', '363921594', '1649295804', '1869535257', '13645013013',
]

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
        return configured
    try:
        return st.context.url.split('?', 1)[0]
    except Exception:
        return ''


def authorize_url() -> str:
    return _secret('authorize_url', AUTH_URL_DEFAULT)


def token_url() -> str:
    return _secret('token_url', TOKEN_URL_DEFAULT)


def scopes() -> list[str]:
    raw = _secret('scopes', '')
    if raw:
        return [item for item in raw.replace(',', ' ').split() if item.strip()]
    return list(DEFAULT_SCOPES)


def _new_state() -> str:
    payload = {
        'nonce': secrets.token_urlsafe(24),
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'source': 'ia_planilhas_bling',
    }
    raw = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')


def build_authorization_url() -> str:
    state = _new_state()
    st.session_state[EXPECTED_STATE_KEY] = state
    params = {
        'client_id': client_id(),
        'response_type': 'code',
        'state': state,
        'scopes': ' '.join(scopes()),
    }
    uri = redirect_uri()
    if uri:
        params['redirect_uri'] = uri
    return f'{authorize_url()}?{urlencode(params)}'


def is_connected() -> bool:
    token = st.session_state.get(TOKEN_STATE_KEY)
    return isinstance(token, dict) and bool(token.get('access_token'))


def connection_status() -> dict[str, Any]:
    token = st.session_state.get(TOKEN_STATE_KEY)
    if not isinstance(token, dict):
        return {'connected': False, 'message': 'Bling não conectado.'}
    connected_at = str(st.session_state.get(TOKEN_CONNECTED_AT_KEY) or '')
    expires_in = token.get('expires_in')
    return {
        'connected': bool(token.get('access_token')),
        'connected_at': connected_at,
        'expires_in': expires_in,
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
        return False, 'Client ID do Bling não configurado.'
    if not secret:
        return False, 'Client Secret do Bling ainda não está configurado nos secrets do app.'

    payload: dict[str, str] = {
        'grant_type': 'authorization_code',
        'code': code,
    }
    if uri:
        payload['redirect_uri'] = uri

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
        st.session_state[TOKEN_STATE_KEY] = data
        st.session_state[TOKEN_CONNECTED_AT_KEY] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        st.session_state.pop(LAST_ERROR_KEY, None)
        add_audit_event(
            'bling_oauth_connected',
            area='BLING_OAUTH',
            status='OK',
            details={'expires_in': data.get('expires_in'), 'responsible_file': RESPONSIBLE_FILE},
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
        add_audit_event(
            'bling_oauth_state_mismatch',
            area='BLING_OAUTH',
            status='ERRO',
            details={'responsible_file': RESPONSIBLE_FILE},
        )
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
    for key in (TOKEN_STATE_KEY, TOKEN_CONNECTED_AT_KEY, LAST_ERROR_KEY, EXPECTED_STATE_KEY, CALLBACK_DONE_KEY):
        st.session_state.pop(key, None)
    add_audit_event('bling_oauth_disconnected', area='BLING_OAUTH', status='OK', details={'responsible_file': RESPONSIBLE_FILE})


__all__ = [
    'build_authorization_url',
    'connection_status',
    'disconnect',
    'is_connected',
    'process_oauth_callback',
]
