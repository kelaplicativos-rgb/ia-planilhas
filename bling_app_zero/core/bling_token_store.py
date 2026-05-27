from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_token_store.py'
SESSION_ID_KEY = 'bling_oauth_user_session_id'
SESSION_TOKEN_KEY = 'bling_oauth_token_response'
SESSION_CONNECTED_AT_KEY = 'bling_oauth_connected_at'
DEFAULT_DB_PATH = Path('bling_user_tokens') / 'tokens.sqlite3'

SENSITIVE_TOKEN_KEYS = {
    'access_token',
    'refresh_token',
    'token',
    'authorization',
    'client_secret',
}


def _secret(name: str, default: str = '') -> str:
    try:
        bling = st.secrets.get('bling', {})
        value = bling.get(name, default) if hasattr(bling, 'get') else default
        return str(value or default).strip()
    except Exception:
        return default


def token_store_mode() -> str:
    mode = _secret('token_store_mode', 'sqlite').lower()
    return mode if mode in {'session', 'sqlite'} else 'sqlite'


def token_store_path() -> Path:
    configured = _secret('token_store_path', '')
    if configured:
        return Path(configured)
    return DEFAULT_DB_PATH


def get_user_session_id() -> str:
    current = str(st.session_state.get(SESSION_ID_KEY) or '').strip()
    if current:
        return current
    current = uuid4().hex
    st.session_state[SESSION_ID_KEY] = current
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


def save_token(token: dict[str, Any], *, user_session_id: str | None = None) -> None:
    if not isinstance(token, dict) or not token.get('access_token'):
        raise ValueError('Token Bling inválido para salvar.')

    session_id = user_session_id or get_user_session_id()
    connected_at = _now()
    expires_at = _expires_at_from_token(token)

    st.session_state[SESSION_TOKEN_KEY] = dict(token)
    st.session_state[SESSION_CONNECTED_AT_KEY] = connected_at

    if token_store_mode() == 'sqlite':
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

    add_audit_event(
        'bling_token_saved',
        area='BLING_OAUTH',
        status='OK',
        details={
            'store_mode': token_store_mode(),
            'user_session_id': session_id,
            'expires_at': expires_at,
            'token_summary': _safe_token_summary(token),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def load_token(*, user_session_id: str | None = None) -> tuple[dict[str, Any] | None, dict[str, str]]:
    session_id = user_session_id or get_user_session_id()
    current = st.session_state.get(SESSION_TOKEN_KEY)
    if isinstance(current, dict) and current.get('access_token'):
        return current, {
            'store_mode': 'session_state',
            'user_session_id': session_id,
            'connected_at': str(st.session_state.get(SESSION_CONNECTED_AT_KEY) or ''),
            'expires_at': '',
        }

    if token_store_mode() != 'sqlite':
        return None, {'store_mode': 'session_state', 'user_session_id': session_id, 'connected_at': '', 'expires_at': ''}

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

    st.session_state[SESSION_TOKEN_KEY] = token
    st.session_state[SESSION_CONNECTED_AT_KEY] = str(row[1] or '')
    return token, {
        'store_mode': 'sqlite',
        'user_session_id': session_id,
        'connected_at': str(row[1] or ''),
        'expires_at': str(row[2] or ''),
    }


def clear_token(*, user_session_id: str | None = None) -> None:
    session_id = user_session_id or get_user_session_id()
    st.session_state.pop(SESSION_TOKEN_KEY, None)
    st.session_state.pop(SESSION_CONNECTED_AT_KEY, None)

    if token_store_mode() == 'sqlite':
        path = _ensure_db()
        with sqlite3.connect(path) as conn:
            conn.execute('DELETE FROM bling_tokens WHERE user_session_id = ?', (session_id,))
            conn.commit()

    add_audit_event(
        'bling_token_cleared',
        area='BLING_OAUTH',
        status='OK',
        details={'store_mode': token_store_mode(), 'user_session_id': session_id, 'responsible_file': RESPONSIBLE_FILE},
    )


__all__ = ['clear_token', 'get_user_session_id', 'load_token', 'save_token', 'token_store_mode', 'token_store_path']
