from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlsplit

import requests
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_token_store import load_token, save_token

RESPONSIBLE_FILE = 'bling_app_zero/ui/bling_backend_bridge.py'


def _secret(name: str, default: str = '') -> str:
    try:
        bling = st.secrets.get('bling', {})
        value = bling.get(name, default) if hasattr(bling, 'get') else default
        if value not in (None, ''):
            return str(value).strip()
    except Exception:
        pass
    return str(os.getenv(name) or os.getenv(name.upper()) or default or '').strip()


def backend_auth_url() -> str:
    return _secret('backend_auth_url', '') or _secret('BLING_BACKEND_AUTH_URL', '')


def backend_shared_secret() -> str:
    return _secret('backend_shared_secret', '') or _secret('BLING_BACKEND_SHARED_SECRET', '')


def backend_base_url() -> str:
    configured = backend_auth_url()
    if not configured:
        return ''
    marker = '/auth/bling/start'
    if marker in configured:
        return configured.split(marker, 1)[0].rstrip('/')
    parsed = urlsplit(configured)
    if not parsed.scheme or not parsed.netloc:
        return ''
    return f'{parsed.scheme}://{parsed.netloc}'.rstrip('/')


def backend_connection_status() -> dict[str, Any]:
    base = backend_base_url()
    if not base:
        return {'enabled': False, 'connected': False, 'error': '', 'source': 'streamlit'}
    try:
        response = requests.get(f'{base}/auth/bling/status', timeout=12)
        if response.status_code >= 400:
            return {'enabled': True, 'connected': False, 'error': f'HTTP {response.status_code}', 'source': 'backend'}
        data = response.json() if response.content else {}
        if not isinstance(data, dict):
            data = {}
        data['enabled'] = True
        data['source'] = 'backend'
        data['connected'] = bool(data.get('connected'))
        return data
    except Exception as exc:
        return {'enabled': True, 'connected': False, 'error': str(exc)[:220], 'source': 'backend'}


def sync_backend_token_to_streamlit() -> bool:
    local_token, _meta = load_token()
    if isinstance(local_token, dict) and local_token.get('access_token'):
        return True

    base = backend_base_url()
    secret = backend_shared_secret()
    if not base or not secret:
        return False

    try:
        response = requests.get(
            f'{base}/auth/bling/token',
            headers={'X-Backend-Secret': secret},
            timeout=12,
        )
        if response.status_code >= 400:
            add_audit_event(
                'bling_backend_token_bridge_failed',
                area='BLING_OAUTH',
                status='ERRO',
                details={'status_code': response.status_code, 'responsible_file': RESPONSIBLE_FILE},
            )
            return False
        payload = response.json() if response.content else {}
        token = payload.get('token') if isinstance(payload, dict) else None
        if isinstance(token, dict) and token.get('access_token'):
            save_token(token)
            add_audit_event(
                'bling_backend_token_bridged_to_streamlit',
                area='BLING_OAUTH',
                status='OK',
                details={'responsible_file': RESPONSIBLE_FILE},
            )
            return True
    except Exception as exc:
        add_audit_event(
            'bling_backend_token_bridge_exception',
            area='BLING_OAUTH',
            status='ERRO',
            details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE},
        )
    return False


__all__ = [
    'backend_auth_url',
    'backend_base_url',
    'backend_connection_status',
    'backend_shared_secret',
    'sync_backend_token_to_streamlit',
]
