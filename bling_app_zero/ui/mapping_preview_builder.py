from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.core.mapping import apply_mapping
from bling_app_zero.core.mapping_super_assistant import safe_default_for_target
from bling_app_zero.core.text import normalize_key
from bling_app_zero.ui.mapping_widget_state import is_manual_value, manual_value_key, target_widget_key


def apply_safe_defaults(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    for column in out.columns:
        default_value = safe_default_for_target(str(column))
        if default_value:
            out[column] = out[column].apply(lambda value: default_value if not str(value or '').strip() else value)
    return out


def apply_manual_fixed_values(
    df: pd.DataFrame,
    mapping: dict[str, str],
    target_columns: list[str],
    mapping_key: str,
) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    for index, target in enumerate(target_columns):
        if not is_manual_value(mapping.get(target, '')) or target not in out.columns:
            continue
        widget_key = target_widget_key(mapping_key, index)
        manual_value = str(st.session_state.get(manual_value_key(widget_key), '') or '')
        out[target] = manual_value
    return out


def fill_deposito_manual(df: pd.DataFrame, deposito: str) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if not deposito:
        return out
    for column in out.columns:
        if 'deposito' in normalize_key(column):
            out[column] = deposito
    return out


def build_cadastro_preview(
    df_source: pd.DataFrame,
    model: pd.DataFrame,
    mapping: dict[str, str],
    target_columns: list[str],
    mapping_key: str,
) -> pd.DataFrame:
    mapping_for_apply = {target: value for target, value in mapping.items() if not is_manual_value(value)}
    preview = apply_mapping(df_source, model, mapping_for_apply)
    preview = apply_manual_fixed_values(preview, mapping, target_columns, mapping_key)
    preview = apply_safe_defaults(preview)
    return sanitize_for_bling(preview)


def build_estoque_preview(
    df_source: pd.DataFrame,
    model: pd.DataFrame,
    mapping: dict[str, str],
    target_columns: list[str],
    mapping_key: str,
    deposito: str,
) -> pd.DataFrame:
    mapping_for_apply = {target: value for target, value in mapping.items() if not is_manual_value(value)}
    preview = apply_mapping(df_source, model, mapping_for_apply)
    preview = apply_manual_fixed_values(preview, mapping, target_columns, mapping_key)
    preview = fill_deposito_manual(preview, deposito)
    return sanitize_for_bling(preview)


__all__ = [
    'apply_manual_fixed_values',
    'apply_safe_defaults',
    'build_cadastro_preview',
    'build_estoque_preview',
    'fill_deposito_manual',
]
