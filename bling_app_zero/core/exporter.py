from __future__ import annotations

import re
from typing import Sequence

import pandas as pd

from bling_app_zero.core.final_csv_exporter import (
    build_final_csv_export,
    enforce_contract,
    filename_for_operation as _default_filename_for_operation,
    final_csv_bytes,
    sanitize_final_dataframe,
)
from bling_app_zero.core.final_template_exporter import build_preserved_template_export, template_can_be_preserved

DESTINATION_MODEL_UPLOAD_OBJECT_KEY = 'destination_model_upload_object'
DESTINATION_MODEL_UPLOAD_NAME_KEY = 'destination_model_upload_name'
DESTINATION_MODEL_UPLOAD_BYTES_KEY = 'destination_model_upload_bytes'
PRESERVED_TEMPLATE_ACTIVE_KEY = 'final_preserved_template_download_active'
PRESERVED_TEMPLATE_FILENAME_KEY = 'final_preserved_template_download_filename'
PRESERVED_TEMPLATE_FORMAT_KEY = 'final_preserved_template_download_format'
PRESERVED_TEMPLATE_ERROR_KEY = 'final_preserved_template_download_error'
GTIN_COLUMNS = {'gtin', 'gtin/ean', 'ean', 'codigo de barras', 'código de barras'}
IMAGE_COLUMN_SIGNALS = ('imagem', 'imagens', 'url imagens', 'url imagens externas', 'foto', 'fotos')
URL_RE = re.compile(r'https?://[^\s|;,]+', re.I)


def _column_key(value: object) -> str:
    text = str(value or '').strip().lower()
    text = text.replace('\ufeff', '').replace('\x00', '')
    text = re.sub(r'\s+', ' ', text)
    return text


def _is_gtin_column(column: object) -> bool:
    key = _column_key(column)
    return key in GTIN_COLUMNS or key.replace(' ', '') in {'gtin', 'gtinean', 'ean'}


def _is_image_column(column: object) -> bool:
    key = _column_key(column)
    return any(signal in key for signal in IMAGE_COLUMN_SIGNALS)


def _clean_gtin(value: object) -> str:
    digits = re.sub(r'\D+', '', str(value or ''))
    return digits if len(digits) in {8, 12, 13, 14} else ''


def normalize_image_urls(value):
    text = str(value or '').strip()
    if not text:
        return ''
    parts: list[str] = []
    for match in URL_RE.findall(text.replace('|', ' ').replace(';', ' ').replace(',', ' ')):
        url = match.strip().rstrip('.,;)')
        if url and url not in parts:
            parts.append(url)
    if parts:
        return '|'.join(parts)
    raw_parts = re.split(r'[|;,]+', text)
    for item in raw_parts:
        url = item.strip()
        if url and url not in parts:
            parts.append(url)
    return '|'.join(parts)


def _sanitize_legacy_fields(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    for column in out.columns:
        if _is_gtin_column(column):
            out[column] = out[column].map(_clean_gtin)
        elif _is_image_column(column):
            out[column] = out[column].map(normalize_image_urls)
    return out.fillna('')


def _session_state():
    try:
        import streamlit as st

        return st.session_state
    except Exception:
        return None


def _current_template_upload() -> tuple[str, bytes] | None:
    state = _session_state()
    if state is None:
        return None

    name = str(state.get(DESTINATION_MODEL_UPLOAD_NAME_KEY) or '').strip()
    data = state.get(DESTINATION_MODEL_UPLOAD_BYTES_KEY)
    if name and isinstance(data, (bytes, bytearray)) and data:
        return name, bytes(data)

    uploaded = state.get(DESTINATION_MODEL_UPLOAD_OBJECT_KEY)
    if uploaded is None:
        return None
    name = str(getattr(uploaded, 'name', '') or name).strip()
    try:
        data = uploaded.getvalue()
    except Exception:
        data = None
    if not name or not data:
        return None
    data_bytes = bytes(data)
    state[DESTINATION_MODEL_UPLOAD_NAME_KEY] = name
    state[DESTINATION_MODEL_UPLOAD_BYTES_KEY] = data_bytes
    return name, data_bytes


def _remember_preserved_template(filename: str, fmt: str) -> None:
    state = _session_state()
    if state is None:
        return
    state[PRESERVED_TEMPLATE_ACTIVE_KEY] = True
    state[PRESERVED_TEMPLATE_FILENAME_KEY] = filename
    state[PRESERVED_TEMPLATE_FORMAT_KEY] = fmt
    state.pop(PRESERVED_TEMPLATE_ERROR_KEY, None)


def _clear_preserved_template(error: str | None = None) -> None:
    state = _session_state()
    if state is None:
        return
    state[PRESERVED_TEMPLATE_ACTIVE_KEY] = False
    state.pop(PRESERVED_TEMPLATE_FILENAME_KEY, None)
    state.pop(PRESERVED_TEMPLATE_FORMAT_KEY, None)
    if error:
        state[PRESERVED_TEMPLATE_ERROR_KEY] = str(error)
    else:
        state.pop(PRESERVED_TEMPLATE_ERROR_KEY, None)


def enforce_export_contract(df: pd.DataFrame | None, contract_columns: Sequence[object] | None = None) -> pd.DataFrame:
    return enforce_contract(df, contract_columns)


def sanitize_for_bling(
    df: pd.DataFrame,
    operation: str = 'global',
    contract_columns: Sequence[object] | None = None,
    explicit_empty_columns: Sequence[object] | None = None,
) -> pd.DataFrame:
    safe = sanitize_final_dataframe(
        df,
        operation='universal',
        contract_columns=contract_columns,
        explicit_empty_columns=explicit_empty_columns,
        run_download_features=False,
    )
    return _sanitize_legacy_fields(safe)


def to_bling_csv_bytes(
    df: pd.DataFrame,
    operation: str = 'global',
    contract_columns: Sequence[object] | None = None,
    explicit_empty_columns: Sequence[object] | None = None,
) -> bytes:
    safe = sanitize_for_bling(
        df,
        operation='universal',
        contract_columns=contract_columns,
        explicit_empty_columns=explicit_empty_columns,
    )
    template = _current_template_upload()
    if template is not None:
        template_name, template_bytes = template
        if template_can_be_preserved(template_name):
            try:
                preserved = build_preserved_template_export(template_name, template_bytes, safe)
                if preserved is not None:
                    _remember_preserved_template(preserved.file_name, preserved.format)
                    return preserved.file_bytes
            except Exception as exc:
                _clear_preserved_template(str(exc))
        else:
            _clear_preserved_template('Formato do modelo não preservável no download direto.')

    _clear_preserved_template()
    return final_csv_bytes(
        safe,
        operation='universal',
        contract_columns=contract_columns,
        explicit_empty_columns=explicit_empty_columns,
        run_download_features=False,
    )


def filename_for_operation(operation: str) -> str:
    state = _session_state()
    if state is not None and bool(state.get(PRESERVED_TEMPLATE_ACTIVE_KEY)):
        preserved_name = str(state.get(PRESERVED_TEMPLATE_FILENAME_KEY) or '').strip()
        if preserved_name:
            return preserved_name
    return _default_filename_for_operation(operation)


__all__ = [
    'build_final_csv_export',
    'enforce_export_contract',
    'filename_for_operation',
    'normalize_image_urls',
    'sanitize_for_bling',
    'to_bling_csv_bytes',
]
