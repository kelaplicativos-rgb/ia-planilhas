from __future__ import annotations

import base64
import importlib
import json
import os
import secrets
from collections.abc import MutableMapping
from datetime import datetime
from html import escape
from typing import Any
from urllib.parse import urlencode

import requests

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
CONTEXT_UNIVERSAL = 'universal'
FINISH_MODE_CSV = 'csv_download'
FLOW_WIZARD = 'wizard_cadastro_estoque'
STEP_ORIGEM = 'origem'
HOME_BOOT_LOCK_KEY = 'home_boot_landing_rendered_once'
HOME_FLOW_SCHEMA_KEY = 'home_source_first_flow_schema_v1'
HOME_FLOW_SCHEMA_VERSION = 'source_first_origin_start_v4_unified_bling_20260613'
UNIFIED_BLING_SEND_KEY = 'home_bling_connected_same_flow_api_send'
_FALLBACK_STATE: dict[str, Any] = {}
_FALLBACK_QUERY_PARAMS: dict[str, Any] = {}

SECRET_ALIASES: dict[str, tuple[str, ...]] = {
    'client_id': ('client_id', 'clientId', 'clientID', 'CLIENT_ID', 'bling_client_id', 'BLING_CLIENT_ID', 'oauth_client_id', 'BLING_OAUTH_CLIENT_ID'),
    'client_secret': ('client_secret', 'clientSecret', 'clientSECRET', 'CLIENT_SECRET', 'bling_client_secret', 'BLING_CLIENT_SECRET', 'oauth_client_secret', 'BLING_OAUTH_CLIENT_SECRET'),
    'redirect_uri': ('redirect_uri', 'redirectUrl', 'redirectURL', 'callback_url', 'callback_uri', 'BLING_REDIRECT_URI', 'bling_redirect_uri', 'BLING_CALLBACK_URL'),
    'authorize_url': ('authorize_url', 'authorization_url', 'BLING_AUTHORIZE_URL', 'bling_authorize_url'),
    'token_url': ('token_url', 'BLING_TOKEN_URL', 'bling_token_url'),
    'include_redirect_uri_in_authorize': ('include_redirect_uri_in_authorize', 'BLING_INCLUDE_REDIRECT_URI_IN_AUTHORIZE'),
    'backend_auth_url': ('backend_auth_url', 'BLING_BACKEND_AUTH_URL'),
}


def _streamlit_module() -> Any | None:
    try:
        return importlib.import_module('streamlit')
    except Exception:
        return None


def _state_store() -> MutableMapping[str, Any]:
    st = _streamlit_module()
    if st is not None:
        try:
            return st.session_state
        except Exception:
            pass
    return _FALLBACK_STATE


def _query_params_store() -> MutableMapping[str, Any]:
    st = _streamlit_module()
    if st is not None:
        try:
            return st.query_params
        except Exception:
            pass
    return _FALLBACK_QUERY_PARAMS


