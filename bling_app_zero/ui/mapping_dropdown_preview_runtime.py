from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/mapping_dropdown_preview_runtime.py'
PATCH_VERSION = 'dropdown_preview_source_or_model_v4'
BLANKS = {'', 'nan', 'none', 'null', '<na>'}
_CONTEXT: dict[str, Any] = {'source': None, 'target': None}

SOURCE_STATE_KEYS = (
    'mapeiaai_universal_source_df',
    'mapeiaai_universal_processed_df',
    'cadastro_wizard_df_para_mapear',
    'df_origem_cadastro_precificada',
    'df_origem_unificada',
    'df_produtos_origem',
    'df_source',
    'df_origem',
    'df_origem_site',
    'df_site_bruto_universal',
    'df_site_bruto',
    'cadastro_wizard_df_origem',
    'df_origem_planilha',
    'df_origem_cadastro',
    'df_origem_site_como_planilha_universal',
    'df_origem_site_como_planilha',
)

MODEL_STATE_KEYS = (
    'mapeiaai_universal_model_df',
    'home_modelo_universal_df',
    'df_modelo_universal',
    'modelo_universal_df',
    'site_modelo_cadastro_como_planilha',
    'site_modelo_operacao_como_planilha',
)


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


def _session_frames(keys: tuple[str, ...]) -> list[pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    try:
        import streamlit as st
        session_items = list(st.session_state.items())
    except Exception:
        session_items = []

    seen: set[int] = set()

    def push(frame: Any) -> None:
        if isinstance(frame, pd.DataFrame) and id(frame) not in seen:
            seen.add(id(frame))
            frames.append(frame)

    for key in keys:
        for name, frame in session_items:
            if str(name) == key:
                push(frame)

    # Fallback defensivo: se algum runtime chamou o preview sem o contexto principal,
    # ainda assim procure DataFrames compatíveis na sessão, mas sem misturar modelo/origem
    # antes das chaves preferenciais.
    keywords = ('source', 'origem', 'processed', 'site', 'produtos') if keys == SOURCE_STATE_KEYS else ('model', 'modelo')
    for name, frame in session_items:
        lname = str(name).casefold()
        if any(keyword in lname for keyword in keywords):
            push(frame)

    return frames


def _candidate_frames(kind: str) -> list[pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    seen: set[int] = set()

    def push(frame: Any) -> None:
        if isinstance(frame, pd.DataFrame) and id(frame) not in seen:
            seen.add(id(frame))
            frames.append(frame)

    if kind == 'source':
        push(_CONTEXT.get('source'))
        for frame in _session_frames(SOURCE_STATE_KEYS):
            push(frame)
    else:
        push(_CONTEXT.get('target'))
        for frame in _session_frames(MODEL_STATE_KEYS):
            push(frame)
    return frames


def _best_column_state(kind: str, column: str, target_name: str = '', limit: int = 2) -> tuple[str, str, list[str]]:
    columns_to_check: list[str] = []
    for candidate in (column, target_name):
        candidate = str(candidate or '').strip()
        if candidate and candidate not in columns_to_check:
            columns_to_check.append(candidate)

    first_empty: tuple[str, str, list[str]] | None = None
    for frame in _candidate_frames(kind):
        for candidate in columns_to_check:
            state, actual_column, values = _column_state(frame, candidate, limit=limit)
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
    _status, actual_column, values = _best_column_state('model', column, target_name, limit=limit)
    return actual_column, values


def _preview_label(column: str, current_label: object, target_name: str = '') -> str:
    icon = _icon(current_label)
    source_status, source_column, source_values = _best_column_state('source', column, target_name, limit=2)
    if source_values:
        label = column if source_column == column else f'{column} -> origem {source_column}'
        return f'{icon} {label}: origem {_short(source_values)}'

    model_status, model_column, model_values = _best_column_state('model', column, target_name, limit=2)
    if model_values:
        label = column if model_column == column else f'{column} -> modelo {model_column}'
        return f'{icon} {label}: modelo {_short(model_values)}'

    source_info = _status_text(source_status, source_column or column)
    model_info = _status_text(model_status, model_column or target_name or column)
    return f'{icon} {column}: origem {source_info}; modelo {model_info}'


def install_mapping_dropdown_preview_runtime() -> None:
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
                source_status, source_column, source_samples = _best_column_state('source', selected, str(target_name or ''), limit=3)
                if source_samples:
                    icon = shared_mapping.confidence_flag(str(target_name or ''), selected, source).split()[0]
                    shared_mapping.st.caption(f'{icon} **{target_name}**. Prévia da origem ({source_column}): {_short(source_samples, 150)}')
                    return

                model_status, model_column, model_values = _best_column_state('model', selected, str(target_name or ''), limit=3)
                icon = shared_mapping.confidence_flag(str(target_name or ''), selected, source).split()[0]
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
    add_audit_event('mapping_dropdown_preview_runtime_installed', area='MAPEAMENTO', status='OK', details={'format': 'Campo: valor real da origem; fallback para modelo anexado; diferencia vazio/inexistente', 'version': PATCH_VERSION, 'responsible_file': RESPONSIBLE_FILE})


__all__ = ['install_mapping_dropdown_preview_runtime']
