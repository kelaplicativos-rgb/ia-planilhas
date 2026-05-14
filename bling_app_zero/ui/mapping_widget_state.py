from __future__ import annotations

import hashlib

import streamlit as st

from bling_app_zero.ui.mapping_constants import (
    EMPTY_CHOOSE_OPTION,
    EMPTY_LEAVE_OPTION,
    EMPTY_MAPPING_VALUE,
    MANUAL_MAPPING_VALUE,
    MANUAL_WRITE_OPTION,
    MAPPING_WIDGET_PREFIXES,
)


def short_hash(value: str, size: int = 12) -> str:
    return hashlib.sha1(str(value or '').encode('utf-8', errors='ignore')).hexdigest()[:size]


def mapping_base(prefix: str, signature: str) -> str:
    return f'{prefix}{short_hash(signature)}'


def target_widget_key(mapping_key: str, target_index: int) -> str:
    return f'{mapping_key}_f{target_index:03d}'


def manual_value_key(widget_key: str) -> str:
    return f'{widget_key}__manual_value'


def is_manual_value(value: str | None) -> bool:
    return str(value or '').strip() == MANUAL_MAPPING_VALUE


def is_empty_mapping_value(value: str | None) -> bool:
    return str(value or '').strip() == EMPTY_MAPPING_VALUE


def option_value(value: str | None) -> str:
    text = str(value or '').strip()
    if text in {EMPTY_CHOOSE_OPTION, EMPTY_LEAVE_OPTION, MANUAL_WRITE_OPTION, MANUAL_MAPPING_VALUE, EMPTY_MAPPING_VALUE}:
        return ''
    return text


def display_option(value: str | None) -> str:
    text = str(value or '').strip()
    if is_manual_value(text):
        return MANUAL_WRITE_OPTION
    if is_empty_mapping_value(text):
        return EMPTY_LEAVE_OPTION
    return text if text else EMPTY_CHOOSE_OPTION


def is_explicit_empty(widget_key: str, value: str | None) -> bool:
    return is_empty_mapping_value(value) or str(value or '').strip() == EMPTY_LEAVE_OPTION or bool(st.session_state.get(f'{widget_key}__empty_resolved'))


def is_explicit_manual(widget_key: str, value: str | None) -> bool:
    return str(value or '').strip() == MANUAL_WRITE_OPTION or bool(st.session_state.get(f'{widget_key}__manual_resolved')) or is_manual_value(value)


def default_index(options: list[str], value: str, widget_key: str | None = None) -> int:
    if is_manual_value(value):
        return options.index(MANUAL_WRITE_OPTION) if MANUAL_WRITE_OPTION in options else 0
    if is_empty_mapping_value(value):
        return options.index(EMPTY_LEAVE_OPTION) if EMPTY_LEAVE_OPTION in options else 0
    if widget_key and st.session_state.get(f'{widget_key}__manual_resolved'):
        return options.index(MANUAL_WRITE_OPTION) if MANUAL_WRITE_OPTION in options else 0
    if widget_key and st.session_state.get(f'{widget_key}__empty_resolved'):
        return options.index(EMPTY_LEAVE_OPTION) if EMPTY_LEAVE_OPTION in options else 0
    display = display_option(value)
    try:
        return options.index(display)
    except ValueError:
        return 0


def clear_stale_mapping_widgets(active_mapping_key: str) -> None:
    for key in list(st.session_state.keys()):
        text = str(key)
        if text.startswith(MAPPING_WIDGET_PREFIXES) and not text.startswith(active_mapping_key):
            st.session_state.pop(text, None)


def clear_mapping_widgets(mapping_key: str) -> None:
    for key in list(st.session_state.keys()):
        if str(key).startswith(f'{mapping_key}_'):
            st.session_state.pop(key, None)


__all__ = [
    'clear_mapping_widgets',
    'clear_stale_mapping_widgets',
    'default_index',
    'display_option',
    'is_empty_mapping_value',
    'is_explicit_empty',
    'is_explicit_manual',
    'is_manual_value',
    'manual_value_key',
    'mapping_base',
    'option_value',
    'short_hash',
    'target_widget_key',
]
