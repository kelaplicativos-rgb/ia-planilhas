from __future__ import annotations

from bling_app_zero.core.spreadsheet_mapping_center import MappingCommandResult
from bling_app_zero.core.spreadsheet_mapping_center import build_full_mapping_result
from bling_app_zero.core.spreadsheet_mapping_center import build_mapping_state
from bling_app_zero.core.spreadsheet_mapping_center import build_request_from_frames
from bling_app_zero.core.spreadsheet_mapping_center import confidence_for
from bling_app_zero.core.spreadsheet_mapping_center import mapping_options
from bling_app_zero.core.spreadsheet_mapping_center import normalize_engine_key
from bling_app_zero.core.spreadsheet_mapping_center import normalize_selected_source
from bling_app_zero.core.spreadsheet_mapping_center import source_has_values


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
