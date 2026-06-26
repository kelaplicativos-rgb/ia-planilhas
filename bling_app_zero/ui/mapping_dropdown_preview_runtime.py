from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/mapping_dropdown_preview_runtime.py'
PATCH_VERSION = 'dropdown_preview_source_or_model_v7_no_table_expand'
BLANKS = {'', 'nan', 'none', 'null', '<na>'}
_CONTEXT: dict[str, Any] = {'source': None, 'target': None}


def _blank(value: object) -> bool:
    return str(value or '').strip().casefold() in BLANKS


def _norm(value: object) -> str:
    text = str(value or '').strip().casefold()
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-z0-9]+', '', text)


def _clean(value: object) -> str:
    text = str(value or '').replace('\t', ' ').replace('\n', ' ').strip()
    while '  ' in text:
        text = text.replace('  ', ' ')
    return text


def _matching_column(df: Any, column: str) -> str:
    if not isinstance(df, pd.DataFrame) or not column:
        return ''
    if column in df.columns:
        return column
    wanted = _norm(column)
    if not wanted:
        return ''
    for candidate in [str(c) for c in df.columns]:
        if _norm(candidate) == wanted:
            return candidate
    return ''


def _samples(df: Any, column: str, limit: int = 2) -> list[str]:
    actual_column = _matching_column(df, column)
    if not actual_column:
        return []
    out: list[str] = []
    try:
        for value in df[actual_column].dropna().astype(str).tolist():
            text = _clean(value)
            if _blank(text):
                continue
            if text not in out:
                out.append(text)
            if len(out) >= limit:
                break
    except Exception:
        return []
    return out


def _column_state(df: Any, column: str, limit: int = 2) -> tuple[str, str, list[str]]:
    actual_column = _matching_column(df, column)
    if not actual_column:
        return 'missing', '', []
    values = _samples(df, actual_column, limit=limit)
    if values:
        return 'values', actual_column, values
    return 'empty', actual_column, []


def _short(values: list[str], size: int = 72) -> str:
    text = ' | '.join(values)
    return text if len(text) <= size else text[: size - 1].rstrip() + '…'


def _icon(label: object) -> str:
    text = str(label or '').strip()
    for mark in ('🟢', '🟡', '🔴', '⚪'):
        if text.startswith(mark):
            return mark
    return '🟡'


def _restore_dataframe_preview_if_previous_patch_expanded_it() -> None:
    """Desfaz o patch v6 que aumentava preview de tabela no anexo do modelo.

    O preview visual do modelo deve continuar compacto. O toggle de preservação
    controla apenas a mesclagem modelo + origem na saída final.
    """
    try:
        original_dataframe = getattr(st, '_mapeiaai_original_dataframe', None)
        current_version = str(getattr(st, '_mapeiaai_full_table_preview_runtime_version', '') or '')
        if callable(original_dataframe) and current_version and current_version != 'removed_by_v7_no_table_expand':
            st.dataframe = original_dataframe
            st._mapeiaai_full_table_preview_runtime_version = 'removed_by_v7_no_table_expand'
            add_audit_event('full_table_preview_runtime_removed', area='UNIVERSAL', status='OK', details={'reason': 'Preview do anexo do modelo não deve ser expandido; preservação é regra de mesclagem final.', 'previous_version': current_version, 'responsible_file': RESPONSIBLE_FILE})
    except Exception as exc:
        add_audit_event('full_table_preview_runtime_remove_failed', area='UNIVERSAL', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})


def _source_column_state(column: str, limit: int = 2, source: Any | None = None) -> tuple[str, str, list[str]]:
    frame = source if isinstance(source, pd.DataFrame) else _CONTEXT.get('source')
    return _column_state(frame, column, limit=limit)


def _model_column_state(column: str, target_name: str = '', limit: int = 2) -> tuple[str, str, list[str]]:
    model = _CONTEXT.get('target')
    checked: list[str] = []
    for candidate in (column, target_name):
        candidate = str(candidate or '').strip()
        if candidate and candidate not in checked:
            checked.append(candidate)
    first_empty: tuple[str, str, list[str]] | None = None
    for candidate in checked:
        state, actual_column, values = _column_state(model, candidate, limit=limit)
        if state == 'values':
            return state, actual_column, values
        if state == 'empty' and first_empty is None:
            first_empty = (state, actual_column, values)
    return first_empty or ('missing', '', [])


def _status_text(status: str, column: str) -> str:
    if status == 'empty':
        return f'coluna {column} vazia' if column else 'coluna vazia'
    if status == 'missing':
        return 'não existe'
    return ''


