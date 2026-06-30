from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/mapping_dropdown_preview_runtime.py'
PATCH_VERSION = 'dropdown_preview_source_or_model_v13_preserve_toggle_strict'
MODEL_PRESERVE_TOGGLE_KEY = 'mapeiaai_model_preserve_data_toggle_v1'
ORIGIN_REF_PREFIX = 'origem::'
MODEL_REF_PREFIX = 'modelo::'
FIXED_VALUE_PREFIX = '__mapeiaai_fixed_value__:'
EMPTY_OPTION = '(deixar vazio)'
WRITE_OPTION = '✍️ escrever valor fixo/manual'
BLANKS = {'', 'nan', 'none', 'null', '<na>'}
_CONTEXT: dict[str, Any] = {'source': None, 'target': None}
SOURCE_KEYS = ('mapeiaai_universal_processed_df', 'mapeiaai_universal_source_df', 'df_origem_unificada', 'df_origem_site', 'df_source')
MODEL_KEYS = ('mapeiaai_universal_model_df', 'home_modelo_universal_df', 'df_modelo_universal', 'modelo_universal_df')
MAPPING_TOGGLE_WIDGET_MARKER_KEY = 'mapeiaai_mapping_preserve_toggle_widget_marker_v1'


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
    if text.startswith(FIXED_VALUE_PREFIX):
        return 'fixo', text
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


def _df_has_columns(df: Any) -> bool:
    return isinstance(df, pd.DataFrame) and len(getattr(df, 'columns', [])) > 0


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
    if isinstance(frame, pd.DataFrame) and _df_has_columns(frame) and (not column or _matching_column(frame, column)):
        return frame
    return _first_session_frame(MODEL_KEYS, column)


def _model_preserve_toggle_enabled() -> bool:
    return bool(st.session_state.get(MODEL_PRESERVE_TOGGLE_KEY, False))


def _dual_enabled() -> bool:
    model = _model_frame()
    return bool(_df_has_columns(model) and _model_preserve_toggle_enabled())


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


def _color_rank(label: object) -> int:
    icon = _icon(label)
    if icon == '🟢':
        return 0
    if icon == '🟡':
        return 1
    if icon == '⚪':
        return 2
    if icon == '🔴':
        return 3
    return 4


def _status_text(status: str, column: str) -> str:
    if status == 'empty':
        return f'coluna {column} vazia' if column else 'coluna vazia'
    return 'nao existe' if status == 'missing' else ''


def _preview_for(kind: str, column: str, icon: str) -> str:
    if kind == 'modelo' and not _dual_enabled():
        status, actual_column, values = _column_state(_source_frame(column), column, limit=2)
        if values:
            return f'{icon} Origem > {actual_column or column}: {_short(values)}'
        return f'{icon} Origem > {column}: {_status_text(status, actual_column or column)}'
    frame = _source_frame(column) if kind == 'origem' else _model_frame(column)
    status, actual_column, values = _column_state(frame, column, limit=2)
    label_kind = 'Origem' if kind == 'origem' else 'Modelo anexado'
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
        return f'{icon} Origem > {clean_column}: {_short(values)}'
    if not _dual_enabled():
        return f'{icon} Origem > {clean_column}: {_status_text(status, actual_column or clean_column)}'
    m_status, m_column, m_values = _column_state(_model_frame(clean_column), clean_column, limit=2)
    if m_values:
        return f'{icon} Modelo anexado > {clean_column}: {_short(m_values)}'
    return f'{icon} Origem > {clean_column}: {_status_text(status, actual_column or clean_column)}; Modelo anexado: {_status_text(m_status, m_column or target_name or clean_column)}'


def _sort_dropdown_options_by_color(options: list[str], labels: dict[str, str]) -> list[str]:
    indexed = {option: index for index, option in enumerate(options)}
    special = {EMPTY_OPTION, WRITE_OPTION}

    def key(option: str) -> tuple[int, int, str]:
        if option in special:
            return (4, indexed.get(option, 9999), str(option).casefold())
        return (_color_rank(labels.get(option, option)), indexed.get(option, 9999), str(labels.get(option, option)).casefold())

    return sorted(options, key=key)


