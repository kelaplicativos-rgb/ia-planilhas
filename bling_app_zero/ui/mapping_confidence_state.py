from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.column_contract import build_contract
from bling_app_zero.core.mapping_confidence import confidence_for_mapping, resolved_empty_confidence, sort_targets_by_confidence
from bling_app_zero.ui.mapping_widget_state import is_explicit_empty, is_explicit_manual, option_value, target_widget_key

# BLINGFIX: além de colunas marcadas com * / OBRIGATÓRIO no modelo,
# tratamos os campos essenciais do cadastro como obrigatórios visuais.
# Isso evita o erro mostrado no mapeamento: "Obrigatórios 0" mesmo existindo
# Descrição e Preço no modelo do Bling.
ESSENTIAL_REQUIRED_KINDS = {
    'descricao',
    'preco_unitario',
}


def manual_confidence() -> dict[str, object]:
    return {
        'level': 'verde',
        'emoji': '🟢',
        'label': 'valor fixo confirmado',
        'score': 100,
        'order': 2,
        'strict': True,
        'manual': True,
    }


def confidence_for_selection(df_source: pd.DataFrame, target: str, selected: str, widget_key: str) -> dict[str, object]:
    if is_explicit_manual(widget_key, selected):
        return manual_confidence()
    if is_explicit_empty(widget_key, selected):
        return resolved_empty_confidence()
    return confidence_for_mapping(df_source, target, option_value(selected))


def current_confidence_from_widgets(
    df_source: pd.DataFrame,
    target_columns: list[str],
    current_mapping: dict[str, str],
    mapping_key: str,
) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for index, target in enumerate(target_columns):
        widget_key = target_widget_key(mapping_key, index)
        selected = st.session_state.get(widget_key, current_mapping.get(target, ''))
        result[target] = confidence_for_selection(df_source, target, selected, widget_key)
    return result


def ordered_targets_once(order_key: str, target_columns: list[str], confidence: dict[str, dict[str, object]]) -> list[str]:
    saved = st.session_state.get(order_key)
    valid_targets = [str(target) for target in target_columns]
    valid_set = set(valid_targets)
    if isinstance(saved, list):
        clean_saved = [str(item) for item in saved if str(item) in valid_set]
        missing = [target for target in valid_targets if target not in set(clean_saved)]
        if clean_saved or missing:
            order = clean_saved + missing
            st.session_state[order_key] = order
            return order
    order = sort_targets_by_confidence(valid_targets, confidence)
    st.session_state[order_key] = order
    return order


def required_targets(target_columns: list[str]) -> set[str]:
    required: set[str] = set()
    for field in build_contract(target_columns):
        if field.required or field.kind in ESSENTIAL_REQUIRED_KINDS:
            required.add(field.original)
    return required


__all__ = [
    'confidence_for_selection',
    'current_confidence_from_widgets',
    'manual_confidence',
    'ordered_targets_once',
    'required_targets',
]
