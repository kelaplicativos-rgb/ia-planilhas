from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.core.mapping import apply_mapping
from bling_app_zero.core.mapping_super_assistant import safe_default_for_target
from bling_app_zero.core.text import normalize_key
from bling_app_zero.ui.mapping_widget_state import (
    is_empty_mapping_value,
    is_manual_value,
    manual_fixed_value_key,
    manual_value_key,
    target_widget_key,
)

CALCULATED_PRICE_SOURCE_COLUMN = 'Preço de venda'
PRICE_TARGET_ALIASES = (
    'Preço de venda',
    'Preço unitário (OBRIGATÓRIO)',
    'Preço unitário',
    'Preço',
    'Valor',
)


def explicit_empty_targets(mapping: dict[str, str]) -> set[str]:
    return {str(target) for target, value in (mapping or {}).items() if is_empty_mapping_value(value)}


def apply_explicit_empty_values(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    for target in explicit_empty_targets(mapping):
        if target in out.columns:
            out[target] = ''
    return out


def apply_safe_defaults(df: pd.DataFrame, protected_empty_targets: set[str] | None = None) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    protected = set(protected_empty_targets or set())
    for column in out.columns:
        if str(column) in protected:
            out[column] = ''
            continue
        default_value = safe_default_for_target(str(column))
        if default_value:
            out[column] = out[column].apply(lambda value: default_value if not str(value or '').strip() else value)
    return out


def _manual_fixed_value(mapping_key: str, target: str, widget_key: str) -> str:
    stable_key = manual_fixed_value_key(mapping_key, target)
    legacy_key = manual_value_key(widget_key)
    value = str(st.session_state.get(stable_key, '') or '')
    if value:
        return value
    return str(st.session_state.get(legacy_key, '') or '')


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
        manual_value = _manual_fixed_value(mapping_key, target, widget_key)
        out[target] = manual_value
    return out


def apply_calculated_price_lock(df_preview: pd.DataFrame, df_source: pd.DataFrame, protected_empty_targets: set[str] | None = None) -> pd.DataFrame:
    out = df_preview.copy().fillna('') if isinstance(df_preview, pd.DataFrame) else pd.DataFrame()
    protected = set(protected_empty_targets or set())
    if not bool(st.session_state.get('cadastro_preco_calculado_ativo', False)):
        return out
    if not isinstance(df_source, pd.DataFrame) or CALCULATED_PRICE_SOURCE_COLUMN not in df_source.columns:
        return out
    calculated_values = df_source[CALCULATED_PRICE_SOURCE_COLUMN].reset_index(drop=True)
    if len(calculated_values) != len(out):
        return out
    applied_targets: list[str] = []
    for column in PRICE_TARGET_ALIASES:
        if column in protected:
            out[column] = ''
            continue
        if column in out.columns:
            out[column] = calculated_values
            applied_targets.append(column)
    if applied_targets:
        st.session_state['cadastro_preco_calculado_targets_aplicados'] = applied_targets
    else:
        st.session_state.pop('cadastro_preco_calculado_targets_aplicados', None)
    return out


def fill_deposito_manual(df: pd.DataFrame, deposito: str, protected_empty_targets: set[str] | None = None) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    protected = set(protected_empty_targets or set())
    if not deposito:
        return out
    for column in out.columns:
        if str(column) in protected:
            out[column] = ''
            continue
        if 'deposito' in normalize_key(column):
            out[column] = deposito
    return out


def _mapping_for_apply(mapping: dict[str, str]) -> dict[str, str]:
    return {
        target: value
        for target, value in (mapping or {}).items()
        if not is_manual_value(value) and not is_empty_mapping_value(value)
    }


def build_cadastro_preview(
    df_source: pd.DataFrame,
    model: pd.DataFrame,
    mapping: dict[str, str],
    target_columns: list[str],
    mapping_key: str,
) -> pd.DataFrame:
    protected_empty = explicit_empty_targets(mapping)
    preview = apply_mapping(df_source, model, _mapping_for_apply(mapping))
    preview = apply_manual_fixed_values(preview, mapping, target_columns, mapping_key)
    preview = apply_safe_defaults(preview, protected_empty)
    preview = apply_calculated_price_lock(preview, df_source, protected_empty)
    preview = apply_explicit_empty_values(preview, mapping)
    return sanitize_for_bling(preview, operation='cadastro', explicit_empty_columns=protected_empty)


def build_estoque_preview(
    df_source: pd.DataFrame,
    model: pd.DataFrame,
    mapping: dict[str, str],
    target_columns: list[str],
    mapping_key: str,
    deposito: str,
) -> pd.DataFrame:
    protected_empty = explicit_empty_targets(mapping)
    preview = apply_mapping(df_source, model, _mapping_for_apply(mapping))
    preview = apply_manual_fixed_values(preview, mapping, target_columns, mapping_key)
    preview = fill_deposito_manual(preview, deposito, protected_empty)
    preview = apply_explicit_empty_values(preview, mapping)
    return sanitize_for_bling(preview, operation='estoque', explicit_empty_columns=protected_empty)


__all__ = [
    'apply_calculated_price_lock',
    'apply_explicit_empty_values',
    'apply_manual_fixed_values',
    'apply_safe_defaults',
    'build_cadastro_preview',
    'build_estoque_preview',
    'explicit_empty_targets',
    'fill_deposito_manual',
]
