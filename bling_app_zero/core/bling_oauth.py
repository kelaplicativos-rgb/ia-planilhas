from __future__ import annotations

import base64
import json
import os
import secrets
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import requests
import streamlit as st
import streamlit.components.v1 as components

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_token_store import clear_token, get_user_session_id, load_token, save_token
from bling_app_zero.core.oauth_return_snapshot import restore_download_oauth_return

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_oauth.py'
AUTH_URL_DEFAULT = 'https://www.bling.com.br/Api/v3/oauth/authorize'
TOKEN_URL_DEFAULT = 'https://www.bling.com.br/Api/v3/oauth/token'
PUBLIC_REDIRECT_URI_DEFAULT = 'https://ia-planilhas.streamlit.app/'
CLIENT_ID_DEFAULT = ''

TOKEN_STATE_KEY = 'bling_oauth_token_response'
TOKEN_CONNECTED_AT_KEY = 'bling_oauth_connected_at'
LAST_ERROR_KEY = 'bling_oauth_last_error'
EXPECTED_STATE_KEY = 'bling_oauth_expected_state'
CALLBACK_DONE_KEY = 'bling_oauth_callback_done_for_code'
RETURN_CONTEXT_KEY = 'bling_oauth_return_context'
RESTORED_AFTER_CALLBACK_KEY = 'bling_oauth_restored_after_callback'
STATE_SOURCE = 'ia_planilhas_bling'
CONTEXT_BLING_API = 'bling_api'

SECRET_ALIASES: dict[str, tuple[str, ...]] = {
    'client_id': ('client_id', 'clientId', 'clientID', 'CLIENT_ID', 'bling_client_id', 'BLING_CLIENT_ID', 'oauth_client_id', 'BLING_OAUTH_CLIENT_ID'),
    'client_secret': ('client_secret', 'clientSecret', 'clientSECRET', 'CLIENT_SECRET', 'bling_client_secret', 'BLING_CLIENT_SECRET', 'oauth_client_secret', 'BLING_OAUTH_CLIENT_SECRET'),
    'redirect_uri': ('redirect_uri', 'redirectUrl', 'redirectURL', 'callback_url', 'callback_uri', 'BLING_REDIRECT_URI', 'bling_redirect_uri', 'BLING_CALLBACK_URL'),
    'authorize_url': ('authorize_url', 'authorization_url', 'BLING_AUTHORIZE_URL', 'bling_authorize_url'),
    'token_url': ('token_url', 'BLING_TOKEN_URL', 'bling_token_url'),
    'include_redirect_uri_in_authorize': ('include_redirect_uri_in_authorize', 'BLING_INCLUDE_REDIRECT_URI_IN_AUTHORIZE'),
}


def _read_from_mapping(mapping: Any, names: tuple[str, ...]) -> str:
    if not hasattr(mapping, 'get'):
        return ''
    for name in names:
        try:
            value = mapping.get(name)
        except Exception:
            value = None
        if value not in (None, ''):
            return str(value).strip()
    return ''


def _secret(name: str, default: str = '') -> str:
    aliases = SECRET_ALIASES.get(name, (name,))
    try:
        bling = st.secrets.get('bling', {})
        value = _read_from_mapping(bling, aliases)
        if value:
            return value
    except Exception:
        pass
    try:
        value = _read_from_mapping(st.secrets, aliases)
        if value:
            return value
    except Exception:
        pass
    for alias in aliases:
        value = os.environ.get(alias)
        if value:
            return str(value).strip()
        upper_value = os.environ.get(str(alias).upper())
        if upper_value:
            return str(upper_value).strip()
    return str(default or '').strip()


def _secret_bool(name: str, default: bool = False) -> bool:
    raw = _secret(name, '1' if default else '0').strip().lower()
    return raw in {'1', 'true', 'sim', 'yes', 'on'}


def _mask(value: str) -> str:
    text = str(value or '').strip()
    if not text:
        return ''
    if len(text) <= 8:
        return text[:2] + '***'
    return text[:4] + '***' + text[-4:]


