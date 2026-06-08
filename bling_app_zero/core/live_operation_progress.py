from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Mapping

RESPONSIBLE_FILE = 'bling_app_zero/core/live_operation_progress.py'

LIVE_OPERATION_STATE_KEY = 'live_operation_progress_state_v1'
LIVE_OPERATION_LOG_KEY = 'live_operation_progress_log_v1'
LIVE_OPERATION_LAST_KEY = 'live_operation_progress_last_v1'
LIVE_OPERATION_LAST_SEEN_AT_KEY = 'live_operation_progress_last_seen_at_v1'
MAX_LIVE_EVENTS = 240


def _now_label() -> str:
    return time.strftime('%H:%M:%S')


def safe_text(value: object) -> str:
    if value is None:
        return ''
    try:
        if value != value:  # NaN
            return ''
    except Exception:
        pass
    return str(value)


def safe_int(value: object) -> int:
    try:
        if value is None or value == '':
            return 0
        return int(float(value))
    except Exception:
        return 0


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None or value == '':
            return default
        return float(value)
    except Exception:
        return default


def _clamp_progress(value: object) -> float:
    progress = safe_float(value, 0.0)
    if progress > 1:
        progress = progress / 100.0
    return max(0.0, min(1.0, progress))


@dataclass(frozen=True)
class LiveOperationEvent:
    area: str = ''
    operation: str = ''
    stage: str = ''
    message: str = ''
    progress: float = 0.0
    processed: int = 0
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    current_item: str = ''
    current_url: str = ''
    checkpoint: str = ''
    elapsed_seconds: float = 0.0
    time: str = ''
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any] | None = None) -> 'LiveOperationEvent':
        data = dict(payload or {})
        processed = data.get('processed') or data.get('attempted') or data.get('rows_done') or data.get('scanned_pages') or data.get('deep_capture_scanned_pages') or 0
        total = data.get('total') or data.get('rows_total') or data.get('max_products') or data.get('max_pages') or 0
        success = data.get('success') or data.get('sent') or data.get('ok') or data.get('urls_found') or data.get('found_products') or data.get('deep_capture_found_products') or 0
        failed = data.get('failed') or data.get('errors') or 0
        progress = data.get('progress', data.get('progress_value', 0.0))
        if not progress and safe_int(total) > 0:
            progress = safe_int(processed) / max(safe_int(total), 1)
        known_keys = {
            'area', 'operation', 'stage', 'message', 'progress', 'progress_value', 'processed', 'attempted', 'rows_done',
            'scanned_pages', 'deep_capture_scanned_pages', 'total', 'rows_total', 'max_products', 'max_pages',
            'success', 'sent', 'ok', 'urls_found', 'found_products', 'deep_capture_found_products', 'failed', 'errors',
            'skipped', 'current_item', 'current_url', 'checkpoint', 'elapsed_seconds', 'total_seconds', 'time',
        }
        return cls(
            area=safe_text(data.get('area') or data.get('scope') or 'GERAL'),
            operation=safe_text(data.get('operation') or data.get('operacao') or ''),
            stage=safe_text(data.get('stage') or 'Processando'),
            message=safe_text(data.get('message') or ''),
            progress=_clamp_progress(progress),
            processed=safe_int(processed),
            total=safe_int(total),
            success=safe_int(success),
            failed=safe_int(failed),
            skipped=safe_int(data.get('skipped') or 0),
            current_item=safe_text(data.get('current_item') or data.get('item') or ''),
            current_url=safe_text(data.get('current_url') or ''),
            checkpoint=safe_text(data.get('checkpoint') or ''),
            elapsed_seconds=safe_float(data.get('elapsed_seconds') or data.get('total_seconds') or 0.0),
            time=safe_text(data.get('time') or _now_label()),
            extra={str(k): v for k, v in data.items() if k not in known_keys},
        )

    def to_payload(self) -> dict[str, Any]:
        out = asdict(self)
        extra = out.pop('extra', {}) or {}
        out.update(extra)
        return out

    def to_row(self) -> dict[str, str]:
        current = self.current_item or self.current_url
        if len(current) > 72:
            current = current[:69] + '...'
        return {
            'Hora': safe_text(self.time),
            'Área': safe_text(self.area),
            'Operação': safe_text(self.operation),
            'Etapa': safe_text(self.stage),
            'Mensagem': safe_text(self.message),
            'Processados': safe_text(self.processed),
            'Total': safe_text(self.total),
            'Sucesso': safe_text(self.success),
            'Falhas': safe_text(self.failed),
            'Ignorados': safe_text(self.skipped),
            'Checkpoint': safe_text(self.checkpoint),
            'Item atual': safe_text(current),
        }


