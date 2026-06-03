from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from bling_app_zero.core.mapping_state import (
    CONFIDENCE_EMPTY,
    CONFIDENCE_HIGH,
    CONFIDENCE_REVIEW,
    EMPTY_OPTION,
    MappingField,
    MappingRequest,
    MappingState,
)

RESPONSIBLE_FILE = 'bling_app_zero/core/mapping_engine.py'


@dataclass(frozen=True)
class MappingCommandResult:
    state: MappingState
    rows: tuple[dict[str, str], ...]
    message: str = ''
    needs_rerun: bool = False


def normalize_key(value: object) -> str:
    return re.sub(r'[^a-z0-9]+', '', str(value or '').lower())


def source_has_values(source: Any, source_column: str) -> bool:
    try:
        columns = getattr(source, 'columns', [])
        if source_column in columns:
            return bool(source[source_column].astype(str).str.strip().ne('').any())
    except Exception:
        pass
    return False


def confidence_for(target: str, source_column: str, source: Any = None) -> tuple[str, str]:
    if not source_column:
        return CONFIDENCE_EMPTY, '🔴 vazio'
    target_key = normalize_key(target)
    source_key = normalize_key(source_column)
    if target_key and (target_key == source_key or target_key in source_key or source_key in target_key):
        return CONFIDENCE_HIGH, '🟢 alto'
    if source is not None and source_has_values(source, source_column):
        return CONFIDENCE_REVIEW, '🟡 revisar'
    return CONFIDENCE_EMPTY, '🔴 vazio'


def normalize_selected_source(value: object) -> str:
    text = str(value or '').strip()
    return '' if text == EMPTY_OPTION else text


def build_mapping_state(
    request: MappingRequest,
    mapping: Mapping[str, str] | None = None,
    *,
    source: Any = None,
    engine: str = 'local',
    message: str = '',
) -> MappingCommandResult:
    current = {str(k): normalize_selected_source(v) for k, v in dict(mapping or {}).items()}
    fields: list[MappingField] = []
    rows: list[dict[str, str]] = []
    for target in request.target_columns:
        target_name = str(target)
        selected = current.get(target_name, '')
        confidence, label = confidence_for(target_name, selected, source)
        field = MappingField(target=target_name, source=selected, confidence=confidence, label=label)
        fields.append(field)
        rows.append({'Farol': label, 'Contrato final': target_name, 'Origem usada': selected or '(vazio)'})
    state = MappingState(request=request, fields=tuple(fields), engine=engine or 'local', message=message)
    return MappingCommandResult(state=state, rows=tuple(rows), message=message, needs_rerun=False)


def mapping_options(source_columns: tuple[str, ...] | list[str]) -> list[str]:
    return [EMPTY_OPTION] + [str(column) for column in list(source_columns or [])]


def build_request_from_frames(source: Any, target: Any, *, operation: str = 'universal', signature: str = '') -> MappingRequest:
    source_columns = tuple(str(col) for col in list(getattr(source, 'columns', []) or []))
    target_columns = tuple(str(col) for col in list(getattr(target, 'columns', []) or []))
    return MappingRequest(operation=operation, signature=signature, source_columns=source_columns, target_columns=target_columns)


__all__ = [
    'MappingCommandResult',
    'build_mapping_state',
    'build_request_from_frames',
    'confidence_for',
    'mapping_options',
    'normalize_key',
    'normalize_selected_source',
    'source_has_values',
]
