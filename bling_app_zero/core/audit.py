from __future__ import annotations

import hashlib
import importlib
import json
from collections.abc import MutableMapping
from datetime import datetime
from typing import Any
from uuid import uuid4

from bling_app_zero.core.audit_file_store import persist_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/core/audit.py'
AUDIT_SESSION_KEY = 'audit_events'
AUDIT_SESSION_ID_KEY = 'audit_session_id'
AUDIT_STATE_SNAPSHOT_KEY = 'audit_state_snapshot'
AUDIT_MAX_ITEMS = 600
AUDIT_EXPORT_FILENAME = 'bling_audit_trail.jsonl'
REDACTED_VALUE = '[REDACTED]'

SENSITIVE_KEYWORDS = (
    'password',
    'senha',
    'secret',
    'token',
    'client_secret',
    'authorization',
    'cookie',
    'api_key',
    'apikey',
    'credential',
    'credentials',
    'auth',
    'security_code',
    'captcha',
    '2fa',
    'ephemeral',
)

IGNORED_STATE_KEYS = {
    AUDIT_SESSION_KEY,
    AUDIT_SESSION_ID_KEY,
    AUDIT_STATE_SNAPSHOT_KEY,
    'logs',
    'debug_home_area_open',
}

IGNORED_STATE_PREFIXES = (
    'audit_',
    'debug_',
    '_streamlit',
    'FormSubmitter:',
    'support_diagnostic_zip_bytes',
    'support_diagnostic_bytes',
)

_FALLBACK_STATE: dict[str, Any] = {}


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


def _now_iso() -> str:
    return datetime.now().isoformat(timespec='milliseconds')


def _safe_text(value: Any, limit: int = 600) -> str:
    text = str(value or '').replace('\x00', '').strip()
    if len(text) > limit:
        return text[:limit] + '...'
    return text


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key or '').strip().lower()
    return any(word in normalized for word in SENSITIVE_KEYWORDS)


def _should_ignore_state_key(key: Any) -> bool:
    text = str(key or '')
    return text in IGNORED_STATE_KEYS or any(text.startswith(prefix) for prefix in IGNORED_STATE_PREFIXES)


