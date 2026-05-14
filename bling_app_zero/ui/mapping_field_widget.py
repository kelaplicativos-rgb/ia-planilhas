from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.layout import render_mapping_preview, render_mapping_title
from bling_app_zero.ui.mapping_confidence_state import confidence_for_selection, manual_confidence
from bling_app_zero.ui.mapping_constants import (
    EMPTY_LEAVE_OPTION,
    EMPTY_MAPPING_VALUE,
    MANUAL_MAPPING_VALUE,
    MANUAL_WRITE_OPTION,
)
from bling_app_zero.ui.mapping_widget_state import (
    default_index,
    manual_value_key,
    option_value,
    target_widget_key,
)


def first_row_preview(df_source: pd.DataFrame, selected_column: str) -> str:
    selected_column = option_value(selected_column)
    if not selected_column or selected_column not in df_source.columns or df_source.empty:
        return ''
    value = df_source[selected_column].iloc[0]
    text = str(value if value is not None else '').strip()
    if len(text) > 160:
        text = text[:160] + '...'
    return text


def render_selected_column_preview(df_source: pd.DataFrame, selected_column: str) -> None:
    render_mapping_preview(first_row_preview(df_source, selected_column))


def signal_label(target: str, info: dict[str, object]) -> str:
    emoji = str(info.get('emoji') or '🔴').strip() or '🔴'
    return f'{emoji} {target}'


def render_manual_value_input(target: str, widget_key: str) -> str:
    value_key = manual_value_key(widget_key)
    manual_value = st.text_input(
        f'Valor fixo para {target}',
        value=str(st.session_state.get(value_key, '') or ''),
        key=value_key,
        placeholder='Digite o valor que será repetido no arquivo final',
    )
    return str(manual_value or '')


def render_mapping_select(
    df_source: pd.DataFrame,
    target: str,
    target_index: int,
    suggested: str,
    mapping_key: str,
    options: list[str],
) -> tuple[str, dict[str, object]]:
    widget_key = target_widget_key(mapping_key, target_index)
    if widget_key in st.session_state:
        widget_value = st.session_state.get(widget_key, suggested)
        if widget_value == MANUAL_WRITE_OPTION:
            suggested = MANUAL_MAPPING_VALUE
        elif widget_value == EMPTY_LEAVE_OPTION:
            suggested = EMPTY_MAPPING_VALUE
        else:
            suggested = option_value(widget_value)

    raw_before = st.session_state.get(widget_key, suggested)
    info_before = confidence_for_selection(df_source, target, raw_before, widget_key)
    label = signal_label(target, info_before)

    with st.container(border=True):
        render_mapping_title(label)
        selected_raw = st.selectbox(
            target,
            options,
            index=default_index(options, suggested, widget_key),
            key=widget_key,
            label_visibility='collapsed',
        )
        if selected_raw == MANUAL_WRITE_OPTION:
            st.session_state[f'{widget_key}__manual_resolved'] = True
            st.session_state.pop(f'{widget_key}__empty_resolved', None)
            render_manual_value_input(target, widget_key)
            selected = MANUAL_MAPPING_VALUE
        elif selected_raw == EMPTY_LEAVE_OPTION:
            st.session_state[f'{widget_key}__empty_resolved'] = True
            st.session_state.pop(f'{widget_key}__manual_resolved', None)
            selected = EMPTY_MAPPING_VALUE
        else:
            st.session_state.pop(f'{widget_key}__empty_resolved', None)
            st.session_state.pop(f'{widget_key}__manual_resolved', None)
            selected = option_value(selected_raw)

        info_after = confidence_for_selection(df_source, target, selected_raw, widget_key)
        if selected == MANUAL_MAPPING_VALUE:
            info_after = manual_confidence()
        elif selected == EMPTY_MAPPING_VALUE:
            info_after = {
                'level': 'verde',
                'emoji': '🟢',
                'label': 'vazio confirmado',
                'score': 100,
                'order': 2,
                'strict': True,
                'explicit_empty': True,
            }
        else:
            render_selected_column_preview(df_source, selected)

    return selected, info_after


__all__ = [
    'first_row_preview',
    'render_manual_value_input',
    'render_mapping_select',
    'render_selected_column_preview',
    'signal_label',
]
