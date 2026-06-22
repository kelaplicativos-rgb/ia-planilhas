from __future__ import annotations

from typing import Any

from bling_app_zero.core.mapping_state import MappingRequest
from bling_app_zero.core.spreadsheet_mapping_center import MappingCommandResult
from bling_app_zero.core.spreadsheet_mapping_center import auto_map_columns
from bling_app_zero.core.spreadsheet_mapping_center import build_mapping_state
from bling_app_zero.core.spreadsheet_mapping_center import confidence_for
from bling_app_zero.core.spreadsheet_mapping_center import mapping_options
from bling_app_zero.core.spreadsheet_mapping_center import normalize_engine_key
from bling_app_zero.core.spreadsheet_mapping_center import normalize_selected_source
from bling_app_zero.core.spreadsheet_mapping_center import source_has_values


def _safe_frame_columns(frame: Any) -> tuple[str, ...]:
    """Return column names without evaluating pandas Index as a boolean.

    Pandas raises ``ValueError: The truth value of a Index is ambiguous`` when
    code tries to use ``frame.columns or []``. The universal mapping flow can
    receive DataFrames, dict-like objects, or empty/None values, so this helper
    normalizes all supported cases without boolean evaluation of Index objects.
    """
    columns = getattr(frame, 'columns', None)
    if columns is None:
        if isinstance(frame, dict):
            columns = frame.keys()
        elif isinstance(frame, (list, tuple, set)):
            columns = frame
        else:
            return tuple()

    try:
        return tuple(str(column) for column in list(columns))
    except Exception:
        return tuple()


def build_request_from_frames(source: Any, target: Any, *, operation: str = 'universal', signature: str = '') -> MappingRequest:
    source_columns = _safe_frame_columns(source)
    target_columns = _safe_frame_columns(target)
    return MappingRequest(operation=operation, signature=signature, source_columns=source_columns, target_columns=target_columns)


def build_full_mapping_result(
    df_source: Any,
    df_model: Any,
    *,
    operation: str = 'universal',
    signature: str = '',
    engine: str = 'local',
) -> MappingCommandResult:
    """Entrada única para anexos usando request seguro para pandas.Index."""
    mapping = auto_map_columns(df_source, df_model)
    request = build_request_from_frames(df_source, df_model, operation=operation, signature=signature)
    return build_mapping_state(request, mapping, source=df_source, engine=engine, message='Mapeamento centralizado gerado por planilha anexada.')


def normalize_key(value: object) -> str:
    return normalize_engine_key(value)


__all__ = [
    'MappingCommandResult',
    'build_full_mapping_result',
    'build_mapping_state',
    'build_request_from_frames',
    'confidence_for',
    'mapping_options',
    'normalize_key',
    'normalize_selected_source',
    'source_has_values',
]
