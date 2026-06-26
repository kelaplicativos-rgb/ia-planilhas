from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/mapping_green_preserve_runtime.py'
MODEL_PRESERVE_TOGGLE_KEY = 'mapeiaai_model_preserve_data_toggle_v1'
_BLANK_MARKERS = {'', 'nan', 'none', 'null', '<na>'}
_CONTEXT: dict[str, Any] = {'source': None, 'target': None}


def _is_blank(value: object) -> bool:
    return str(value or '').strip().casefold() in _BLANK_MARKERS


def _column_has_values(df: Any, column: str) -> bool:
    if not isinstance(df, pd.DataFrame) or not column or column not in df.columns:
        return False
    try:
        return bool(df[column].fillna('').astype(str).map(lambda value: not _is_blank(value)).any())
    except Exception:
        return False


def _sample_values(df: Any, column: str, limit: int = 2) -> list[str]:
    if not isinstance(df, pd.DataFrame) or not column or column not in df.columns:
        return []
    values: list[str] = []
    try:
        for value in df[column].dropna().astype(str).tolist():
            text = str(value or '').replace('\t', '').strip()
            if not text or text.casefold() in _BLANK_MARKERS:
                continue
            if text not in values:
                values.append(text)
            if len(values) >= limit:
                break
    except Exception:
        return []
    return values


def _short_preview(values: list[str], max_chars: int = 64) -> str:
    text = ' | '.join(values)
    return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + '…'


def _source_preview(source_column: str) -> str:
    values = _sample_values(_CONTEXT.get('source'), source_column)
    return _short_preview(values) if values else ''


def _target_preview(target_name: str) -> str:
    values = _sample_values(_CONTEXT.get('target'), target_name)
    return _short_preview(values) if values else ''


def _target_has_values(target_name: str) -> bool:
    target = _CONTEXT.get('target')
    return _column_has_values(target, target_name)


def _source_has_values(source_column: str) -> bool:
    source = _CONTEXT.get('source')
    return _column_has_values(source, source_column)


def _unsafe_blank_source_for_preserved_model(target_name: str, source_column: str) -> bool:
    if not bool(st.session_state.get(MODEL_PRESERVE_TOGGLE_KEY, False)):
        return False
    if not target_name or not source_column:
        return False
    return bool(_target_has_values(target_name) and not _source_has_values(source_column))


def _sanitize_mapping(current: dict[str, str]) -> tuple[dict[str, str], int]:
    clean = dict(current or {})
    changed = 0
    for target_name, source_column in list(clean.items()):
        source_column = str(source_column or '').strip()
        if not source_column or source_column.startswith('__mapeiaai_fixed_value__:'):
            continue
        if _unsafe_blank_source_for_preserved_model(str(target_name), source_column):
            clean[str(target_name)] = ''
            changed += 1
    return clean, changed


def _leading_icon(label: str) -> str:
    text = str(label or '').strip()
    if text.startswith('🟢'):
        return '🟢'
    if text.startswith('🟡'):
        return '🟡'
    if text.startswith('🔴'):
        return '🔴'
    if text.startswith('⚪'):
        return '⚪'
    return '⚪'


def _labels_with_real_preview(labels: dict[str, str], source_columns: list[str], target_name: str, unsafe: set[str]) -> dict[str, str]:
    updated = dict(labels or {})
    for column in source_columns:
        if column not in updated:
            continue
        if column in unsafe:
            model_preview = _target_preview(target_name)
            suffix = f' · origem vazia / preservar modelo: {model_preview}' if model_preview else ' · origem vazia / preservar modelo'
            updated[column] = f'🟡 {column}{suffix}'
            continue
        preview = _source_preview(column)
        if preview:
            icon = _leading_icon(str(updated.get(column) or ''))
            updated[column] = f'{icon} {column} · {preview}'
    return updated


