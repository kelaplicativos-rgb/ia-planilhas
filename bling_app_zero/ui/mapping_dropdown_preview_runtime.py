from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/mapping_dropdown_preview_runtime.py'
PATCH_VERSION = 'dropdown_preview_source_or_model_v9_dual_source_toggle'
MODEL_PRESERVE_TOGGLE_KEY = 'mapeiaai_model_preserve_data_toggle_v1'
ORIGIN_REF_PREFIX = 'origem::'
MODEL_REF_PREFIX = 'modelo::'
EMPTY_OPTION = '(deixar vazio)'
WRITE_OPTION = '✍️ escrever valor fixo/manual'
BLANKS = {'', 'nan', 'none', 'null', '<na>'}
_CONTEXT: dict[str, Any] = {'source': None, 'target': None}
SOURCE_KEYS = ('mapeiaai_universal_processed_df', 'mapeiaai_universal_source_df', 'df_origem_unificada', 'df_origem_site', 'df_source')
MODEL_KEYS = ('mapeiaai_universal_model_df', 'home_modelo_universal_df', 'df_modelo_universal', 'modelo_universal_df')


def _norm(value: object) -> str:
    text = str(value or '').strip().casefold()
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-z0-9]+', '', text)


def _clean(value: object) -> str:
    text = str(value or '').replace('\t', ' ').replace('\n', ' ').strip()
    while '  ' in text:
        text = text.replace('  ', ' ')
    return text


def _split_ref(value: object) -> tuple[str, str]:
    text = str(value or '').strip()
    if text.startswith(ORIGIN_REF_PREFIX):
        return 'origem', text[len(ORIGIN_REF_PREFIX):].strip()
    if text.startswith(MODEL_REF_PREFIX):
        return 'modelo', text[len(MODEL_REF_PREFIX):].strip()
    return 'origem', text


def _is_ref(value: object) -> bool:
    text = str(value or '')
    return text.startswith(ORIGIN_REF_PREFIX) or text.startswith(MODEL_REF_PREFIX)


def _ref(kind: str, column: object) -> str:
    return (MODEL_REF_PREFIX if kind == 'modelo' else ORIGIN_REF_PREFIX) + str(column or '').strip()


def _matching_column(df: Any, column: str) -> str:
    _kind, column = _split_ref(column)
    if not isinstance(df, pd.DataFrame) or not column:
        return ''
    if column in df.columns:
        return column
    wanted = _norm(column)
    for candidate in [str(c) for c in df.columns]:
        if wanted and _norm(candidate) == wanted:
            return candidate
    return ''


def _df_has_values(df: Any) -> bool:
    try:
        frame = df.fillna('').astype(str)
        return bool(frame.apply(lambda col: col.str.strip().ne('').any()).any())
    except Exception:
        return False


def _first_session_frame(keys: tuple[str, ...], column: str = '') -> pd.DataFrame | None:
    for key in keys:
        frame = st.session_state.get(key)
        if isinstance(frame, pd.DataFrame) and not frame.empty and (not column or _matching_column(frame, column)):
            return frame
    return None


def _source_frame(column: str = '') -> pd.DataFrame | None:
    frame = _CONTEXT.get('source')
    if isinstance(frame, pd.DataFrame) and (not column or _matching_column(frame, column)):
        return frame
    return _first_session_frame(SOURCE_KEYS, column)


def _model_frame(column: str = '') -> pd.DataFrame | None:
    frame = _CONTEXT.get('target')
    if isinstance(frame, pd.DataFrame) and (not column or _matching_column(frame, column)):
        return frame
    return _first_session_frame(MODEL_KEYS, column)


def _dual_enabled() -> bool:
    return bool(st.session_state.get(MODEL_PRESERVE_TOGGLE_KEY, False)) and _df_has_values(_model_frame())


def _samples(df: Any, column: str, limit: int = 2) -> list[str]:
    actual_column = _matching_column(df, column)
    if not actual_column:
        return []
    out: list[str] = []
    try:
        for value in df[actual_column].dropna().astype(str).tolist():
            text = _clean(value)
            if text.casefold() in BLANKS:
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
    return ('values', actual_column, values) if values else ('empty', actual_column, [])


def _short(values: list[str], size: int = 72) -> str:
    text = ' | '.join(values)
    return text if len(text) <= size else text[: size - 1].rstrip() + '…'


def _icon(label: object) -> str:
    text = str(label or '').strip()
    for mark in ('🟢', '🟡', '🔴', '⚪'):
        if text.startswith(mark):
            return mark
    return '🟡'


def _status_text(status: str, column: str) -> str:
    if status == 'empty':
        return f'coluna {column} vazia' if column else 'coluna vazia'
    return 'não existe' if status == 'missing' else ''


def _preview_for(kind: str, column: str, icon: str) -> str:
    frame = _source_frame(column) if kind == 'origem' else _model_frame(column)
    status, actual_column, values = _column_state(frame, column, limit=2)
    label_kind = 'Origem' if kind == 'origem' else 'Modelo'
    if values:
        return f'{icon} {label_kind} > {actual_column or column}: {_short(values)}'
    return f'{icon} {label_kind} > {column}: {_status_text(status, actual_column or column)}'


def _preview_label(column: str, current_label: object, target_name: str = '') -> str:
    icon = _icon(current_label)
    kind, clean_column = _split_ref(column)
    if _is_ref(column):
        return _preview_for(kind, clean_column, icon)
    status, actual_column, values = _column_state(_source_frame(clean_column), clean_column, limit=2)
    if values:
        return f'{icon} {clean_column}: origem {_short(values)}'
    m_status, m_column, m_values = _column_state(_model_frame(clean_column), clean_column, limit=2)
    if m_values:
        return f'{icon} {clean_column}: modelo {_short(m_values)}'
    return f'{icon} {clean_column}: origem {_status_text(status, actual_column or clean_column)}; modelo {_status_text(m_status, m_column or target_name or clean_column)}'