def _ranked_options(options: list[str], labels: dict[str, str], target_name: str, current_value: str = '') -> tuple[list[str], dict[str, str]]:
    if not _dual_enabled():
        clean_options: list[str] = []
        clean_labels: dict[str, str] = {}
        for option in list(options or []):
            if str(option).startswith(MODEL_REF_PREFIX):
                continue
            if option in {EMPTY_OPTION, WRITE_OPTION}:
                clean_options.append(option)
                clean_labels[option] = labels.get(option, option)
                continue
            kind, column = _split_ref(option)
            if kind == 'modelo':
                continue
            plain_option = column if kind == 'origem' and _is_ref(option) else str(option)
            if plain_option not in clean_options:
                clean_options.append(plain_option)
                clean_labels[plain_option] = _preview_label(plain_option, labels.get(option, labels.get(plain_option, '🟡 ' + plain_option)), target_name)
        return _sort_dropdown_options_by_color(clean_options, clean_labels), clean_labels

    source_columns = [str(option) for option in options if option not in {EMPTY_OPTION, WRITE_OPTION} and not _is_ref(option)]
    model_columns = [str(column) for column in getattr(_model_frame(), 'columns', [])]
    new_options: list[str] = []
    new_labels: dict[str, str] = {}

    for column in source_columns:
        token = _ref('origem', column)
        if token not in new_options:
            new_options.append(token)
            new_labels[token] = _preview_label(token, labels.get(column, '🟡 ' + column), target_name)

    for column in model_columns:
        token = _ref('modelo', column)
        if token not in new_options:
            new_options.append(token)
            icon = '🟢' if _norm(column) == _norm(target_name) else '🟡'
            new_labels[token] = _preview_label(token, icon + ' ' + column, target_name)

    current_value = str(current_value or '').strip()
    if _is_ref(current_value) and current_value not in new_options:
        kind, column = _split_ref(current_value)
        token = _ref(kind, column)
        new_options.append(token)
        new_labels[token] = _preview_label(token, '🟡 ' + column, target_name)

    for special in (EMPTY_OPTION, WRITE_OPTION):
        if special in options and special not in new_options:
            new_options.append(special)
            new_labels[special] = special

    return _sort_dropdown_options_by_color(new_options, new_labels), new_labels


def _origin_green_candidates_for_target(target_name: str, source_columns: list[str]) -> list[str]:
    target_key = _norm(target_name)
    if not target_key:
        return []
    out: list[str] = []
    for column in [str(column) for column in source_columns]:
        if _norm(column) == target_key:
            out.append(_ref('origem', column))
    return list(dict.fromkeys(out))


def _auto_bind_unique_origin_green_matches(current: dict[str, str], target_columns: list[str], source_columns: list[str]) -> tuple[dict[str, str], int]:
    updated = dict(current or {})
    applied = 0
    ambiguous = 0
    model_green_only = 0
    preserved = 0
    for target_name in [str(column) for column in target_columns]:
        current_value = str(updated.get(target_name, '') or '').strip()
        if current_value:
            preserved += 1
            continue
        origin_candidates = _origin_green_candidates_for_target(target_name, source_columns)
        model_has_same_name = bool(_dual_enabled() and any(_norm(column) == _norm(target_name) for column in [str(column) for column in getattr(_model_frame(), 'columns', [])]))
        if len(origin_candidates) == 1:
            updated[target_name] = origin_candidates[0]
            applied += 1
        elif len(origin_candidates) > 1:
            ambiguous += 1
        elif model_has_same_name:
            model_green_only += 1
    try:
        add_audit_event('mapping_auto_bind_unique_origin_green_applied', area='MAPEAMENTO', status='OK', details={'applied': int(applied), 'ambiguous_origin_green_fields': int(ambiguous), 'model_green_only_not_autobound': int(model_green_only), 'preserved_existing_choices': int(preserved), 'rule': 'apenas_um_candidato_verde_da_origem_autovincula', 'responsible_file': RESPONSIBLE_FILE})
    except Exception:
        pass
    return updated, applied