def install_mapping_green_preserve_runtime() -> None:
    try:
        from bling_app_zero.ui import shared_mapping
    except Exception as exc:
        add_audit_event('mapping_green_preserve_runtime_import_failed', area='MAPEAMENTO', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
        return

    if getattr(shared_mapping, '_mapeiaai_green_preserve_runtime_patched', False):
        return

    original_render = shared_mapping.render_shared_contract_mapping
    original_auto_bind = shared_mapping._auto_bind_exact_green_matches
    original_ranked_options = shared_mapping._ranked_source_options

    def auto_bind_exact_green_matches_no_blank(current: dict[str, str], target_columns: list[str], source_columns: list[str]) -> tuple[dict[str, str], int]:
        # O auto-vinculo verde so pode vincular origem com valor util.
        # Ele nao pode selecionar uma coluna vazia da origem quando o modelo ja tem dados.
        candidate, applied = original_auto_bind(current, target_columns, source_columns)
        sanitized, removed = _sanitize_mapping(candidate)
        if removed:
            add_audit_event(
                'mapping_auto_green_blank_source_skipped',
                area='MAPEAMENTO',
                status='OK',
                details={
                    'removed_blank_source_links': int(removed),
                    'reason': 'auto_vinculo_verde_nao_pode_apagar_dados_preservados_do_modelo',
                    'responsible_file': RESPONSIBLE_FILE,
                },
            )
        return sanitized, max(0, int(applied) - int(removed))

    def ranked_source_options_no_blank_green(target_name: str, current_value: str, source_columns: list[str], suggestions_index: dict[str, dict[str, Any]], source_profiles: dict[str, dict[str, float]] | None = None):
        options, labels = original_ranked_options(target_name, current_value, source_columns, suggestions_index, source_profiles)
        unsafe = {option for option in list(options) if option in source_columns and _unsafe_blank_source_for_preserved_model(str(target_name), str(option))}
        if unsafe:
            # Tira a coluna vazia do topo verde. Ela continua disponível no dropdown para decisão manual,
            # mas o sistema não sugere nem auto-seleciona como vínculo verde.
            options = [option for option in options if option not in unsafe]
            insert_at = 0
            try:
                empty_index = options.index(shared_mapping.EMPTY_OPTION)
                write_index = options.index(shared_mapping.WRITE_OPTION)
                insert_at = max(empty_index, write_index) + 1
            except Exception:
                insert_at = min(2, len(options))
            for offset, option in enumerate(unsafe):
                options.insert(min(insert_at + offset, len(options)), option)
        labels = _labels_with_real_preview(labels, source_columns, str(target_name), unsafe)
        return options, labels

    def render_shared_contract_mapping_green_preserve(source: pd.DataFrame, target: pd.DataFrame, *, signature: str, mapping_state_key: str, engine_state_key: str, key_prefix: str = 'mapeiaai_shared', ai_enabled: bool = True) -> dict[str, str]:
        previous_source = _CONTEXT.get('source')
        previous_target = _CONTEXT.get('target')
        _CONTEXT['source'] = source
        _CONTEXT['target'] = target
        try:
            current = st.session_state.get(mapping_state_key)
            if isinstance(current, dict):
                sanitized, removed = _sanitize_mapping(current)
                if removed:
                    st.session_state[mapping_state_key] = sanitized
                    add_audit_event(
                        'mapping_blank_source_link_removed_before_render',
                        area='MAPEAMENTO',
                        status='OK',
                        details={
                            'removed_blank_source_links': int(removed),
                            'mapping_state_key': mapping_state_key,
                            'reason': 'preservar_modelo_quando_origem_idêntica_esta_vazia',
                            'responsible_file': RESPONSIBLE_FILE,
                        },
                    )
            edited = original_render(source, target, signature=signature, mapping_state_key=mapping_state_key, engine_state_key=engine_state_key, key_prefix=key_prefix, ai_enabled=ai_enabled)
            if isinstance(edited, dict):
                sanitized, removed = _sanitize_mapping(edited)
                if removed:
                    st.session_state[mapping_state_key] = sanitized
                    edited = sanitized
                    add_audit_event(
                        'mapping_blank_source_link_removed_after_render',
                        area='MAPEAMENTO',
                        status='OK',
                        details={
                            'removed_blank_source_links': int(removed),
                            'mapping_state_key': mapping_state_key,
                            'reason': 'auto_vinculo_verde_nao_pode_apagar_dados_do_modelo',
                            'responsible_file': RESPONSIBLE_FILE,
                        },
                    )
            return dict(edited or {})
        finally:
            _CONTEXT['source'] = previous_source
            _CONTEXT['target'] = previous_target

    shared_mapping._auto_bind_exact_green_matches = auto_bind_exact_green_matches_no_blank
    shared_mapping._ranked_source_options = ranked_source_options_no_blank_green
    shared_mapping.render_shared_contract_mapping = render_shared_contract_mapping_green_preserve
    shared_mapping._mapeiaai_green_preserve_runtime_patched = True
    add_audit_event('mapping_green_preserve_runtime_installed', area='MAPEAMENTO', status='OK', details={'auto_green_skips_blank_source': True, 'dropdown_real_preview': True, 'preserve_model_toggle_key': MODEL_PRESERVE_TOGGLE_KEY, 'responsible_file': RESPONSIBLE_FILE})


__all__ = ['install_mapping_green_preserve_runtime']
