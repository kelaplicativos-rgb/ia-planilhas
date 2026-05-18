from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import os
import re

LOG_DIR = Path(os.getenv('BLING_AUDIT_LOG_DIR', 'logs/runtime'))
MAX_EVENTS = 600


def _safe_part(value: Any, limit: int = 80) -> str:
    text = str(value or '').strip().lower()[:limit]
    text = re.sub(r'[^a-z0-9_.-]+', '-', text)
    return text.strip('-') or 'unknown'


def _line(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str) + '\n'


def _write(path: Path, content: str, *, append: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = 'a' if append else 'w'
    with path.open(mode, encoding='utf-8') as handle:
        handle.write(content)


def persist_audit_event(event: dict[str, Any], events: list[dict[str, Any]]) -> None:
    try:
        session_id = _safe_part(event.get('session_id'), 48)
        date_part = _safe_part(str(event.get('timestamp') or '')[:10], 24)
        compact = list(events)[-MAX_EVENTS:]
        _write(LOG_DIR / 'sessions' / f'{date_part}_{session_id}.jsonl', _line(event), append=True)
        _write(LOG_DIR / 'latest.jsonl', ''.join(_line(item) for item in compact))
        _write(LOG_DIR / 'blinglogs_loop.jsonl', ''.join(_line(item) for item in compact))
    except Exception:
        return


__all__ = ['persist_audit_event']
