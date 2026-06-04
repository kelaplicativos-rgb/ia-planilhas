from __future__ import annotations

import importlib
import json
import os
import sqlite3
from collections.abc import MutableMapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_token_store.py'
SESSION_ID_KEY = 'bling_oauth_user_session_id'
SESSION_TOKEN_KEY = 'bling_oauth_token_response'
SESSION_CONNECTED_AT_KEY = 'bling_oauth_connected_at'
DEFAULT_DB_PATH = Path('bling_user_tokens') / 'tokens.sqlite3'
DEFAULT_FIRESTORE_COLLECTION = 'bling_tokens'
_FALLBACK_STATE: dict[str, Any] = {}

SENSITIVE_TOKEN_KEYS = {
    'access_token',
    'refresh_token',
    'token',
    'authorization',
    'client_secret',
}

SECRET_ALIASES: dict[str, tuple[str, ...]] = {
    'token_store_mode': ('token_store_mode', 'BLING_TOKEN_STORE_MODE', 'bling_token_store_mode'),
    'token_store_path': ('token_store_path', 'BLING_TOKEN_STORE_PATH', 'bling_token_store_path'),
    'firestore_collection': ('firestore_collection', 'BLING_FIRESTORE_COLLECTION', 'bling_firestore_collection'),
    'firestore_service_account_json': ('firestore_service_account_json', 'BLING_FIRESTORE_SERVICE_ACCOUNT_JSON', 'GOOGLE_SERVICE_ACCOUNT_JSON'),
    'firestore_project_id': ('firestore_project_id', 'BLING_FIRESTORE_PROJECT_ID', 'GOOGLE_CLOUD_PROJECT'),
}

GOOGLE_SECRET_ALIASES: dict[str, tuple[str, ...]] = {
    'service_account_json': ('service_account_json', 'GOOGLE_SERVICE_ACCOUNT_JSON', 'google_service_account_json'),
    'project_id': ('project_id', 'GOOGLE_CLOUD_PROJECT', 'google_project_id'),
}


def _streamlit_module() -> Any | None:
    try:
        return importlib.import_module('streamlit')
    except Exception:
        return None


def state_store(state: MutableMapping[str, Any] | None = None) -> MutableMapping[str, Any]:
    if state is not None:
        return state
    st = _streamlit_module()
    if st is not None:
        try:
            return st.session_state
        except Exception:
            pass
    return _FALLBACK_STATE


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
    secrets = _secrets_store()
    try:
        bling = secrets.get('bling', {})
        value = _read_from_mapping(bling, aliases)
        if value:
            return value
    except Exception:
        pass
    try:
        value = _read_from_mapping(secrets, aliases)
        if value:
            return value
    except Exception:
        pass
    for alias in aliases:
        value = os.environ.get(alias) or os.environ.get(str(alias).upper())
        if value:
            return str(value).strip()
    return str(default or '').strip()


def _google_secret(name: str, default: str = '') -> str:
    aliases = GOOGLE_SECRET_ALIASES.get(name, (name,))
    secrets = _secrets_store()
    try:
        google = secrets.get('google', {})
        value = _read_from_mapping(google, aliases)
        if value:
            return value
    except Exception:
        pass
    try:
        value = _read_from_mapping(secrets, aliases)
        if value:
            return value
    except Exception:
        pass
    for alias in aliases:
        value = os.environ.get(alias) or os.environ.get(str(alias).upper())
        if value:
            return str(value).strip()
    return str(default or '').strip()


def token_store_mode() -> str:
    mode = _secret('token_store_mode', 'sqlite').lower()
    return mode if mode in {'session', 'sqlite', 'firestore'} else 'sqlite'


def token_store_path() -> Path:
    configured = _secret('token_store_path', '')
    if configured:
        return Path(configured)
    return DEFAULT_DB_PATH


def firestore_collection_name() -> str:
    return _secret('firestore_collection', DEFAULT_FIRESTORE_COLLECTION) or DEFAULT_FIRESTORE_COLLECTION


