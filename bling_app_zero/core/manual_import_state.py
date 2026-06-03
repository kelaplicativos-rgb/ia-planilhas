from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Mapping

RESPONSIBLE_FILE = 'bling_app_zero/core/manual_import_state.py'

STATUS_IDLE = 'idle'
STATUS_READY = 'ready'
STATUS_DONE = 'done'
STATUS_ERROR = 'error'

SOURCE_FILE = 'arquivo'
SOURCE_PASTED = 'colado'
SOURCE_UNKNOWN = 'desconhecido'


@dataclass(frozen=True)
class ManualImportRequest:
    operation: str = 'universal'
    source_type: str = SOURCE_UNKNOWN
    raw_label: str = ''
    requested_columns: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None = None) -> 'ManualImportRequest':
        data = dict(values or {})
        requested = data.get('requested_columns') or data.get('columns') or ()
        if isinstance(requested, str):
            requested_columns = tuple(part.strip() for part in requested.split(',') if part.strip())
        else:
            requested_columns = tuple(str(item) for item in list(requested or []))
        return cls(
            operation=str(data.get('operation') or data.get('operacao') or data.get('direct_bling_operation_choice') or 'universal').strip() or 'universal',
            source_type=str(data.get('source_type') or SOURCE_UNKNOWN).strip() or SOURCE_UNKNOWN,
            raw_label=str(data.get('raw_label') or data.get('label') or '').strip(),
            requested_columns=requested_columns,
        )

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out['requested_columns'] = list(self.requested_columns)
        return out


@dataclass(frozen=True)
class ManualImportResult:
    status: str = STATUS_IDLE
    rows: int = 0
    columns: tuple[str, ...] = field(default_factory=tuple)
    data_key: str = ''
    origin_key: str = ''
    raw_label: str = ''
    message: str = ''
    error: str = ''
    recovery_messages: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.status == STATUS_DONE and not self.error and self.rows > 0

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out['columns'] = list(self.columns)
        out['recovery_messages'] = list(self.recovery_messages)
        return out


@dataclass(frozen=True)
class ManualImportState:
    request: ManualImportRequest = field(default_factory=ManualImportRequest)
    result: ManualImportResult = field(default_factory=ManualImportResult)

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None = None) -> 'ManualImportState':
        data = dict(values or {})
        request_raw = data.get('request') if isinstance(data.get('request'), Mapping) else data
        result_raw = data.get('result') if isinstance(data.get('result'), Mapping) else {}
        return cls(
            request=ManualImportRequest.from_mapping(request_raw),
            result=ManualImportResult(**{k: v for k, v in dict(result_raw).items() if k in ManualImportResult.__dataclass_fields__}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {'request': self.request.to_dict(), 'result': self.result.to_dict()}


__all__ = [
    'ManualImportRequest',
    'ManualImportResult',
    'ManualImportState',
    'SOURCE_FILE',
    'SOURCE_PASTED',
    'SOURCE_UNKNOWN',
    'STATUS_DONE',
    'STATUS_ERROR',
    'STATUS_IDLE',
    'STATUS_READY',
]
