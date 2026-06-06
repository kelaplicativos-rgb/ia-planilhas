from __future__ import annotations

import base64
import importlib
import os
from datetime import datetime
from typing import Any

import requests

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_token_store import load_token, save_token

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_token_refresh.py'
TOKEN_URL_DEFAULT = 'https://api.bling.com.br/Api/v3/oauth/token'
EXPIRY_FORMAT = '%Y-%m-%d %H:%M:%S'

SECRET_ALIASES: dict[str, tuple[str, ...]] = {
    'client_id': ('client_id', 'clientId', 'clientID', 'CLIENT_ID', 'bling_client_id', 'BLING_CLIENT_ID', 'oauth_client_id', 'BLING_OAUTH_CLIENT_ID'),
    'client_secret': ('client_secret', 'clientSecret', 'CLIENT_SECRET', 'bling_client_secret', 'BLING_CLIENT_SECRET', 'oauth_client_secret', 'BLING_OAUTH_CLIENT_SECRET'),
    'token_url': ('token_url', 'BLING_TOKEN_URL', 'bling_token_url'),
}


def _streamlit_module() -> Any | None:
    try:
        return importlib.import_module('streamlit')
    except Exception:
        return None


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
        value = os.environ.get(alias) or os.environ.get(str(alias).upper())
        if value:
            return str(value).strip()
    return str(default or '').strip()


def _normalize_bling_url(value: str, fallback: str = TOKEN_URL_DEFAULT) -> str:
    text = str(value or fallback or '').strip()
    if text.startswith('https://www.bling.com.br/Api/v3'):
        text = text.replace('https://www.bling.com.br/Api/v3', 'https://api.bling.com.br/Api/v3', 1)
    return text or fallback


def _token_url() -> str:
    return _normalize_bling_url(_secret('token_url', TOKEN_URL_DEFAULT), TOKEN_URL_DEFAULT)


def _client_id() -> str:
    return _secret('client_id', '')


def _client_secret() -> str:
    return _secret('client_secret', '')


def _basic_auth_header(client_id: str, client_secret: str) -> str:
    raw = f'{client_id}:{client_secret}'.encode('utf-8')
    return 'Basic ' + base64.b64encode(raw).decode('ascii')


def _is_expired(expires_at: str) -> bool:
    text = str(expires_at or '').strip()
    if not text:
        return False
    try:
        return datetime.now() >= datetime.strptime(text, EXPIRY_FORMAT)
    except Exception:
        return False


def refresh_bling_token(token: dict[str, Any] | None = None) -> tuple[dict[str, Any] | None, str]:
    current = token if isinstance(token, dict) else None
    if current is None:
        current, _meta = load_token()
    if not isinstance(current, dict) or not current.get('refresh_token'):
        return current if isinstance(current, dict) else None, 'Token sem refresh_token. Reconecte o Bling.'

    client_id = _client_id()
    client_secret = _client_secret()
    if not client_id or not client_secret:
        return current, 'Client ID ou Client Secret do Bling ausente nos secrets.'

    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': str(current.get('refresh_token') or ''),
    }
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': _basic_auth_header(client_id, client_secret),
    }

    try:
        response = requests.post(_token_url(), data=payload, headers=headers, timeout=30)
        if response.status_code >= 400:
            preview = response.text[:300]
            add_audit_event(
                'bling_token_refresh_error',
                area='BLING_OAUTH',
                status='ERRO',
                details={
                    'status_code': response.status_code,
                    'response_preview': preview,
                    'responsible_file': RESPONSIBLE_FILE,
                },
            )
            return current, f'Falha ao renovar token do Bling. Status {response.status_code}.'

        refreshed = response.json()
        if not isinstance(refreshed, dict) or not refreshed.get('access_token'):
            return current, 'Resposta inválida ao renovar token do Bling.'

        if not refreshed.get('refresh_token') and current.get('refresh_token'):
            refreshed['refresh_token'] = current.get('refresh_token')

        save_token(refreshed)
        add_audit_event(
            'bling_token_refreshed',
            area='BLING_OAUTH',
            status='OK',
            details={'responsible_file': RESPONSIBLE_FILE},
        )
        return refreshed, ''
    except Exception as exc:
        add_audit_event(
            'bling_token_refresh_exception',
            area='BLING_OAUTH',
            status='ERRO',
            details={'error': str(exc), 'responsible_file': RESPONSIBLE_FILE},
        )
        return current, f'Falha ao renovar token do Bling: {exc}'


def load_valid_bling_token() -> tuple[dict[str, Any] | None, dict[str, str], str]:
    token, meta = load_token()
    if not isinstance(token, dict) or not token.get('access_token'):
        return None, meta, 'Bling não conectado. Conecte o app antes de enviar direto.'

    expires_at = str(meta.get('expires_at') or '')
    if _is_expired(expires_at):
        refreshed, error = refresh_bling_token(token)
        if isinstance(refreshed, dict) and refreshed.get('access_token') and not error:
            token, meta = load_token()
            return token, meta, ''
        return token, meta, error or 'Token do Bling expirado. Reconecte o Bling.'

    return token, meta, ''


__all__ = ['load_valid_bling_token', 'refresh_bling_token']