def get_user_session_id(*, state: MutableMapping[str, Any] | None = None) -> str:
    store = state_store(state)
    current = str(store.get(SESSION_ID_KEY) or '').strip()
    if current:
        return current
    current = uuid4().hex
    store[SESSION_ID_KEY] = current
    return current


def _now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _expires_at_from_token(token: dict[str, Any]) -> str:
    try:
        seconds = int(token.get('expires_in') or 0)
    except Exception:
        seconds = 0
    if seconds <= 0:
        return ''
    return (datetime.now() + timedelta(seconds=max(0, seconds - 60))).strftime('%Y-%m-%d %H:%M:%S')


def _safe_token_summary(token: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(token, dict):
        return {}
    safe: dict[str, Any] = {}
    for key, value in token.items():
        if str(key).lower() in SENSITIVE_TOKEN_KEYS:
            safe[str(key)] = '[REDACTED]'
        else:
            safe[str(key)] = value
    return safe


def _ensure_db() -> Path:
    path = token_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS bling_tokens (
                user_session_id TEXT PRIMARY KEY,
                token_json TEXT NOT NULL,
                connected_at TEXT NOT NULL,
                expires_at TEXT,
                updated_at TEXT NOT NULL
            )
            '''
        )
        conn.commit()
    return path


def _firestore_client():
    from google.cloud import firestore
    from google.oauth2 import service_account

    credentials_json = _google_secret('service_account_json', '') or _secret('firestore_service_account_json', '')
    project_id = _google_secret('project_id', '') or _secret('firestore_project_id', '')

    if credentials_json:
        data = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(data)
        return firestore.Client(project=project_id or data.get('project_id'), credentials=credentials)

    if project_id:
        return firestore.Client(project=project_id)

    return firestore.Client()


def _save_token_firestore(session_id: str, token: dict[str, Any], connected_at: str, expires_at: str) -> None:
    client = _firestore_client()
    client.collection(firestore_collection_name()).document(session_id).set(
        {
            'user_session_id': session_id,
            'token': token,
            'connected_at': connected_at,
            'expires_at': expires_at,
            'updated_at': connected_at,
        }
    )


def _load_token_firestore(session_id: str) -> tuple[dict[str, Any] | None, dict[str, str]]:
    client = _firestore_client()
    snapshot = client.collection(firestore_collection_name()).document(session_id).get()
    if not snapshot.exists:
        return None, {'store_mode': 'firestore', 'user_session_id': session_id, 'connected_at': '', 'expires_at': ''}
    data = snapshot.to_dict() or {}
    token = data.get('token')
    if not isinstance(token, dict) or not token.get('access_token'):
        return None, {
            'store_mode': 'firestore',
            'user_session_id': session_id,
            'connected_at': str(data.get('connected_at') or ''),
            'expires_at': str(data.get('expires_at') or ''),
        }
    return token, {
        'store_mode': 'firestore',
        'user_session_id': session_id,
        'connected_at': str(data.get('connected_at') or ''),
        'expires_at': str(data.get('expires_at') or ''),
    }


def _clear_token_firestore(session_id: str) -> None:
    client = _firestore_client()
    client.collection(firestore_collection_name()).document(session_id).delete()


def save_token(token: dict[str, Any], *, user_session_id: str | None = None, state: MutableMapping[str, Any] | None = None) -> None:
    if not isinstance(token, dict) or not token.get('access_token'):
        raise ValueError('Token Bling inválido para salvar.')

    store = state_store(state)
    session_id = user_session_id or get_user_session_id(state=store)
    connected_at = _now()
    expires_at = _expires_at_from_token(token)
    mode = token_store_mode()

    store[SESSION_TOKEN_KEY] = dict(token)
    store[SESSION_CONNECTED_AT_KEY] = connected_at

    if mode == 'sqlite':
        path = _ensure_db()
        with sqlite3.connect(path) as conn:
            conn.execute(
                '''
                INSERT INTO bling_tokens (user_session_id, token_json, connected_at, expires_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_session_id) DO UPDATE SET
                    token_json = excluded.token_json,
                    connected_at = excluded.connected_at,
                    expires_at = excluded.expires_at,
                    updated_at = excluded.updated_at
                ''',
                (session_id, json.dumps(token, ensure_ascii=False), connected_at, expires_at, connected_at),
            )
            conn.commit()
    elif mode == 'firestore':
        _save_token_firestore(session_id, token, connected_at, expires_at)

    add_audit_event(
        'bling_token_saved',
        area='BLING_OAUTH',
        status='OK',
        details={
            'store_mode': mode,
            'user_session_id': session_id,
            'expires_at': expires_at,
            'token_summary': _safe_token_summary(token),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def load_token(*, user_session_id: str | None = None, state: MutableMapping[str, Any] | None = None) -> tuple[dict[str, Any] | None, dict[str, str]]:
    store = state_store(state)
    session_id = user_session_id or get_user_session_id(state=store)
    current = store.get(SESSION_TOKEN_KEY)
    if isinstance(current, dict) and current.get('access_token'):
        return current, {
            'store_mode': 'session_state',
            'user_session_id': session_id,
            'connected_at': str(store.get(SESSION_CONNECTED_AT_KEY) or ''),
            'expires_at': '',
        }

    mode = token_store_mode()
    if mode == 'session':
        return None, {'store_mode': 'session_state', 'user_session_id': session_id, 'connected_at': '', 'expires_at': ''}

    if mode == 'firestore':
        token, meta = _load_token_firestore(session_id)
        if isinstance(token, dict) and token.get('access_token'):
            store[SESSION_TOKEN_KEY] = token
            store[SESSION_CONNECTED_AT_KEY] = meta.get('connected_at', '')
        return token, meta

    path = _ensure_db()
    with sqlite3.connect(path) as conn:
        row = conn.execute(
            'SELECT token_json, connected_at, expires_at FROM bling_tokens WHERE user_session_id = ?',
            (session_id,),
        ).fetchone()

    if not row:
        return None, {'store_mode': 'sqlite', 'user_session_id': session_id, 'connected_at': '', 'expires_at': ''}

    try:
        token = json.loads(row[0])
    except Exception:
        token = None

    if not isinstance(token, dict) or not token.get('access_token'):
        return None, {'store_mode': 'sqlite', 'user_session_id': session_id, 'connected_at': str(row[1] or ''), 'expires_at': str(row[2] or '')}

    store[SESSION_TOKEN_KEY] = token
    store[SESSION_CONNECTED_AT_KEY] = str(row[1] or '')
    return token, {
        'store_mode': 'sqlite',
        'user_session_id': session_id,
        'connected_at': str(row[1] or ''),
        'expires_at': str(row[2] or ''),
    }


def clear_token(*, user_session_id: str | None = None, state: MutableMapping[str, Any] | None = None) -> None:
    store = state_store(state)
    session_id = user_session_id or get_user_session_id(state=store)
    mode = token_store_mode()
    store.pop(SESSION_TOKEN_KEY, None)
    store.pop(SESSION_CONNECTED_AT_KEY, None)

    if mode == 'sqlite':
        path = _ensure_db()
        with sqlite3.connect(path) as conn:
            conn.execute('DELETE FROM bling_tokens WHERE user_session_id = ?', (session_id,))
            conn.commit()
    elif mode == 'firestore':
        _clear_token_firestore(session_id)

    add_audit_event(
        'bling_token_cleared',
        area='BLING_OAUTH',
        status='OK',
        details={'store_mode': mode, 'user_session_id': session_id, 'responsible_file': RESPONSIBLE_FILE},
    )


__all__ = ['clear_token', 'get_user_session_id', 'load_token', 'save_token', 'state_store', 'token_store_mode', 'token_store_path']
