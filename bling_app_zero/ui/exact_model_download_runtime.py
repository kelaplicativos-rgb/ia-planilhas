from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.exporter import enforce_export_contract
from bling_app_zero.core.files import read_uploaded_file
from bling_app_zero.core.final_csv_exporter import exact_contract_columns
from bling_app_zero.core.text import normalize_key

RESPONSIBLE_FILE = 'bling_app_zero/ui/exact_model_download_runtime.py'
PATCH_ATTR = '_exact_model_download_runtime_unico_v3'
ORIGINAL_ATTR = '_exact_model_original_download_dataframe_for_contract'
MODEL_BYTES_KEY = 'destination_model_upload_bytes'
MODEL_NAME_KEY = 'destination_model_upload_name'

MODEL_DF_KEYS = (
    'mapeiaai_final_contract_df',
    'home_modelo_universal_df',
    'df_modelo_universal',
    'modelo_universal_df',
    'home_modelo_estoque_df',
    'df_modelo_estoque',
    'modelo_estoque_df',
    'estoque_wizard_df_modelo',
    'home_modelo_cadastro_df',
    'df_modelo_cadastro',
    'modelo_cadastro_df',
    'home_modelo_atualizacao_preco_df',
    'df_modelo_atualizacao_preco',
    'modelo_atualizacao_preco_df',
)


class NamedBytesIO(BytesIO):
    def __init__(self, data: bytes, name: str):
        super().__init__(data)
        self.name = name


def _columns_from_df(value: Any) -> list[str]:
    if isinstance(value, pd.DataFrame) and len(value.columns) > 0:
        return exact_contract_columns(value.columns)
    return []


def _columns_from_upload_bytes() -> list[str]:
    data = st.session_state.get(MODEL_BYTES_KEY)
    if not isinstance(data, (bytes, bytearray)) or not data:
        return []
    name = str(st.session_state.get(MODEL_NAME_KEY) or 'modelo.csv')
    try:
        df_model = read_uploaded_file(NamedBytesIO(bytes(data), name))
    except Exception as exc:
        add_audit_event('exact_model_read_failed', area='DOWNLOAD', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
        return []
    return _columns_from_df(df_model)


def active_model_columns() -> tuple[list[str], str]:
    columns = _columns_from_upload_bytes()
    if columns:
        return columns, MODEL_BYTES_KEY
    for key in MODEL_DF_KEYS:
        columns = _columns_from_df(st.session_state.get(key))
        if columns:
            return columns, key
    return [], ''


def _adapt(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    source = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    by_key: dict[str, str] = {}
    for column in source.columns:
        key = normalize_key(column)
        if key and key not in by_key:
            by_key[key] = column
    out = pd.DataFrame(index=source.index)
    for target in columns:
        if target in source.columns:
            out[target] = source[target]
            continue
        src = by_key.get(normalize_key(target))
        out[target] = source[src] if src in source.columns else ''
    return enforce_export_contract(out, columns).fillna('')


def install_exact_model_download_runtime() -> bool:
    try:
        from bling_app_zero.ui import home_download
    except Exception:
        return False
    if getattr(home_download, PATCH_ATTR, False):
        return False
    original = getattr(home_download, ORIGINAL_ATTR, None)
    if original is None:
        original = home_download.download_dataframe_for_contract
        setattr(home_download, ORIGINAL_ATTR, original)

    def download_dataframe_for_contract(df: pd.DataFrame, operation: str):
        columns, source_key = active_model_columns()
        if columns:
            adapted = _adapt(df, columns)
            add_audit_event('exact_attached_model_contract_applied', area='DOWNLOAD', status='OK', details={'source_key': source_key, 'columns_count': len(columns), 'columns': columns, 'responsible_file': RESPONSIBLE_FILE})
            return adapted, True, columns
        return original(df, operation)

    home_download.download_dataframe_for_contract = download_dataframe_for_contract
    setattr(home_download, PATCH_ATTR, True)
    return True


__all__ = ['install_exact_model_download_runtime', 'active_model_columns']
