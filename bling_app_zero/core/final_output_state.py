from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Mapping

RESPONSIBLE_FILE = 'bling_app_zero/core/final_output_state.py'

STATUS_IDLE = 'idle'
STATUS_DONE = 'done'
STATUS_ERROR = 'error'


@dataclass(frozen=True)
class FinalOutputRequest:
    operation: str = 'universal'
    file_name: str = 'mapeiaai_planilha_final_mapeada.csv'
    contract_columns: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None = None) -> 'FinalOutputRequest':
        data = dict(values or {})
        return cls(
            operation=str(data.get('operation') or 'universal').strip() or 'universal',
            file_name=str(data.get('file_name') or 'mapeiaai_planilha_final_mapeada.csv').strip() or 'mapeiaai_planilha_final_mapeada.csv',
            contract_columns=tuple(str(item) for item in list(data.get('contract_columns') or [])),
        )

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out['contract_columns'] = list(self.contract_columns)
        return out


@dataclass(frozen=True)
class FinalOutputResult:
    status: str = STATUS_IDLE
    rows: int = 0
    columns: tuple[str, ...] = field(default_factory=tuple)
    file_name: str = ''
    csv_size_bytes: int = 0
    smartcore_score: int = 0
    message: str = ''
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.status == STATUS_DONE and not self.errors

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out['columns'] = list(self.columns)
        out['errors'] = list(self.errors)
        out['warnings'] = list(self.warnings)
        return out


@dataclass(frozen=True)
class FinalOutputState:
    request: FinalOutputRequest = field(default_factory=FinalOutputRequest)
    result: FinalOutputResult = field(default_factory=FinalOutputResult)

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None = None) -> 'FinalOutputState':
        data = dict(values or {})
        request_raw = data.get('request') if isinstance(data.get('request'), Mapping) else data
        result_raw = data.get('result') if isinstance(data.get('result'), Mapping) else {}
        return cls(
            request=FinalOutputRequest.from_mapping(request_raw),
            result=FinalOutputResult(**{k: v for k, v in dict(result_raw).items() if k in FinalOutputResult.__dataclass_fields__}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {'request': self.request.to_dict(), 'result': self.result.to_dict()}


__all__ = [
    'FinalOutputRequest',
    'FinalOutputResult',
    'FinalOutputState',
    'STATUS_DONE',
    'STATUS_ERROR',
    'STATUS_IDLE',
]
