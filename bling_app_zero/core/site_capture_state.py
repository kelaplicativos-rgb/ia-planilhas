from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Mapping

RESPONSIBLE_FILE = 'bling_app_zero/core/site_capture_state.py'

CAPTURE_MODE_CADASTRO = 'cadastro'
CAPTURE_MODE_ESTOQUE = 'estoque'
CAPTURE_MODE_PRECO = 'atualizacao_preco'
CAPTURE_MODE_UNIVERSAL = 'universal'

STATUS_IDLE = 'idle'
STATUS_RUNNING = 'running'
STATUS_DONE = 'done'
STATUS_ERROR = 'error'


@dataclass(frozen=True)
class SiteCaptureRequest:
    url: str = ''
    mode: str = CAPTURE_MODE_CADASTRO
    max_pages: int = 0
    max_products: int = 0
    use_ai_validation: bool = True
    send_to_bling: bool = False

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None = None) -> 'SiteCaptureRequest':
        data = dict(values or {})
        return cls(
            url=str(data.get('url') or data.get('site_url') or data.get('url_site') or '').strip(),
            mode=str(data.get('mode') or data.get('operation') or data.get('operacao') or data.get('direct_bling_operation_choice') or CAPTURE_MODE_CADASTRO).strip(),
            max_pages=int(data.get('max_pages') or data.get('max_paginas') or 0),
            max_products=int(data.get('max_products') or data.get('max_produtos') or 0),
            use_ai_validation=bool(data.get('use_ai_validation', True)),
            send_to_bling=bool(data.get('send_to_bling') or data.get('api_mode') or False),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SiteCaptureProgress:
    status: str = STATUS_IDLE
    current_step: str = ''
    message: str = ''
    percent: int = 0
    rows: int = 0
    pages: int = 0
    errors: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SiteCaptureResult:
    status: str = STATUS_IDLE
    rows: int = 0
    columns: tuple[str, ...] = field(default_factory=tuple)
    data_key: str = ''
    report_key: str = ''
    message: str = ''
    error: str = ''

    @property
    def ok(self) -> bool:
        return self.status == STATUS_DONE and not self.error

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SiteCaptureState:
    request: SiteCaptureRequest = field(default_factory=SiteCaptureRequest)
    progress: SiteCaptureProgress = field(default_factory=SiteCaptureProgress)
    result: SiteCaptureResult = field(default_factory=SiteCaptureResult)

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None = None) -> 'SiteCaptureState':
        data = dict(values or {})
        request_raw = data.get('request') if isinstance(data.get('request'), Mapping) else data
        progress_raw = data.get('progress') if isinstance(data.get('progress'), Mapping) else {}
        result_raw = data.get('result') if isinstance(data.get('result'), Mapping) else {}
        return cls(
            request=SiteCaptureRequest.from_mapping(request_raw),
            progress=SiteCaptureProgress(**{k: v for k, v in dict(progress_raw).items() if k in SiteCaptureProgress.__dataclass_fields__}),
            result=SiteCaptureResult(**{k: v for k, v in dict(result_raw).items() if k in SiteCaptureResult.__dataclass_fields__}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'request': self.request.to_dict(),
            'progress': self.progress.to_dict(),
            'result': self.result.to_dict(),
        }


__all__ = [
    'CAPTURE_MODE_CADASTRO',
    'CAPTURE_MODE_ESTOQUE',
    'CAPTURE_MODE_PRECO',
    'CAPTURE_MODE_UNIVERSAL',
    'STATUS_DONE',
    'STATUS_ERROR',
    'STATUS_IDLE',
    'STATUS_RUNNING',
    'SiteCaptureProgress',
    'SiteCaptureRequest',
    'SiteCaptureResult',
    'SiteCaptureState',
]