def _secrets_store() -> Any:
    st = _streamlit_module()
    if st is not None:
        try:
            return st.secrets
        except Exception:
            return {}
    return {}


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
    secrets_store = _secrets_store()
    try:
        bling = secrets_store.get('bling', {})
        value = _read_from_mapping(bling, aliases)
        if value:
            return value
    except Exception:
        pass
    try:
        value = _read_from_mapping(secrets_store, aliases)
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
            details={
                'redirect_uri': PUBLIC_REDIRECT_URI_DEFAULT,
                'reason': 'redirect_uri não configurado no secrets.toml; usando fallback público',
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


def backend_auth_url() -> str:
    return _secret('backend_auth_url', '')


def include_redirect_uri_in_authorize() -> bool:
    return _secret_bool('include_redirect_uri_in_authorize', False)


def oauth_config_status() -> dict[str, Any]:
    cid = client_id()
    secret = client_secret()
    uri = redirect_uri()
    backend_url = backend_auth_url()
    return {
        'ready': bool(backend_url or (cid and secret and uri)),
        'has_client_id': bool(cid),
        'has_client_secret': bool(secret),
        'has_redirect_uri': bool(uri),
        'client_id_masked': _mask(cid),
        'redirect_uri': uri,
        'authorize_url': authorize_url(),
        'token_url': token_url(),
        'backend_auth_url': backend_url,
        'uses_backend_auth': bool(backend_url),
        'include_redirect_uri_in_authorize': include_redirect_uri_in_authorize(),
        'missing': [] if backend_url else [name for name, ok in (('client_id', bool(cid)), ('client_secret', bool(secret)), ('redirect_uri', bool(uri))) if not ok],
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
    payload: dict[str, Any] = {
        'n': secrets.token_urlsafe(18),
        't': datetime.now().isoformat(timespec='seconds'),
        'src': STATE_SOURCE,
        'sid': get_user_session_id(),
    }
    if isinstance(extra_context, dict):
        payload.update({k: v for k, v in extra_context.items() if isinstance(k, str)})
    return _encode_state_payload(payload)


def build_authorization_url(extra_context: dict[str, Any] | None = None) -> str:
    forced_backend_url = backend_auth_url()
    if forced_backend_url:
        add_audit_event(
            'bling_oauth_backend_authorization_forced',
            area='BLING_OAUTH',
            status='OK',
            details={'backend_auth_url': forced_backend_url, 'responsible_file': RESPONSIBLE_FILE},
        )
        return forced_backend_url

    store = _state_store()
    cid = client_id()
    if not cid:
        store[LAST_ERROR_KEY] = 'Client ID do Bling não configurado nos secrets do app.'
        add_audit_event(
            'bling_oauth_missing_client_id',
            area='BLING_OAUTH',
            status='ERRO',
            details={'responsible_file': RESPONSIBLE_FILE, 'accepted_aliases': SECRET_ALIASES['client_id']},
        )
        return ''
    state = _new_state(extra_context)
    store[EXPECTED_STATE_KEY] = state
    if isinstance(extra_context, dict):
        store[RETURN_CONTEXT_KEY] = dict(extra_context)
    uri = redirect_uri()
    include_redirect = include_redirect_uri_in_authorize()
    params = {'response_type': 'code', 'client_id': cid, 'state': state}
    if include_redirect:
        params['redirect_uri'] = uri
    add_audit_event(
        'bling_oauth_authorization_url_built',
        area='BLING_OAUTH',
        status='OK',
        details={
            'redirect_uri': uri,
            'include_redirect_uri_in_authorize': include_redirect,
            'has_client_id': bool(cid),
            'client_id_masked': _mask(cid),
            'has_state': bool(state),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return f'{authorize_url()}?{urlencode(params)}'


def required_redirect_uri() -> str:
    backend_url = backend_auth_url()
    if backend_url and '/auth/bling/start' in backend_url:
        return backend_url.split('/auth/bling/start', 1)[0].rstrip('/') + '/auth/bling/callback'
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
        return {
            'connected': False,
            'message': 'Bling não conectado.',
            'error': str(exc),
            'required_redirect_uri': required_redirect_uri(),
            'include_redirect_uri_in_authorize': include_redirect_uri_in_authorize(),
            'oauth_config': config,
        }
    if not isinstance(token, dict):
        return {
            'connected': False,
            'message': 'Bling não conectado.',
            'required_redirect_uri': required_redirect_uri(),
            'include_redirect_uri_in_authorize': include_redirect_uri_in_authorize(),
            'oauth_config': config,
            **meta,
        }
    return {
        'connected': bool(token.get('access_token')),
        'connected_at': meta.get('connected_at', ''),
        'expires_at': meta.get('expires_at', ''),
        'expires_in': token.get('expires_in'),
        'store_mode': meta.get('store_mode', ''),
        'user_session_id': meta.get('user_session_id', ''),
        'required_redirect_uri': required_redirect_uri(),
        'include_redirect_uri_in_authorize': include_redirect_uri_in_authorize(),
        'oauth_config': config,
        'message': 'Bling conectado.' if token.get('access_token') else 'Bling não conectado.',
    }


def _query_param(name: str) -> str:
    try:
        value = _query_params_store().get(name)
    except Exception:
        return ''
    if isinstance(value, list):
        return str(value[0] if value else '').strip()
    return str(value or '').strip()


def _basic_auth_header(cid: str, secret: str) -> str:
    raw = f'{cid}:{secret}'.encode('utf-8')
    return 'Basic ' + base64.b64encode(raw).decode('ascii')


def exchange_code_for_token(code: str) -> tuple[bool, str]:
    store = _state_store()
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
            store[LAST_ERROR_KEY] = text
            add_audit_event(
                'bling_oauth_token_error',
                area='BLING_OAUTH',
                status='ERRO',
                details={'status_code': response.status_code, 'response_preview': text, 'redirect_uri': uri, 'client_id_masked': _mask(cid), 'responsible_file': RESPONSIBLE_FILE},
            )
            return False, f'Falha ao conectar ao Bling. Status {response.status_code}. Confira se o Callback URL cadastrado no app v3 do Bling é exatamente: {uri}'
        data = response.json()
        save_token(data)
        store.pop(LAST_ERROR_KEY, None)
        add_audit_event(
            'bling_oauth_connected',
            area='BLING_OAUTH',
            status='OK',
            details={'expires_in': data.get('expires_in'), 'user_session_id': get_user_session_id(), 'redirect_uri': uri, 'client_id_masked': _mask(cid), 'responsible_file': RESPONSIBLE_FILE},
        )
        return True, 'Bling conectado com sucesso.'
    except Exception as exc:
        store[LAST_ERROR_KEY] = str(exc)
        add_audit_event(
            'bling_oauth_exception',
            area='BLING_OAUTH',
            status='ERRO',
            details={'error': str(exc), 'redirect_uri': uri, 'client_id_masked': _mask(cid), 'responsible_file': RESPONSIBLE_FILE},
        )
        return False, f'Falha ao conectar ao Bling: {exc}'


def _state_is_trusted(state: str, expected: str, payload: dict[str, Any]) -> bool:
    if expected and state and state == expected:
        return True
    source = payload.get('source') or payload.get('src')
    session_id = payload.get('session_id') or payload.get('sid')
    if source == STATE_SOURCE and session_id:
        return True
    return not expected


def _restore_unified_bling_flow(payload: dict[str, Any]) -> None:
    store = _state_store()
    store['home_active_operation_v2'] = FLOW_WIZARD
    store['home_allow_operation_v2_session'] = True
    store['home_single_page_flow_active'] = True
    store[HOME_BOOT_LOCK_KEY] = True
    store['home_entry_context'] = CONTEXT_UNIVERSAL
    store['home_slim_entry_context'] = CONTEXT_UNIVERSAL
    store['bling_finish_mode'] = FINISH_MODE_CSV
    store['finish_mode'] = FINISH_MODE_CSV
    store[UNIFIED_BLING_SEND_KEY] = True
    store['bling_wizard_step'] = STEP_ORIGEM
    store['home_wizard_step'] = STEP_ORIGEM
    store[HOME_FLOW_SCHEMA_KEY] = HOME_FLOW_SCHEMA_VERSION
    store.pop('home_bling_auth_ready_url', None)

    qp = _query_params_store()
    try:
        qp['operation_v2'] = FLOW_WIZARD
        qp['step'] = STEP_ORIGEM
        for key in ('flow', 'origem', 'operacao', 'operation'):
            qp.pop(key, None)
    except Exception:
        pass

    add_audit_event(
        'bling_oauth_return_restored_to_unified_flow',
        area='BLING_OAUTH',
        status='OK',
        details={
            'return_to': payload.get('return_to') or '',
            'source_step': payload.get('source_step') or '',
            'operation_v2': FLOW_WIZARD,
            'step': STEP_ORIGEM,
            'home_entry_context': CONTEXT_UNIVERSAL,
            'api_send_flag': True,
            'boot_lock_preserved': True,
            'schema_version': HOME_FLOW_SCHEMA_VERSION,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _restore_oauth_return_context(payload: dict[str, Any]) -> None:
    store = _state_store()
    if store.get(RESTORED_AFTER_CALLBACK_KEY):
        return
    source_step = str(payload.get('source_step') or '')
    return_to = str(payload.get('return_to') or '')
    if source_step == 'download_panel' or return_to == 'download_panel':
        restore_download_oauth_return()

    # BLINGFIX 2026-06-13:
    # O link atual da Home envia return_to=home_light_entry. Antes esse retorno não era tratado
    # e o app caía em uma Home/tela intermediária até o usuário atualizar a página.
    # Agora qualquer conexão iniciada pela Home/entrada do Bling volta direto para o mesmo wizard.
    if source_step in {'bling_connection_entry', 'home_same_tab_connection', 'home_light_entry'} or return_to in {'start', 'home_light_entry'}:
        _restore_unified_bling_flow(payload)
    store[RESTORED_AFTER_CALLBACK_KEY] = True


def _clear_query_params_after_callback() -> None:
    qp = _query_params_store()
    for key in ('code', 'state', 'error', 'error_description'):
        try:
            qp.pop(key, None)
        except Exception:
            pass


def process_oauth_callback() -> None:
    code = _query_param('code')
    state = _query_param('state')
    error = _query_param('error')
    error_description = _query_param('error_description')
    if not code and not error:
        return
    store = _state_store()
    callback_marker = f'{code}:{state}'
    if code and store.get(CALLBACK_DONE_KEY) == callback_marker:
        return
    if error:
        store[LAST_ERROR_KEY] = error_description or error
        add_audit_event('bling_oauth_callback_error', area='BLING_OAUTH', status='ERRO', details={'error': error, 'description': error_description, 'responsible_file': RESPONSIBLE_FILE})
        _clear_query_params_after_callback()
        return
    expected = str(store.get(EXPECTED_STATE_KEY) or '').strip()
    payload = _decode_state_payload(state)
    if not _state_is_trusted(state, expected, payload):
        store[LAST_ERROR_KEY] = 'Estado OAuth inválido. Gere o link novamente.'
        add_audit_event('bling_oauth_invalid_state', area='BLING_OAUTH', status='ERRO', details={'expected': bool(expected), 'received': bool(state), 'payload': payload, 'responsible_file': RESPONSIBLE_FILE})
        _clear_query_params_after_callback()
        return
    ok, message = exchange_code_for_token(code)
    if ok:
        store[CALLBACK_DONE_KEY] = callback_marker
        _restore_oauth_return_context(payload)
    store[LAST_ERROR_KEY] = '' if ok else message
    _clear_query_params_after_callback()
    st = _streamlit_module()
    if st is not None:
        try:
            st.rerun()
        except Exception:
            pass


def disconnect() -> None:
    clear_token()
    store = _state_store()
    for key in (LAST_ERROR_KEY, EXPECTED_STATE_KEY, CALLBACK_DONE_KEY, RETURN_CONTEXT_KEY, RESTORED_AFTER_CALLBACK_KEY):
        store.pop(key, None)
    add_audit_event('bling_oauth_disconnected', area='BLING_OAUTH', status='OK', details={'responsible_file': RESPONSIBLE_FILE})


def render_connection_status_card() -> None:
    st = _streamlit_module()
    if st is None:
        return
    status = connection_status()
    if status.get('connected'):
        st.success('Bling conectado.')
    else:
        st.warning('Bling não conectado.')
    config = status.get('oauth_config') if isinstance(status.get('oauth_config'), dict) else {}
    with st.expander('Detalhes técnicos da conexão Bling', expanded=False):
        st.write({
            'ready': config.get('ready'),
            'uses_backend_auth': config.get('uses_backend_auth'),
            'backend_auth_url_configured': bool(config.get('backend_auth_url')),
            'has_client_id': config.get('has_client_id'),
            'has_client_secret': config.get('has_client_secret'),
            'redirect_uri': status.get('required_redirect_uri'),
            'include_redirect_uri_in_authorize': status.get('include_redirect_uri_in_authorize'),
            'connected': status.get('connected'),
            'store_mode': status.get('store_mode'),
            'missing': config.get('missing'),
        })


__all__ = [
    'build_authorization_url',
    'client_id',
    'client_secret',
    'connection_status',
    'disconnect',
    'exchange_code_for_token',
    'include_redirect_uri_in_authorize',
    'is_connected',
    'oauth_config_status',
    'process_oauth_callback',
    'redirect_uri',
    'render_connection_status_card',
    'required_redirect_uri',
]