def _restore_dataframe_preview_if_previous_patch_expanded_it() -> None:
    original_dataframe = getattr(st, '_mapeiaai_original_dataframe', None)
    current_version = str(getattr(st, '_mapeiaai_full_table_preview_runtime_version', '') or '')
    if callable(original_dataframe) and current_version and current_version != 'removed_by_v12_color_rank_unique_origin_green_autobind':
        st.dataframe = original_dataframe
        st._mapeiaai_full_table_preview_runtime_version = 'removed_by_v12_color_rank_unique_origin_green_autobind'


def _clear_legacy_unscoped_mapping_values(mapping_state_key: str) -> int:
    mapping = st.session_state.get(mapping_state_key)
    if not isinstance(mapping, dict) or not _dual_enabled():
        return 0
    changed = 0
    cleaned: dict[str, str] = {}
    for target, selected in dict(mapping).items():
        text = str(selected or '').strip()
        if text and not _is_ref(text) and not text.startswith(FIXED_VALUE_PREFIX):
            cleaned[str(target)] = ''
            changed += 1
        else:
            cleaned[str(target)] = text
    if changed:
        st.session_state[mapping_state_key] = cleaned
        add_audit_event('mapping_dropdown_legacy_unscoped_values_cleared', area='MAPEAMENTO', status='OK', details={'changed_fields': int(changed), 'reason': 'origem_modelo_devem_ficar_separados_sem_mesclar_nomes_iguais', 'responsible_file': RESPONSIBLE_FILE})
    return changed


def _clear_model_refs_when_toggle_disabled(mapping_state_key: str) -> int:
    mapping = st.session_state.get(mapping_state_key)
    if not isinstance(mapping, dict) or _dual_enabled():
        return 0
    changed = 0
    cleaned: dict[str, str] = {}
    for target, selected in dict(mapping).items():
        text = str(selected or '').strip()
        kind, column = _split_ref(text)
        if kind == 'modelo':
            cleaned[str(target)] = ''
            changed += 1
        elif kind == 'origem' and text.startswith(ORIGIN_REF_PREFIX):
            cleaned[str(target)] = column
            changed += 1
        else:
            cleaned[str(target)] = text
    if changed:
        st.session_state[mapping_state_key] = cleaned
        add_audit_event('mapping_dropdown_model_refs_removed_toggle_off', area='MAPEAMENTO', status='OK', details={'changed_fields': int(changed), 'reason': 'toggle_preservar_dados_modelo_desligado_nao_exibe_nem_usa_campos_modelo', 'responsible_file': RESPONSIBLE_FILE})
    return changed


