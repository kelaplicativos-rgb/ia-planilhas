from __future__ import annotations

import importlib
import os
import time
from typing import Any
from urllib.parse import urlsplit

import requests

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/core/interaction_guard.py'

LOGOUT_GUARD_KEY = 'bling_force_disconnected'
LOGOUT_GUARD_AT_KEY = 'bling_force_disconnected_at'
LOGOUT_GUARD_REASON_KEY = 'bling_force_disconnected_reason'
MANUAL_BACK_LOCK_KEY = 'wizard_manual_back_lock'
MANUAL_BACK_TARGET_KEY = 'wizard_manual_back_target'
MANUAL_BACK_FROM_KEY = 'wizard_manual_back_from'
MANUAL_BACK_AT_KEY = 'wizard_manual_back_at'
MANUAL_BACK_RELEASE_KEY = 'wizard_manual_back_release_on_next'

LOGOUT_SESSION_KEYS = (
    'bling_oauth_token_response',
    'bling_oauth_connected_at',
    'bling_oauth_callback_done_for_code',
    'bling_oauth_expected_state',
    'bling_oauth_return_context',
    'bling_oauth_restored_after_callback',
    'home_bling_backend_last_status',
    'home_bling_auth_ready_url',
    'neutral_bling_send_state_v1',
    'bling_api_last_batch_seconds_v1',
    'bling_smart_sender_product_cache_v3',
    'bling_smart_sender_category_cache_v3',
)


def _streamlit_module() -> Any | None:
    try:
        return importlib.import_module('streamlit')
    except Exception:
        return None


def _state() -> Any:
    st = _streamlit_module()
    if st is None:
        return {}
    try:
        return st.session_state
    except Exception:
        return {}


def _secret(name: str, default: str = '') -> str:
    st = _streamlit_module()
    try:
        bling = st.secrets.get('bling', {}) if st is not None else {}
        value = bling.get(name, default) if hasattr(bling, 'get') else default
        if value not in (None, ''):
            return str(value).strip()
    except Exception:
        pass
    return str(os.getenv(name) or os.getenv(name.upper()) or default or '').strip()


def backend_base_url_from_auth_url() -> str:
    configured = _secret('backend_auth_url', '') or _secret('BLING_BACKEND_AUTH_URL', '')
    if not configured:
        return ''
    marker = '/auth/bling/start'
    if marker in configured:
        return configured.split(marker, 1)[0].rstrip('/')
    parsed = urlsplit(configured)
    if not parsed.scheme or not parsed.netloc:
        return ''
    return f'{parsed.scheme}://{parsed.netloc}'.rstrip('/')


def backend_shared_secret() -> str:
    return _secret('backend_shared_secret', '') or _secret('BLING_BACKEND_SHARED_SECRET', '')


def logout_guard_active() -> bool:
    store = _state()
    return bool(getattr(store, 'get', lambda *_: False)(LOGOUT_GUARD_KEY, False))


def activate_logout_guard(reason: str = 'manual_disconnect') -> None:
    store = _state()
    if not hasattr(store, '__setitem__'):
        return
    store[LOGOUT_GUARD_KEY] = True
    store[LOGOUT_GUARD_AT_KEY] = time.time()
    store[LOGOUT_GUARD_REASON_KEY] = reason
    for key in LOGOUT_SESSION_KEYS:
        try:
            store.pop(key, None)
        except Exception:
            pass
    add_audit_event(
        'bling_logout_guard_activated',
        area='BLING_OAUTH',
        status='OK',
        details={'reason': reason, 'responsible_file': RESPONSIBLE_FILE},
    )


def clear_logout_guard(reason: str = 'manual_connect') -> None:
    store = _state()
    if not hasattr(store, 'pop'):
        return
    for key in (LOGOUT_GUARD_KEY, LOGOUT_GUARD_AT_KEY, LOGOUT_GUARD_REASON_KEY):
        try:
            store.pop(key, None)
        except Exception:
            pass
    add_audit_event(
        'bling_logout_guard_cleared',
        area='BLING_OAUTH',
        status='OK',
        details={'reason': reason, 'responsible_file': RESPONSIBLE_FILE},
    )


def disconnect_backend_token() -> bool:
    base = backend_base_url_from_auth_url()
    if not base:
        return False
    headers: dict[str, str] = {}
    secret = backend_shared_secret()
    if secret:
        headers['X-Backend-Secret'] = secret
    try:
        response = requests.post(f'{base}/auth/bling/disconnect', headers=headers, timeout=12)
        ok = response.status_code < 400
        add_audit_event(
            'bling_backend_disconnect_called',
            area='BLING_OAUTH',
            status='OK' if ok else 'AVISO',
            details={'status_code': response.status_code, 'responsible_file': RESPONSIBLE_FILE},
        )
        return ok
    except Exception as exc:
        add_audit_event(
            'bling_backend_disconnect_failed',
            area='BLING_OAUTH',
            status='ERRO',
            details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE},
        )
        return False


def activate_manual_back_lock(from_step: str, target_step: str) -> None:
    store = _state()
    if not hasattr(store, '__setitem__'):
        return
    target = str(target_step or '').strip().lower()
    source = str(from_step or '').strip().lower()
    store[MANUAL_BACK_LOCK_KEY] = True
    store[MANUAL_BACK_TARGET_KEY] = target
    store[MANUAL_BACK_FROM_KEY] = source
    store[MANUAL_BACK_AT_KEY] = time.time()
    store[MANUAL_BACK_RELEASE_KEY] = False
    add_audit_event(
        'wizard_manual_back_lock_activated',
        area='WIZARD',
        step=target,
        status='OK',
        details={'from': source, 'to': target, 'responsible_file': RESPONSIBLE_FILE},
    )


def manual_back_lock_active(target_step: str | None = None) -> bool:
    store = _state()
    getter = getattr(store, 'get', lambda *_: None)
    if not bool(getter(MANUAL_BACK_LOCK_KEY, False)):
        return False
    if not target_step:
        return True
    target = str(getter(MANUAL_BACK_TARGET_KEY, '') or '').strip().lower()
    return target == str(target_step or '').strip().lower()


def locked_manual_back_target(default: str = '') -> str:
    store = _state()
    getter = getattr(store, 'get', lambda *_: None)
    return str(getter(MANUAL_BACK_TARGET_KEY, default) or default or '').strip().lower()


def clear_manual_back_lock(reason: str = 'manual_next') -> None:
    store = _state()
    if not hasattr(store, 'pop'):
        return
    target = str(store.get(MANUAL_BACK_TARGET_KEY, '') or '').strip().lower() if hasattr(store, 'get') else ''
    for key in (
        MANUAL_BACK_LOCK_KEY,
        MANUAL_BACK_TARGET_KEY,
        MANUAL_BACK_FROM_KEY,
        MANUAL_BACK_AT_KEY,
        MANUAL_BACK_RELEASE_KEY,
    ):
        try:
            store.pop(key, None)
        except Exception:
            pass
    add_audit_event(
        'wizard_manual_back_lock_cleared',
        area='WIZARD',
        step=target,
        status='OK',
        details={'reason': reason, 'responsible_file': RESPONSIBLE_FILE},
    )


__all__ = [
    'activate_logout_guard',
    'activate_manual_back_lock',
    'backend_base_url_from_auth_url',
    'backend_shared_secret',
    'clear_logout_guard',
    'clear_manual_back_lock',
    'disconnect_backend_token',
    'locked_manual_back_target',
    'logout_guard_active',
    'manual_back_lock_active',
]