def _sanitize(value: Any, *, depth: int = 0) -> Any:
    if depth > 3:
        return _safe_text(value, 240)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in list(value.items())[:60]:
            safe_key = _safe_text(key, 100)
            result[safe_key] = REDACTED_VALUE if _is_sensitive_key(key) else _sanitize(item, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        return [_sanitize(item, depth=depth + 1) for item in list(value)[:40]]
    if hasattr(value, 'shape') and hasattr(value, 'columns'):
        try:
            return {
                'type': type(value).__name__,
                'shape': tuple(value.shape),
                'columns': [_safe_text(col, 90) for col in list(value.columns)[:50]],
            }
        except Exception:
            return {'type': type(value).__name__}
    return _safe_text(type(value).__name__)


def _fingerprint(value: Any) -> str:
    try:
        payload = json.dumps(_sanitize(value), ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        payload = _safe_text(value, 1000)
    return hashlib.sha256(payload.encode('utf-8', errors='ignore')).hexdigest()


def _state_value_summary(value: Any, *, key: Any | None = None) -> dict[str, Any]:
    if key is not None and _is_sensitive_key(key):
        return {
            'type': type(value).__name__,
            'fingerprint': hashlib.sha256(REDACTED_VALUE.encode('utf-8')).hexdigest(),
            'value': REDACTED_VALUE,
        }
    sanitized = _sanitize(value)
    return {
        'type': type(value).__name__,
        'fingerprint': _fingerprint(value),
        'value': sanitized,
    }


def _capture_state_snapshot(state: MutableMapping[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    store = state if state is not None else _state_store()
    snapshot: dict[str, dict[str, Any]] = {}
    for key, value in store.items():
        if _should_ignore_state_key(key):
            continue
        safe_key = _safe_text(key, 140)
        snapshot[safe_key] = _state_value_summary(value, key=key)
    return snapshot


def get_audit_session_id(state: MutableMapping[str, Any] | None = None) -> str:
    store = state if state is not None else _state_store()
    current = store.get(AUDIT_SESSION_ID_KEY)
    if current:
        return str(current)
    session_id = uuid4().hex
    store[AUDIT_SESSION_ID_KEY] = session_id
    return session_id


def add_audit_event(
    action: str,
    *,
    area: str = 'SISTEMA',
    step: str | None = None,
    status: str = 'INFO',
    details: dict[str, Any] | None = None,
    state: MutableMapping[str, Any] | None = None,
) -> None:
    store = state if state is not None else _state_store()
    events = store.get(AUDIT_SESSION_KEY, [])
    if not isinstance(events, list):
        events = []
    event = {
        'timestamp': _now_iso(),
        'session_id': get_audit_session_id(store),
        'area': _safe_text(area, 100).upper(),
        'step': _safe_text(step or store.get('bling_wizard_step') or '', 100),
        'action': _safe_text(action, 180),
        'status': _safe_text(status or 'INFO', 40).upper(),
        'details': _sanitize(details or {}),
    }
    events.append(event)
    if len(events) > AUDIT_MAX_ITEMS:
        del events[:-AUDIT_MAX_ITEMS]
    store[AUDIT_SESSION_KEY] = events
    persist_audit_event(event, events)


def audit_session_state_changes(stage: str = 'runtime', *, state: MutableMapping[str, Any] | None = None) -> None:
    store = state if state is not None else _state_store()
    previous = store.get(AUDIT_STATE_SNAPSHOT_KEY)
    current = _capture_state_snapshot(store)
    if not isinstance(previous, dict):
        store[AUDIT_STATE_SNAPSHOT_KEY] = current
        add_audit_event('state_snapshot_initialized', area='AUDIT', details={'stage': stage, 'keys': len(current)}, state=store)
        return

    previous_keys = set(previous.keys())
    current_keys = set(current.keys())
    added = sorted(current_keys - previous_keys)
    removed = sorted(previous_keys - current_keys)
    common = sorted(previous_keys & current_keys)

    for key in added[:80]:
        add_audit_event('field_added', area='STATE', details={'stage': stage, 'key': key, 'new': current.get(key)}, state=store)
    for key in removed[:80]:
        add_audit_event('field_removed', area='STATE', details={'stage': stage, 'key': key, 'old': previous.get(key)}, state=store)
    for key in common[:140]:
        old = previous.get(key, {})
        new = current.get(key, {})
        if old.get('fingerprint') == new.get('fingerprint'):
            continue
        add_audit_event('field_changed', area='STATE', details={'stage': stage, 'key': key, 'old': old, 'new': new}, state=store)

    store[AUDIT_STATE_SNAPSHOT_KEY] = current


def audit_button(label: str, *, key: str, area: str, step: str | None = None, **button_kwargs: Any) -> bool:
    st = _streamlit_module()
    if st is None:
        return False
    clicked = st.button(label, key=key, **button_kwargs)
    if clicked:
        add_audit_event('button_clicked', area=area, step=step, details={'label': label, 'key': key})
    return bool(clicked)


def audit_download_payload(state: MutableMapping[str, Any] | None = None) -> bytes:
    store = state if state is not None else _state_store()
    events = list(store.get(AUDIT_SESSION_KEY, []))
    lines = [json.dumps(_sanitize(event), ensure_ascii=False, default=str) for event in events]
    return ('\n'.join(lines) + ('\n' if lines else '')).encode('utf-8')


def clear_audit_events(state: MutableMapping[str, Any] | None = None) -> None:
    store = state if state is not None else _state_store()
    store[AUDIT_SESSION_KEY] = []
    add_audit_event('audit_log_cleared', area='AUDIT', status='INFO', state=store)


def get_audit_events(state: MutableMapping[str, Any] | None = None) -> list[dict[str, Any]]:
    store = state if state is not None else _state_store()
    return list(store.get(AUDIT_SESSION_KEY, []))


__all__ = [
    'AUDIT_EXPORT_FILENAME',
    'add_audit_event',
    'audit_button',
    'audit_download_payload',
    'audit_session_state_changes',
    'clear_audit_events',
    'get_audit_events',
    'get_audit_session_id',
]
