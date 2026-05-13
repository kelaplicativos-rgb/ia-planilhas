from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.core.mapping import apply_mapping
from bling_app_zero.core.mapping_super_assistant import safe_default_for_target
from bling_app_zero.core.text import normalize_key
from bling_app_zero.ui.mapping_widget_state import is_manual_value, manual_value_key, target_widget_key

CALCULATED_PRICE_SOURCE_COLUMN = 'Preço de venda'
PRICE_TARGET_ALIASES = (
    'Preço de venda',
    'Preço unitário (OBRIGATÓRIO)',
    'Preço unitário',
    'Preço',
    'Valor',
)


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


def apply_calculated_price_lock(df_preview: pd.DataFrame, df_source: pd.DataFrame) -> pd.DataFrame:
    """Força o preço da calculadora nos campos de preço do Bling.

    Quando a precificação do cadastro está ativa, o usuário ainda consegue revisar
    o mapeamento, mas o CSV final não deve voltar a usar o preço bruto do fornecedor
    por engano. O valor calculado em `Preço de venda` passa a ser a fonte oficial
    para todos os aliases de preço existentes no modelo.
    """
    out = df_preview.copy().fillna('') if isinstance(df_preview, pd.DataFrame) else pd.DataFrame()
    if not bool(st.session_state.get('cadastro_preco_calculado_ativo', False)):
        return out
    if not isinstance(df_source, pd.DataFrame) or CALCULATED_PRICE_SOURCE_COLUMN not in df_source.columns:
        return out
    calculated_values = df_source[CALCULATED_PRICE_SOURCE_COLUMN].reset_index(drop=True)
    if len(calculated_values) != len(out):
        return out
    applied_targets: list[str] = []
    for column in PRICE_TARGET_ALIASES:
        if column in out.columns:
            out[column] = calculated_values
            applied_targets.append(column)
    if applied_targets:
        st.session_state['cadastro_preco_calculado_targets_aplicados'] = applied_targets
    else:
        st.session_state.pop('cadastro_preco_calculado_targets_aplicados', None)
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
    preview = apply_calculated_price_lock(preview, df_source)
    return sanitize_for_bling(preview, operation='cadastro')


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
    return sanitize_for_bling(preview, operation='estoque')


__all__ = [
    'apply_calculated_price_lock',
    'apply_manual_fixed_values',
    'apply_safe_defaults',
    'build_cadastro_preview',
    'build_estoque_preview',
    'fill_deposito_manual',
]