def _normalize_redirect_uri(value: str) -> str:
    configured = str(value or '').strip()
    if not configured:
        add_audit_event(
            'bling_oauth_redirect_uri_default_used',
            area='BLING_OAUTH',
            status='AVISO',
            details={'redirect_uri': PUBLIC_REDIRECT_URI_DEFAULT, 'reason': 'redirect_uri não configurado no secrets.toml; usando fallback público', 'responsible_file': RESPONSIBLE_FILE},
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


def include_redirect_uri_in_authorize() -> bool:
    return _secret_bool('include_redirect_uri_in_authorize', False)


def oauth_config_status() -> dict[str, Any]:
    cid = client_id()
    secret = client_secret()
    uri = redirect_uri()
    return {
        'ready': bool(cid and secret and uri),
        'has_client_id': bool(cid),
        'has_client_secret': bool(secret),
        'has_redirect_uri': bool(uri),
        'client_id_masked': _mask(cid),
        'redirect_uri': uri,
        'authorize_url': authorize_url(),
        'token_url': token_url(),
        'include_redirect_uri_in_authorize': include_redirect_uri_in_authorize(),
        'missing': [name for name, ok in (('client_id', bool(cid)), ('client_secret', bool(secret)), ('redirect_uri', bool(uri))) if not ok],
    }


def _encode_state_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
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
    payload: dict[str, Any] = {'n': secrets.token_urlsafe(18), 't': datetime.now().isoformat(timespec='seconds'), 'src': STATE_SOURCE, 'sid': get_user_session_id()}
    if isinstance(extra_context, dict):
        payload.update({k: v for k, v in extra_context.items() if isinstance(k, str)})
    return _encode_state_payload(payload)


def build_authorization_url(extra_context: dict[str, Any] | None = None) -> str:
    cid = client_id()
    if not cid:
        st.session_state[LAST_ERROR_KEY] = 'Client ID do Bling não configurado nos secrets do app.'
        add_audit_event('bling_oauth_missing_client_id', area='BLING_OAUTH', status='ERRO', details={'responsible_file': RESPONSIBLE_FILE, 'accepted_aliases': SECRET_ALIASES['client_id']})
        return ''
    state = _new_state(extra_context)
    st.session_state[EXPECTED_STATE_KEY] = state
    if isinstance(extra_context, dict):
        st.session_state[RETURN_CONTEXT_KEY] = dict(extra_context)
    uri = redirect_uri()
    include_redirect = include_redirect_uri_in_authorize()
    params = {'response_type': 'code', 'client_id': cid, 'state': state}
    if include_redirect:
        params['redirect_uri'] = uri
    add_audit_event('bling_oauth_authorization_url_built', area='BLING_OAUTH', status='OK', details={'redirect_uri': uri, 'include_redirect_uri_in_authorize': include_redirect, 'has_client_id': bool(cid), 'client_id_masked': _mask(cid), 'has_state': bool(state), 'responsible_file': RESPONSIBLE_FILE})
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
    config = oauth_config_status()
    try:
        token, meta = load_token()
    except Exception as exc:
        return {'connected': False, 'message': 'Bling não conectado.', 'error': str(exc), 'required_redirect_uri': required_redirect_uri(), 'include_redirect_uri_in_authorize': include_redirect_uri_in_authorize(), 'oauth_config': config}
    if not isinstance(token, dict):
        return {'connected': False, 'message': 'Bling não conectado.', 'required_redirect_uri': required_redirect_uri(), 'include_redirect_uri_in_authorize': include_redirect_uri_in_authorize(), 'oauth_config': config, **meta}
    return {'connected': bool(token.get('access_token')), 'connected_at': meta.get('connected_at', ''), 'expires_at': meta.get('expires_at', ''), 'expires_in': token.get('expires_in'), 'store_mode': meta.get('store_mode', ''), 'user_session_id': meta.get('user_session_id', ''), 'required_redirect_uri': required_redirect_uri(), 'include_redirect_uri_in_authorize': include_redirect_uri_in_authorize(), 'oauth_config': config, 'message': 'Bling conectado.' if token.get('access_token') else 'Bling não conectado.'}


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
    if not uri:
        return False, 'Redirect URI do Bling não configurado.'
    payload: dict[str, str] = {'grant_type': 'authorization_code', 'code': code, 'redirect_uri': uri}
    headers = {'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded', 'Authorization': _basic_auth_header(cid, secret)}
    try:
        response = requests.post(token_url(), data=payload, headers=headers, timeout=30)
        if response.status_code >= 400:
            text = response.text[:500]
            st.session_state[LAST_ERROR_KEY] = text
            add_audit_event('bling_oauth_token_error', area='BLING_OAUTH', status='ERRO', details={'status_code': response.status_code, 'response_preview': text, 'redirect_uri': uri, 'client_id_masked': _mask(cid), 'responsible_file': RESPONSIBLE_FILE})
            return False, f'Falha ao conectar ao Bling. Status {response.status_code}. Confira se o Callback URL cadastrado no app v3 do Bling é exatamente: {uri}'
        data = response.json()
        save_token(data)
        st.session_state.pop(LAST_ERROR_KEY, None)
        add_audit_event('bling_oauth_connected', area='BLING_OAUTH', status='OK', details={'expires_in': data.get('expires_in'), 'user_session_id': get_user_session_id(), 'redirect_uri': uri, 'client_id_masked': _mask(cid), 'responsible_file': RESPONSIBLE_FILE})
        return True, 'Bling conectado com sucesso.'
    except Exception as exc:
        st.session_state[LAST_ERROR_KEY] = str(exc)
        add_audit_event('bling_oauth_exception', area='BLING_OAUTH', status='ERRO', details={'error': str(exc), 'redirect_uri': uri, 'client_id_masked': _mask(cid), 'responsible_file': RESPONSIBLE_FILE})
        return False, f'Falha ao conectar ao Bling: {exc}'


def _state_is_trusted(state: str, expected: str, payload: dict[str, Any]) -> bool:
    if expected and state and state == expected:
        return True
    source = payload.get('source') or payload.get('src')
    session_id = payload.get('session_id') or payload.get('sid')
    if source == STATE_SOURCE and session_id:
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
    session_id = str(state_payload.get('session_id') or state_payload.get('sid') or get_user_session_id()).strip()
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


def _try_close_oauth_popup_after_success() -> None:
    components.html(
        '''
<script>
(function () {
    try {
        if (window.opener && !window.opener.closed) {
            const nextUrl = window.location.origin + window.location.pathname + '?operation_v2=wizard_cadastro_estoque';
            window.opener.location.href = nextUrl;
            setTimeout(function () { window.close(); }, 700);
        }
    } catch (err) {
        console.log('OAuth popup close skipped:', err);
    }
})();
</script>
''',
        height=0,
    )


def handle_oauth_callback() -> None:
    code = _query_param('code')
    state = _query_param('state')
    error = _query_param('error')
    expected_state = str(st.session_state.get(EXPECTED_STATE_KEY) or '')
    state_payload = _decode_state_payload(state)
    if error:
        st.session_state[LAST_ERROR_KEY] = error
        st.error(f'Bling não autorizou a conexão: {error}')
        add_audit_event('bling_oauth_callback_error_param', area='BLING_OAUTH', status='ERRO', details={'error': error, 'responsible_file': RESPONSIBLE_FILE})
        return
    if not code:
        return
    if not _state_is_trusted(state, expected_state, state_payload):
        st.warning('Recebi retorno do Bling, mas a sessão de segurança não confere. Gere o link novamente.')
        add_audit_event('bling_oauth_state_mismatch', area='BLING_OAUTH', status='ERRO', details={'has_expected_state': bool(expected_state), 'has_state': bool(state), 'state_payload': state_payload, 'responsible_file': RESPONSIBLE_FILE})
        return
    if st.session_state.get(CALLBACK_DONE_KEY) == code:
        return
    ok, message = exchange_code_for_token(code)
    st.session_state[CALLBACK_DONE_KEY] = code
    if ok:
        st.success(message)
        _restore_oauth_return_context(state_payload)
        st.session_state.pop(EXPECTED_STATE_KEY, None)
        st.session_state.pop(LAST_ERROR_KEY, None)
        try:
            st.query_params.pop('code', None)
            st.query_params.pop('state', None)
        except Exception:
            pass
        _try_close_oauth_popup_after_success()
        st.rerun()
    else:
        st.error(message)


def process_oauth_callback() -> None:
    handle_oauth_callback()


def render_connection_panel() -> None:
    status = connection_status()
    if status.get('connected'):
        st.success('Bling conectado.')
        st.caption(f"Conectado em: {status.get('connected_at', '')}")
        if st.button('Desconectar Bling', use_container_width=True):
            clear_token()
            st.session_state.pop(EXPECTED_STATE_KEY, None)
            st.session_state.pop(LAST_ERROR_KEY, None)
            st.success('Bling desconectado.')
            st.rerun()
        return
    config = status.get('oauth_config') if isinstance(status.get('oauth_config'), dict) else oauth_config_status()
    if not config.get('has_client_id'):
        st.error('Credencial do Bling ausente: client_id não configurado nos secrets do app.')
    if not config.get('has_client_secret'):
        st.warning('Client Secret do Bling ainda não está configurado. A autorização pode abrir, mas o token não será concluído sem ele.')
    st.caption(f"Callback URL exigido no Bling: {required_redirect_uri()}")
    auth_url = build_authorization_url({'return_to': 'download', 'source_step': 'connection_panel'})
    if auth_url:
        st.link_button('Conectar com Bling', auth_url, use_container_width=True)
    else:
        st.info('Configure as credenciais do Bling para liberar o botão de conexão.')


__all__ = [
    'build_authorization_url',
    'client_id',
    'client_secret',
    'connection_status',
    'exchange_code_for_token',
    'handle_oauth_callback',
    'include_redirect_uri_in_authorize',
    'is_connected',
    'oauth_config_status',
    'process_oauth_callback',
    'redirect_uri',
    'render_connection_panel',
    'required_redirect_uri',
]
