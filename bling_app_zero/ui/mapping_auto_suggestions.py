from __future__ import annotations

import pandas as pd

from bling_app_zero.core.mapping_super_assistant import safe_default_for_target, super_auto_map_columns
from bling_app_zero.ui.mapping_constants import PRICE_TARGET_ALIASES


def force_price_suggestion(target: str, source_columns: list[str], suggested: str) -> str:
    if target in PRICE_TARGET_ALIASES and 'Preço de venda' in source_columns:
        return 'Preço de venda'
    return suggested


def build_super_mapping(df_source: pd.DataFrame, model: pd.DataFrame, source_columns: list[str]) -> dict[str, str]:
    auto_mapping = super_auto_map_columns(df_source, model)
    for target, selected in list(auto_mapping.items()):
        default_value = safe_default_for_target(target)
        if default_value:
            auto_mapping[target] = ''
            continue
        auto_mapping[target] = force_price_suggestion(target, source_columns, selected)
    return auto_mapping


def build_stock_auto_mapping(df_source: pd.DataFrame, model: pd.DataFrame) -> dict[str, str]:
    auto_mapping = super_auto_map_columns(df_source, model)
    for target in [str(column) for column in model.columns]:
        if 'deposito' in target.lower() or 'depósito' in target.lower():
            auto_mapping[target] = ''
    return auto_mapping


__all__ = [
    'build_stock_auto_mapping',
    'build_super_mapping',
    'force_price_suggestion',
]
