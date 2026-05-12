from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import uuid4

import streamlit as st

AUDIT_SESSION_KEY = 'audit_events'
AUDIT_SESSION_ID_KEY = 'audit_session_id'
AUDIT_MAX_ITEMS = 5000
AUDIT_EXPORT_FILENAME = 'bling_audit_trail.jsonl'

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
)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec='milliseconds')


def _safe_text(value: Any, limit: int = 1200) -> str:
    text = str(value or '').replace('\x00', '').strip()
    if len(text) > limit:
        return text[:limit] + '...'
    return text


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key or '').strip().lower()
    return any(word in normalized for word in SENSITIVE_KEYWORDS)


def _sanitize(value: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        return _safe_text(value, 400)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            safe_key = _safe_text(key, 120)
            result[safe_key] = '[REDACTED]' if _is_sensitive_key(key) else _sanitize(item, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        return [_sanitize(item, depth=depth + 1) for item in list(value)[:80]]
    if hasattr(value, 'shape') and hasattr(value, 'columns'):
        try:
            return {
                'type': type(value).__name__,
                'shape': tuple(value.shape),
                'columns': [_safe_text(col, 120) for col in list(value.columns)[:80]],
            }
        except Exception:
            return {'type': type(value).__name__}
    return _safe_text(value)


def get_audit_session_id() -> str:
    current = st.session_state.get(AUDIT_SESSION_ID_KEY)
    if current:
        return str(current)
    session_id = uuid4().hex
    st.session_state[AUDIT_SESSION_ID_KEY] = session_id
    return session_id


def add_audit_event(
    action: str,
    *,
    area: str = 'SISTEMA',
    step: str | None = None,
    status: str = 'INFO',
    details: dict[str, Any] | None = None,
) -> None:
    """Registra um movimento auditável do usuário ou do fluxo.

    Use esta função em botões, uploads, mudanças de etapa, downloads, capturas por site,
    mapeamentos e confirmações importantes. O objetivo é reconstruir a jornada do usuário
    dentro da sessão com o máximo de contexto seguro possível.
    """
    events = list(st.session_state.get(AUDIT_SESSION_KEY, []))
    event = {
        'timestamp': _now_iso(),
        'session_id': get_audit_session_id(),
        'area': _safe_text(area, 120).upper(),
        'step': _safe_text(step or st.session_state.get('bling_wizard_step') or '', 120),
        'action': _safe_text(action, 240),
        'status': _safe_text(status or 'INFO', 40).upper(),
        'details': _sanitize(details or {}),
    }
    events.append(event)
    st.session_state[AUDIT_SESSION_KEY] = events[-AUDIT_MAX_ITEMS:]


def audit_button(label: str, *, key: str, area: str, step: str | None = None, **button_kwargs: Any) -> bool:
    clicked = st.button(label, key=key, **button_kwargs)
    if clicked:
        add_audit_event(
            'button_clicked',
            area=area,
            step=step,
            details={'label': label, 'key': key},
        )
    return clicked


def audit_download_payload() -> bytes:
    events = list(st.session_state.get(AUDIT_SESSION_KEY, []))
    lines = [json.dumps(_sanitize(event), ensure_ascii=False, default=str) for event in events]
    return ('\n'.join(lines) + ('\n' if lines else '')).encode('utf-8')


def clear_audit_events() -> None:
    st.session_state[AUDIT_SESSION_KEY] = []
    add_audit_event('audit_log_cleared', area='AUDIT', status='INFO')


def get_audit_events() -> list[dict[str, Any]]:
    return list(st.session_state.get(AUDIT_SESSION_KEY, []))


__all__ = [
    'AUDIT_EXPORT_FILENAME',
    'add_audit_event',
    'audit_button',
    'audit_download_payload',
    'clear_audit_events',
    'get_audit_events',
    'get_audit_session_id',
]
