from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Mapping

RESPONSIBLE_FILE = 'bling_app_zero/core/mapping_state.py'

EMPTY_OPTION = '(deixar vazio)'
CONFIDENCE_EMPTY = 'empty'
CONFIDENCE_REVIEW = 'review'
CONFIDENCE_HIGH = 'high'


@dataclass(frozen=True)
class MappingRequest:
    operation: str = 'universal'
    signature: str = ''
    source_columns: tuple[str, ...] = field(default_factory=tuple)
    target_columns: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None = None) -> 'MappingRequest':
        data = dict(values or {})
        return cls(
            operation=str(data.get('operation') or data.get('operacao') or 'universal').strip() or 'universal',
            signature=str(data.get('signature') or '').strip(),
            source_columns=tuple(str(item) for item in list(data.get('source_columns') or [])),
            target_columns=tuple(str(item) for item in list(data.get('target_columns') or [])),
        )

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out['source_columns'] = list(self.source_columns)
        out['target_columns'] = list(self.target_columns)
        return out


@dataclass(frozen=True)
class MappingField:
    target: str
    source: str = ''
    confidence: str = CONFIDENCE_EMPTY
    label: str = '🔴 vazio'

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class MappingState:
    request: MappingRequest = field(default_factory=MappingRequest)
    fields: tuple[MappingField, ...] = field(default_factory=tuple)
    engine: str = 'local'
    message: str = ''

    @property
    def mapping(self) -> dict[str, str]:
        return {item.target: item.source for item in self.fields}

    def to_dict(self) -> dict[str, Any]:
        return {
            'request': self.request.to_dict(),
            'fields': [item.to_dict() for item in self.fields],
            'mapping': self.mapping,
            'engine': self.engine,
            'message': self.message,
        }

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None = None) -> 'MappingState':
        data = dict(values or {})
        request_raw = data.get('request') if isinstance(data.get('request'), Mapping) else data
        raw_fields = data.get('fields') if isinstance(data.get('fields'), list) else []
        fields = tuple(
            MappingField(
                target=str(item.get('target') or ''),
                source=str(item.get('source') or ''),
                confidence=str(item.get('confidence') or CONFIDENCE_EMPTY),
                label=str(item.get('label') or '🔴 vazio'),
            )
            for item in raw_fields
            if isinstance(item, Mapping)
        )
        if not fields and isinstance(data.get('mapping'), Mapping):
            fields = tuple(MappingField(target=str(k), source=str(v)) for k, v in dict(data.get('mapping') or {}).items())
        return cls(
            request=MappingRequest.from_mapping(request_raw),
            fields=fields,
            engine=str(data.get('engine') or 'local'),
            message=str(data.get('message') or ''),
        )


__all__ = [
    'CONFIDENCE_EMPTY',
    'CONFIDENCE_HIGH',
    'CONFIDENCE_REVIEW',
    'EMPTY_OPTION',
    'MappingField',
    'MappingRequest',
    'MappingState',
]