def _ranked_options(options: list[str], labels: dict[str, str], target_name: str) -> tuple[list[str], dict[str, str]]:
    if not _dual_enabled():
        for option in list(labels):
            if option not in {EMPTY_OPTION, WRITE_OPTION}:
                labels[option] = _preview_label(str(option), labels[option], target_name)
        return options, labels
    source_columns = [str(option) for option in options if option not in {EMPTY_OPTION, WRITE_OPTION} and not _is_ref(option)]
    model_columns = [str(column) for column in getattr(_model_frame(), 'columns', [])]
    new_options: list[str] = []
    new_labels: dict[str, str] = {EMPTY_OPTION: EMPTY_OPTION, WRITE_OPTION: WRITE_OPTION}
    for column in source_columns:
        token = _ref('origem', column)
        if token not in new_options:
            new_options.append(token)
            new_labels[token] = _preview_label(token, labels.get(column, '🟡 ' + column), target_name)
    for special in (EMPTY_OPTION, WRITE_OPTION):
        if special in options:
            new_options.append(special)
    for column in model_columns:
        token = _ref('modelo', column)
        if token not in new_options:
            new_options.append(token)
            icon = '🟢' if _norm(column) == _norm(target_name) else '🟡'
            new_labels[token] = _preview_label(token, icon + ' ' + column, target_name)
    return new_options, new_labels


def _restore_dataframe_preview_if_previous_patch_expanded_it() -> None:
    original_dataframe = getattr(st, '_mapeiaai_original_dataframe', None)
    current_version = str(getattr(st, '_mapeiaai_full_table_preview_runtime_version', '') or '')
    if callable(original_dataframe) and current_version and current_version != 'removed_by_v9_dual_source_toggle':
        st.dataframe = original_dataframe
        st._mapeiaai_full_table_preview_runtime_version = 'removed_by_v9_dual_source_toggle'


def install_mapping_dropdown_preview_runtime() -> None:
    _restore_dataframe_preview_if_previous_patch_expanded_it()
    try:
        from bling_app_zero.ui import shared_mapping
    except Exception as exc:
        add_audit_event('mapping_dropdown_preview_runtime_import_failed', area='MAPEAMENTO', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
        return

    ranked_base = shared_mapping._ranked_source_options
    if not getattr(ranked_base, '_mapeiaai_dropdown_preview_ranked', False):
        def ranked_with_real_preview(target_name, current_value, source_columns, suggestions_index, source_profiles=None):
            options, labels = ranked_base(target_name, current_value, source_columns, suggestions_index, source_profiles)
            return _ranked_options(list(options or []), dict(labels or {}), str(target_name or ''))
        ranked_with_real_preview._mapeiaai_dropdown_preview_ranked = True
        shared_mapping._ranked_source_options = ranked_with_real_preview

    preview_base = shared_mapping._render_mapping_preview
    if not getattr(preview_base, '_mapeiaai_dropdown_preview_caption', False):
        def render_mapping_preview_with_model_fallback(target_name, selected_value, source):
            selected = str(selected_value or '').strip()
            if selected and not shared_mapping.is_fixed_value(selected):
                kind, column = _split_ref(selected)
                frame = _source_frame(column) if kind == 'origem' else _model_frame(column)
                status, actual_column, samples = _column_state(frame, column, limit=3)
                icon = shared_mapping.confidence_flag(str(target_name or ''), column, source).split()[0]
                if samples:
                    label_kind = 'origem' if kind == 'origem' else 'modelo anexado'
                    shared_mapping.st.caption(f'{icon} **{target_name}**. Prévia da {label_kind} ({actual_column}): {_short(samples, 150)}')
                    return
                shared_mapping.st.caption(f'{icon} **{target_name}**. {kind}: {_status_text(status, actual_column or column)}.')
                return
            return preview_base(target_name, selected_value, source)
        render_mapping_preview_with_model_fallback._mapeiaai_dropdown_preview_caption = True
        shared_mapping._render_mapping_preview = render_mapping_preview_with_model_fallback

    render_base = shared_mapping.render_shared_contract_mapping
    if not getattr(render_base, '_mapeiaai_dropdown_preview_render', False):
        def render_with_context(source, target, *, signature: str, mapping_state_key: str, engine_state_key: str, key_prefix: str = 'mapeiaai_shared', ai_enabled: bool = True):
            previous_source, previous_target = _CONTEXT.get('source'), _CONTEXT.get('target')
            _CONTEXT['source'], _CONTEXT['target'] = source, target
            try:
                if _dual_enabled():
                    st.caption('Preservação ativa: escolha Origem ou Modelo anexado em cada campo do mapeamento.')
                return render_base(source, target, signature=signature, mapping_state_key=mapping_state_key, engine_state_key=engine_state_key, key_prefix=key_prefix, ai_enabled=ai_enabled)
            finally:
                _CONTEXT['source'], _CONTEXT['target'] = previous_source, previous_target
        render_with_context._mapeiaai_dropdown_preview_render = True
        shared_mapping.render_shared_contract_mapping = render_with_context

    shared_mapping._mapeiaai_dropdown_preview_runtime_version = PATCH_VERSION
    add_audit_event('mapping_dropdown_preview_runtime_installed', area='MAPEAMENTO', status='OK', details={'version': PATCH_VERSION, 'dual_source_only_when_toggle_on': True, 'responsible_file': RESPONSIBLE_FILE})


__all__ = ['install_mapping_dropdown_preview_runtime']
