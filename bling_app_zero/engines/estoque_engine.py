from __future__ import annotations

import pandas as pd

from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.core.mapping import apply_mapping, auto_map_columns
from bling_app_zero.core.text import normalize_key

DEFAULT_ESTOQUE_COLUMNS = [
    'Código',
    'Descrição',
    'Preço unitário (OBRIGATÓRIO)',
    'Depósito (OBRIGATÓRIO)',
    'Balanço (OBRIGATÓRIO)',
]


def default_model() -> pd.DataFrame:
    return pd.DataFrame(columns=DEFAULT_ESTOQUE_COLUMNS)


def _fill_deposito(df: pd.DataFrame, deposito: str) -> pd.DataFrame:
    out = df.copy().fillna('')
    if not deposito:
        return out
    for col in out.columns:
        key = normalize_key(col)
        if 'deposito' in key:
            out[col] = deposito
    return out


def run_estoque_engine(df_source: pd.DataFrame, df_model: pd.DataFrame | None = None, deposito: str = '') -> tuple[pd.DataFrame, dict[str, str]]:
    model = df_model if isinstance(df_model, pd.DataFrame) and len(df_model.columns) else default_model()
    source = df_source.copy().fillna('') if isinstance(df_source, pd.DataFrame) else pd.DataFrame()
    mapping = auto_map_columns(source, model)
    final = apply_mapping(source, model, mapping)
    final = _fill_deposito(final, deposito)
    return sanitize_for_bling(final), mapping


def requested_columns_from_model(df_model: pd.DataFrame) -> list[str]:
    if isinstance(df_model, pd.DataFrame) and len(df_model.columns):
        return [str(c) for c in df_model.columns]
    return list(DEFAULT_ESTOQUE_COLUMNS)
