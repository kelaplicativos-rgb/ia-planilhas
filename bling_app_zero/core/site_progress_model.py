from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any, Mapping

RESPONSIBLE_FILE = 'bling_app_zero/core/site_progress_model.py'

MAX_PROGRESS_EVENTS = 200


def safe_text(value: object) -> str:
    if value is None:
        return ''
    try:
        # Evita importar pandas no core só para isna.
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


@dataclass(frozen=True)
class SiteProgressEvent:
    stage: str = ''
    message: str = ''
    progress: float = 0.0
    time: str = ''
    urls_found: int = 0
    visited_pages: int = 0
    processed: int = 0
    rows: int = 0
    errors: int = 0
    elapsed_seconds: float = 0.0
    queued_pages: int = 0
    max_pages: int = 0
    max_products: int = 0
    seconds_left: float = 0.0
    current_url: str = ''
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any] | None = None, *, now: str | None = None) -> 'SiteProgressEvent':
        data = dict(payload or {})
        progress = data.get('progress', data.get('progress_value', 0.0))
        found_products = data.get('found_products') or data.get('urls_found') or data.get('total') or data.get('deep_capture_found_products') or 0
        return cls(
            stage=safe_text(data.get('stage')),
            message=safe_text(data.get('message')),
            progress=max(0.0, min(1.0, float(progress or 0.0))),
            time=safe_text(data.get('time') or now or time.strftime('%H:%M:%S')),
            urls_found=safe_int(found_products),
            visited_pages=safe_int(data.get('visited_pages') or data.get('deep_capture_visited_pages') or 0),
            processed=safe_int(data.get('processed') or data.get('scanned_pages') or data.get('deep_capture_scanned_pages') or 0),
            rows=safe_int(data.get('rows') or data.get('found') or found_products or 0),
            errors=safe_int(data.get('errors') or 0),
            elapsed_seconds=float(data.get('total_seconds') or data.get('discovery_seconds') or data.get('elapsed_seconds') or 0.0),
            queued_pages=safe_int(data.get('queued_pages') or 0),
            max_pages=safe_int(data.get('max_pages') or 0),
            max_products=safe_int(data.get('max_products') or 0),
            seconds_left=float(data.get('seconds_left') or 0.0),
            current_url=safe_text(data.get('current_url') or ''),
            extra={
                str(k): v
                for k, v in data.items()
                if k not in {
                    'stage',
                    'message',
                    'progress',
                    'progress_value',
                    'time',
                    'found_products',
                    'urls_found',
                    'total',
                    'deep_capture_found_products',
                    'visited_pages',
                    'deep_capture_visited_pages',
                    'processed',
                    'scanned_pages',
                    'deep_capture_scanned_pages',
                    'rows',
                    'found',
                    'errors',
                    'total_seconds',
                    'discovery_seconds',
                    'elapsed_seconds',
                    'queued_pages',
                    'max_pages',
                    'max_products',
                    'seconds_left',
                    'current_url',
                }
            },
        )

    def to_payload(self) -> dict[str, Any]:
        out = asdict(self)
        extra = out.pop('extra', {}) or {}
        out.update(extra)
        return out

    def to_row(self) -> dict[str, str]:
        current = safe_text(self.current_url)
        if len(current) > 64:
            current = current[:61] + '...'
        return {
            'Hora': safe_text(self.time),
            'Etapa': safe_text(self.stage),
            'Mensagem': safe_text(self.message),
            'Produtos': safe_text(self.urls_found),
            'Visitadas': safe_text(self.visited_pages),
            'Lidas': safe_text(self.processed),
            'Fila': safe_text(self.queued_pages),
            'Meta páginas': safe_text(self.max_pages),
            'Meta produtos': safe_text(self.max_products),
            'Tempo': safe_text(self.elapsed_seconds),
            'Restante': safe_text(self.seconds_left),
            'URL atual': current,
            'Falhas': safe_text(self.errors),
        }


@dataclass(frozen=True)
class SiteProgressState:
    events: tuple[SiteProgressEvent, ...] = field(default_factory=tuple)

    @property
    def last(self) -> SiteProgressEvent | None:
        return self.events[-1] if self.events else None

    def append(self, payload: Mapping[str, Any] | None = None) -> 'SiteProgressState':
        event = SiteProgressEvent.from_payload(payload)
        return SiteProgressState(tuple((list(self.events) + [event])[-MAX_PROGRESS_EVENTS:]))

    def reset(self) -> 'SiteProgressState':
        return SiteProgressState()

    def rows(self) -> list[dict[str, str]]:
        return [event.to_row() for event in self.events]

    def to_dict(self) -> dict[str, Any]:
        return {'events': [event.to_payload() for event in self.events], 'last': self.last.to_payload() if self.last else {}}

    @classmethod
    def from_log(cls, log: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None = None) -> 'SiteProgressState':
        events = [SiteProgressEvent.from_payload(item) for item in list(log or [])]
        return cls(tuple(events[-MAX_PROGRESS_EVENTS:]))


@dataclass(frozen=True)
class SiteProgressMetrics:
    stage: str = 'Buscando'
    urls_found: int = 0
    visited_pages: int = 0
    processed: int = 0
    elapsed_seconds: int = 0
    message: str = ''
    queued_pages: int = 0
    max_pages: int = 0
    max_products: int = 0
    seconds_left: float = 0.0
    current_url: str = ''

    @classmethod
    def from_event(cls, event: SiteProgressEvent | None, *, elapsed_seconds: int = 0) -> 'SiteProgressMetrics':
        if event is None:
            return cls(elapsed_seconds=elapsed_seconds)
        return cls(
            stage=event.stage or 'Buscando',
            urls_found=event.urls_found,
            visited_pages=event.visited_pages,
            processed=event.processed,
            elapsed_seconds=int(elapsed_seconds or event.elapsed_seconds or 0),
            message=event.message or event.stage or '',
            queued_pages=event.queued_pages,
            max_pages=event.max_pages,
            max_products=event.max_products,
            seconds_left=event.seconds_left,
            current_url=event.current_url,
        )


__all__ = [
    'MAX_PROGRESS_EVENTS',
    'SiteProgressEvent',
    'SiteProgressMetrics',
    'SiteProgressState',
    'safe_int',
    'safe_text',
]