def _reset_mapping_widgets_when_toggle_changes(key_prefix: str, signature: str, enabled: bool) -> int:
    marker = f'{MAPPING_TOGGLE_WIDGET_MARKER_KEY}_{key_prefix}_{_norm(signature)[:80]}'
    previous = st.session_state.get(marker)
    if previous is not None and bool(previous) == bool(enabled):
        return 0
    st.session_state[marker] = bool(enabled)
    removed = 0
    for key in list(st.session_state.keys()):
        text = str(key)
        if text.startswith(f'{key_prefix}_map_') or text.startswith(f'{key_prefix}_mapping_page_') or text.startswith(f'{key_prefix}_mapping_scroll_'):
            st.session_state.pop(key, None)
            removed += 1
    if removed:
        add_audit_event('mapping_dropdown_widgets_reset_after_preserve_toggle_change', area='MAPEAMENTO', status='OK', details={'removed_keys': int(removed), 'preserve_toggle_enabled': bool(enabled), 'responsible_file': RESPONSIBLE_FILE})
    return removed


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
            return _ranked_options(list(options or []), dict(labels or {}), str(target_name or ''), str(current_value or ''))
        ranked_with_real_preview._mapeiaai_dropdown_preview_ranked = True
        shared_mapping._ranked_source_options = ranked_with_real_preview

    if hasattr(shared_mapping, '_auto_bind_exact_green_matches'):
        original_auto_bind = getattr(shared_mapping, '_mapeiaai_original_auto_bind_exact_green_matches', None) or shared_mapping._auto_bind_exact_green_matches
        setattr(shared_mapping, '_mapeiaai_original_auto_bind_exact_green_matches', original_auto_bind)
        _auto_bind_unique_origin_green_matches._mapeiaai_auto_bind_unique_origin_green = True
        shared_mapping._auto_bind_exact_green_matches = _auto_bind_unique_origin_green_matches

    if hasattr(shared_mapping, '_apply_price_calculator_mapping_hint'):
        original_price_hint = getattr(shared_mapping, '_mapeiaai_original_apply_price_calculator_mapping_hint', None) or shared_mapping._apply_price_calculator_mapping_hint
        setattr(shared_mapping, '_mapeiaai_original_apply_price_calculator_mapping_hint', original_price_hint)

        def price_calculator_hint_visual_only_when_dual(current, source, target):
            if _dual_enabled():
                return dict(current or {})
            return original_price_hint(current, source, target)

        shared_mapping._apply_price_calculator_mapping_hint = price_calculator_hint_visual_only_when_dual

    if hasattr(shared_mapping, 'confidence_flag'):
        original_confidence = getattr(shared_mapping, '_mapeiaai_original_confidence_flag', None) or shared_mapping.confidence_flag
        setattr(shared_mapping, '_mapeiaai_original_confidence_flag', original_confidence)

        def confidence_flag_with_refs(target, source_column, source):
            kind, column = _split_ref(source_column)
            if kind == 'modelo':
                if not _dual_enabled():
                    return '🔴 modelo oculto'
                if _norm(target) == _norm(column):
                    return '🟢 modelo anexado'
                return '🟡 modelo anexado'
            if kind == 'origem':
                return original_confidence(target, column, source)
            return original_confidence(target, source_column, source)

        shared_mapping.confidence_flag = confidence_flag_with_refs

    preview_base = shared_mapping._render_mapping_preview
    if not getattr(preview_base, '_mapeiaai_dropdown_preview_caption', False):
        def render_mapping_preview_with_model_fallback(target_name, selected_value, source):
            selected = str(selected_value or '').strip()
            if selected and not shared_mapping.is_fixed_value(selected):
                kind, column = _split_ref(selected)
                if kind == 'modelo' and not _dual_enabled():
                    shared_mapping.st.caption(f'🔴 **{target_name}**. Modelo anexado oculto porque o toggle Preservar dados do modelo está desligado.')
                    return
                frame = _source_frame(column) if kind == 'origem' else _model_frame(column)
                status, actual_column, samples = _column_state(frame, column, limit=3)
                icon = shared_mapping.confidence_flag(str(target_name or ''), selected, source).split()[0]
                if samples:
                    label_kind = 'origem' if kind == 'origem' else 'modelo anexado'
                    shared_mapping.st.caption(f'{icon} **{target_name}**. Previa da {label_kind} ({actual_column}): {_short(samples, 150)}')
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
                dual = _dual_enabled()
                _reset_mapping_widgets_when_toggle_changes(key_prefix, signature, dual)
                if dual:
                    _clear_legacy_unscoped_mapping_values(mapping_state_key)
                    st.caption('Modelo anexado preservado: dropdown mostra Origem e Modelo anexado separados. Auto vinculo so aplica quando existir uma unica opcao 🟢 da Origem.')
                else:
                    _clear_model_refs_when_toggle_disabled(mapping_state_key)
                    st.caption('Preservar dados do modelo desligado: dropdown mostra somente colunas da Origem.')
                return render_base(source, target, signature=signature, mapping_state_key=mapping_state_key, engine_state_key=engine_state_key, key_prefix=key_prefix, ai_enabled=ai_enabled)
            finally:
                _CONTEXT['source'], _CONTEXT['target'] = previous_source, previous_target
        render_with_context._mapeiaai_dropdown_preview_render = True
        shared_mapping.render_shared_contract_mapping = render_with_context

    shared_mapping._mapeiaai_dropdown_preview_runtime_version = PATCH_VERSION
    add_audit_event('mapping_dropdown_preview_runtime_installed', area='MAPEAMENTO', status='OK', details={'version': PATCH_VERSION, 'model_options_only_when_preserve_toggle_on': True, 'dropdown_color_rank': True, 'auto_green_unique_origin_only': True, 'model_green_visual_only': True, 'ambiguous_origin_green_requires_user_choice': True, 'unscoped_legacy_mapping_cleared': True, 'stale_model_refs_cleared_when_toggle_off': True, 'responsible_file': RESPONSIBLE_FILE})


__all__ = ['install_mapping_dropdown_preview_runtime']