def _model_samples(column: str, target_name: str = '', limit: int = 2) -> tuple[str, list[str]]:
    _status, actual_column, values = _model_column_state(column, target_name, limit=limit)
    return actual_column, values


def _preview_label(column: str, current_label: object, target_name: str = '') -> str:
    icon = _icon(current_label)
    source_status, source_column, source_values = _source_column_state(column, limit=2)
    if source_values:
        label = column if source_column == column else f'{column} -> origem {source_column}'
        return f'{icon} {label}: origem {_short(source_values)}'

    model_status, model_column, model_values = _model_column_state(column, target_name, limit=2)
    if model_values:
        label = column if model_column == column else f'{column} -> modelo {model_column}'
        return f'{icon} {label}: modelo {_short(model_values)}'

    source_info = _status_text(source_status, source_column or column)
    model_info = _status_text(model_status, model_column or target_name or column)
    return f'{icon} {column}: origem {source_info}; modelo {model_info}'


def install_mapping_dropdown_preview_runtime() -> None:
    _restore_dataframe_preview_if_previous_patch_expanded_it()
    try:
        from bling_app_zero.ui import shared_mapping
    except Exception as exc:
        add_audit_event('mapping_dropdown_preview_runtime_import_failed', area='MAPEAMENTO', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
        return

    if getattr(shared_mapping, '_mapeiaai_dropdown_preview_runtime_version', '') == PATCH_VERSION:
        return

    original_render = shared_mapping.render_shared_contract_mapping
    original_ranked = shared_mapping._ranked_source_options
    original_mapping_preview = shared_mapping._render_mapping_preview

    def ranked_with_real_preview(target_name, current_value, source_columns, suggestions_index, source_profiles=None):
        options, labels = original_ranked(target_name, current_value, source_columns, suggestions_index, source_profiles)
        labels = dict(labels or {})
        for column in list(source_columns or []):
            if column in labels:
                labels[column] = _preview_label(str(column), labels[column], str(target_name or ''))
        return options, labels

    def render_mapping_preview_with_model_fallback(target_name, selected_value, source):
        try:
            selected = str(selected_value or '').strip()
            if selected and not shared_mapping.is_fixed_value(selected):
                source_status, source_column, source_samples = _source_column_state(selected, limit=3, source=source)
                icon = shared_mapping.confidence_flag(str(target_name or ''), selected, source).split()[0]
                if source_samples:
                    shared_mapping.st.caption(f'{icon} **{target_name}**. Prévia da origem ({source_column}): {_short(source_samples, 150)}')
                    return

                model_status, model_column, model_values = _model_column_state(selected, str(target_name or ''), limit=3)
                if model_values:
                    shared_mapping.st.caption(f'{icon} **{target_name}**. Prévia do modelo anexado ({model_column}): {_short(model_values, 150)}')
                    return

                source_info = _status_text(source_status, source_column or selected)
                model_info = _status_text(model_status, model_column or str(target_name or selected))
                shared_mapping.st.caption(f'{icon} **{target_name}**. Origem: {source_info}. Modelo: {model_info}.')
                return
        except Exception:
            pass
        return original_mapping_preview(target_name, selected_value, source)

    def render_with_context(source, target, *, signature: str, mapping_state_key: str, engine_state_key: str, key_prefix: str = 'mapeiaai_shared', ai_enabled: bool = True):
        previous_source = _CONTEXT.get('source')
        previous_target = _CONTEXT.get('target')
        _CONTEXT['source'] = source
        _CONTEXT['target'] = target
        try:
            return original_render(source, target, signature=signature, mapping_state_key=mapping_state_key, engine_state_key=engine_state_key, key_prefix=key_prefix, ai_enabled=ai_enabled)
        finally:
            _CONTEXT['source'] = previous_source
            _CONTEXT['target'] = previous_target

    shared_mapping._ranked_source_options = ranked_with_real_preview
    shared_mapping._render_mapping_preview = render_mapping_preview_with_model_fallback
    shared_mapping.render_shared_contract_mapping = render_with_context
    shared_mapping._mapeiaai_dropdown_preview_runtime_version = PATCH_VERSION
    add_audit_event('mapping_dropdown_preview_runtime_installed', area='MAPEAMENTO', status='OK', details={'format': 'Dropdown mostra campo + conteúdo; preview do modelo continua compacto; preservação fica na mesclagem final', 'version': PATCH_VERSION, 'responsible_file': RESPONSIBLE_FILE})


__all__ = ['install_mapping_dropdown_preview_runtime']