@dataclass(frozen=True)
class LiveOperationState:
    events: tuple[LiveOperationEvent, ...] = field(default_factory=tuple)

    @property
    def last(self) -> LiveOperationEvent | None:
        return self.events[-1] if self.events else None

    def append(self, payload: Mapping[str, Any] | None = None) -> 'LiveOperationState':
        event = LiveOperationEvent.from_payload(payload)
        return LiveOperationState(tuple((list(self.events) + [event])[-MAX_LIVE_EVENTS:]))

    def to_dict(self) -> dict[str, Any]:
        return {'events': [event.to_payload() for event in self.events], 'last': self.last.to_payload() if self.last else {}}

    def rows(self) -> list[dict[str, str]]:
        return [event.to_row() for event in self.events]

    @classmethod
    def from_log(cls, log: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None = None) -> 'LiveOperationState':
        events = [LiveOperationEvent.from_payload(item) for item in list(log or [])]
        return cls(tuple(events[-MAX_LIVE_EVENTS:]))


def _streamlit_state():
    try:
        import streamlit as st  # type: ignore
        return st.session_state
    except Exception:
        return None


def _state_from_session(session: Any | None = None) -> LiveOperationState:
    session = session if session is not None else _streamlit_state()
    if session is None:
        return LiveOperationState()
    stored = session.get(LIVE_OPERATION_STATE_KEY)
    if isinstance(stored, dict) and isinstance(stored.get('events'), list):
        return LiveOperationState.from_log(stored.get('events'))
    return LiveOperationState.from_log(session.get(LIVE_OPERATION_LOG_KEY) or [])


def _sync_state(state: LiveOperationState, session: Any | None = None) -> None:
    session = session if session is not None else _streamlit_state()
    if session is None:
        return
    data = state.to_dict()
    session[LIVE_OPERATION_STATE_KEY] = data
    session[LIVE_OPERATION_LOG_KEY] = data.get('events', [])
    session[LIVE_OPERATION_LAST_KEY] = data.get('last', {})
    session[LIVE_OPERATION_LAST_SEEN_AT_KEY] = time.time()


def reset_live_operation_progress(session: Any | None = None) -> None:
    _sync_state(LiveOperationState(), session=session)


def append_live_operation_progress(payload: Mapping[str, Any] | None = None, session: Any | None = None) -> dict[str, Any]:
    state = _state_from_session(session).append(payload or {})
    _sync_state(state, session=session)
    return state.to_dict().get('last', {})


def get_live_operation_state(session: Any | None = None) -> LiveOperationState:
    return _state_from_session(session)


def get_live_operation_last_seen_at(session: Any | None = None) -> float:
    session = session if session is not None else _streamlit_state()
    if session is None:
        return 0.0
    return safe_float(session.get(LIVE_OPERATION_LAST_SEEN_AT_KEY) or 0.0)


def make_live_progress_callback(
    *,
    area: str,
    operation: str = '',
    progress_bar: Any | None = None,
    status_box: Any | None = None,
    base_payload: Mapping[str, Any] | None = None,
) -> Callable[[Mapping[str, Any]], None]:
    base = dict(base_payload or {})

    def _callback(payload: Mapping[str, Any] | None = None) -> None:
        data = dict(base)
        data.update(dict(payload or {}))
        data.setdefault('area', area)
        data.setdefault('operation', operation)
        last = append_live_operation_progress(data)
        progress = _clamp_progress(last.get('progress') or data.get('progress') or 0.0)
        stage = safe_text(last.get('stage') or data.get('stage') or 'Processando')
        message = safe_text(last.get('message') or data.get('message') or '')
        processed = safe_int(last.get('processed') or data.get('processed') or data.get('attempted') or 0)
        total = safe_int(last.get('total') or data.get('total') or 0)
        text = f'{stage} · {int(progress * 100)}%'
        if total:
            text = f'{text} · {processed}/{total}'
        try:
            if progress_bar is not None:
                progress_bar.progress(progress, text=text)
        except Exception:
            pass
        try:
            if status_box is not None:
                if hasattr(status_box, 'info'):
                    status_box.info(message or stage)
                else:
                    status_box.caption(message or stage)
        except Exception:
            try:
                status_box.caption(message or stage)
            except Exception:
                pass

    return _callback


__all__ = [
    'LIVE_OPERATION_LAST_KEY',
    'LIVE_OPERATION_LAST_SEEN_AT_KEY',
    'LIVE_OPERATION_LOG_KEY',
    'LIVE_OPERATION_STATE_KEY',
    'LiveOperationEvent',
    'LiveOperationState',
    'append_live_operation_progress',
    'get_live_operation_last_seen_at',
    'get_live_operation_state',
    'make_live_progress_callback',
    'reset_live_operation_progress',
    'safe_float',
    'safe_int',
    'safe_text',
]
