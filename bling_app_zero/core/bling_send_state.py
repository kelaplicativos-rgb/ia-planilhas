from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Mapping

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_send_state.py'

STATUS_IDLE = 'idle'
STATUS_RUNNING = 'running'
STATUS_PAUSED = 'paused'
STATUS_DONE = 'done'
STATUS_ERROR = 'error'

OP_CADASTRO = 'cadastro'
OP_ESTOQUE = 'estoque'

CADASTRO_BATCH_SIZE = 25
ESTOQUE_BATCH_SIZE = 60


@dataclass(frozen=True)
class BlingSendRequest:
    identity: str = ''
    operation: str = OP_CADASTRO
    total: int = 0
    batch_size: int = CADASTRO_BATCH_SIZE

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None = None) -> 'BlingSendRequest':
        data = dict(values or {})
        operation = normalize_operation(data.get('operation') or OP_CADASTRO)
        return cls(
            identity=str(data.get('identity') or '').strip(),
            operation=operation,
            total=int(data.get('total') or 0),
            batch_size=int(data.get('batch_size') or batch_size_for_operation(operation)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BlingSendState:
    request: BlingSendRequest = field(default_factory=BlingSendRequest)
    offset: int = 0
    attempted: int = 0
    sent: int = 0
    failed: int = 0
    skipped: int = 0
    errors: tuple[str, ...] = field(default_factory=tuple)
    not_found_indices: tuple[int, ...] = field(default_factory=tuple)
    status: str = STATUS_IDLE
    started: bool = False
    auto_running: bool = False
    paused: bool = False

    @property
    def done(self) -> bool:
        return self.status == STATUS_DONE or self.offset >= self.request.total > 0

    @property
    def progress_ratio(self) -> float:
        return min(1.0, max(0.0, self.attempted / max(self.request.total, 1)))

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out['request'] = self.request.to_dict()
        out['errors'] = list(self.errors)
        out['not_found_indices'] = list(self.not_found_indices)
        out['done'] = self.done
        out['progress_ratio'] = self.progress_ratio
        return out

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None = None) -> 'BlingSendState':
        data = dict(values or {})
        request_raw = data.get('request') if isinstance(data.get('request'), Mapping) else data
        request = BlingSendRequest.from_mapping(request_raw)
        status = str(data.get('status') or '').strip()
        if not status:
            if bool(data.get('done')):
                status = STATUS_DONE
            elif bool(data.get('paused')):
                status = STATUS_PAUSED
            elif bool(data.get('auto_running')):
                status = STATUS_RUNNING
            else:
                status = STATUS_IDLE
        return cls(
            request=request,
            offset=int(data.get('offset') or 0),
            attempted=int(data.get('attempted') or 0),
            sent=int(data.get('sent') or 0),
            failed=int(data.get('failed') or 0),
            skipped=int(data.get('skipped') or 0),
            errors=tuple(str(item) for item in list(data.get('errors') or [])),
            not_found_indices=tuple(sorted(set(int(item) for item in list(data.get('not_found_indices') or []) if str(item).strip().lstrip('-').isdigit()))),
            status=status,
            started=bool(data.get('started')),
            auto_running=bool(data.get('auto_running')),
            paused=bool(data.get('paused')),
        )


def normalize_operation(value: object) -> str:
    text = str(value or '').strip().lower()
    if text in {'estoque', 'stock', 'atualizacao_estoque', 'atualização de estoque'}:
        return OP_ESTOQUE
    return OP_CADASTRO


def batch_size_for_operation(operation: object) -> int:
    return ESTOQUE_BATCH_SIZE if normalize_operation(operation) == OP_ESTOQUE else CADASTRO_BATCH_SIZE


__all__ = [
    'BlingSendRequest',
    'BlingSendState',
    'CADASTRO_BATCH_SIZE',
    'ESTOQUE_BATCH_SIZE',
    'OP_CADASTRO',
    'OP_ESTOQUE',
    'STATUS_DONE',
    'STATUS_ERROR',
    'STATUS_IDLE',
    'STATUS_PAUSED',
    'STATUS_RUNNING',
    'batch_size_for_operation',
    'normalize_operation',
]
