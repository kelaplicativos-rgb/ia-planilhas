from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/mapping_green_preserve_runtime.py'
MODEL_PRESERVE_TOGGLE_KEY = 'mapeiaai_model_preserve_data_toggle_v1'
PATCH_VERSION = 'campo_valor_preview_v3'
BLANKS = {'', 'nan', 'none', 'null', '<na>'}
CTX: dict[str, Any] = {'source': None, 'target': None}


def blank(value: object) -> bool:
    return str(value or '').strip().casefold() in BLANKS


def values(df: Any, col: str, limit: int = 2) -> list[str]:
    if not isinstance(df, pd.DataFrame) or not col or col not in df.columns:
        return []
    out: list[str] = []
    try:
        for raw in df[col].dropna().astype(str).tolist():
            text = str(raw or '').replace('\t', ' ').replace('\n', ' ').strip()
            while '  ' in text:
                text = text.replace('  ', ' ')
            if blank(text):
                continue
            if text not in out:
                out.append(text)
            if len(out) >= limit:
                break
    except Exception:
        return []
    return out


def preview(df: Any, col: str) -> str:
    txt = ' | '.join(values(df, col))
    return txt if len(txt) <= 72 else txt[:71].rstrip() + '…'


def has_values(df: Any, col: str) -> bool:
    return bool(values(df, col, limit=1))


def icon(label: object) -> str:
    text = str(label or '').strip()
    for mark in ('🟢', '🟡', '🔴', '⚪'):
        if text.startswith(mark):
            return mark
    return '🟡'


def unsafe_preserve(target_col: str, source_col: str) -> bool:
    if not bool(st.session_state.get(MODEL_PRESERVE_TOGGLE_KEY, False)):
        return False
    source = CTX.get('source')
    target = CTX.get('target')
    return bool(has_values(target, target_col) and not has_values(source, source_col))


def clean_mapping(data: dict[str, str]) -> tuple[dict[str, str], int]:
    out = dict(data or {})
    removed = 0
    for target_col, source_col in list(out.items()):
        source_col = str(source_col or '').strip()
        if not source_col or source_col.startswith('__mapeiaai_fixed_value__:'):
            continue
        if unsafe_preserve(str(target_col), source_col):
            out[str(target_col)] = ''
            removed += 1
    return out, removed


def make_label(source_col: str, current_label: object, target_col: str) -> str:
    if unsafe_preserve(str(target_col), str(source_col)):
        model_prev = preview(CTX.get('target'), str(target_col))
        return f'🟡 {source_col}: origem vazia / preservar modelo' + (f' ({model_prev})' if model_prev else '')
    prev = preview(CTX.get('source'), str(source_col))
    if prev:
        return f'{icon(current_label)} {source_col}: {prev}'
    return f'🟡 {source_col}: sem previa na origem'


def install_mapping_green_preserve_runtime() -> None:
    try:
        from bling_app_zero.ui import shared_mapping
    except Exception as exc:
        add_audit_event('mapping_green_preserve_runtime_import_failed', area='MAPEAMENTO', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
        return

    if getattr(shared_mapping, '_mapeiaai_green_preserve_runtime_version', '') == PATCH_VERSION:
        return

    original_render = shared_mapping.render_shared_contract_mapping
    original_auto = shared_mapping._auto_bind_exact_green_matches
    original_rank = shared_mapping._ranked_source_options

    def auto_green(current: dict[str, str], target_columns: list[str], source_columns: list[str]) -> tuple[dict[str, str], int]:
        candidate, count = original_auto(current, target_columns, source_columns)
        clean, removed = clean_mapping(candidate)
        if removed:
            add_audit_event('mapping_auto_green_blank_source_skipped', area='MAPEAMENTO', status='OK', details={'removed_blank_source_links': int(removed), 'responsible_file': RESPONSIBLE_FILE})
        return clean, max(0, int(count) - int(removed))

    def ranked(target_name: str, current_value: str, source_columns: list[str], suggestions_index: dict[str, dict[str, Any]], source_profiles: dict[str, dict[str, float]] | None = None):
        opts, labels = original_rank(target_name, current_value, source_columns, suggestions_index, source_profiles)
        labels = dict(labels or {})
        for col in list(source_columns or []):
            if col in labels:
                labels[col] = make_label(str(col), labels[col], str(target_name))
        return opts, labels

    def render(source: pd.DataFrame, target: pd.DataFrame, *, signature: str, mapping_state_key: str, engine_state_key: str, key_prefix: str = 'mapeiaai_shared', ai_enabled: bool = True):
        prev_source = CTX.get('source')
        prev_target = CTX.get('target')
        CTX['source'] = source
        CTX['target'] = target
        try:
            current = st.session_state.get(mapping_state_key)
            if isinstance(current, dict):
                clean, removed = clean_mapping(current)
                if removed:
                    st.session_state[mapping_state_key] = clean
                    add_audit_event('mapping_blank_source_link_removed_before_render', area='MAPEAMENTO', status='OK', details={'removed_blank_source_links': int(removed), 'responsible_file': RESPONSIBLE_FILE})
            edited = original_render(source, target, signature=signature, mapping_state_key=mapping_state_key, engine_state_key=engine_state_key, key_prefix=key_prefix, ai_enabled=ai_enabled)
            if isinstance(edited, dict):
                clean, removed = clean_mapping(edited)
                if removed:
                    st.session_state[mapping_state_key] = clean
                    edited = clean
                    add_audit_event('mapping_blank_source_link_removed_after_render', area='MAPEAMENTO', status='OK', details={'removed_blank_source_links': int(removed), 'responsible_file': RESPONSIBLE_FILE})
            return dict(edited or {})
        finally:
            CTX['source'] = prev_source
            CTX['target'] = prev_target

    shared_mapping._auto_bind_exact_green_matches = auto_green
    shared_mapping._ranked_source_options = ranked
    shared_mapping.render_shared_contract_mapping = render
    shared_mapping._mapeiaai_green_preserve_runtime_version = PATCH_VERSION
    shared_mapping._mapeiaai_green_preserve_runtime_patched = True
    add_audit_event('mapping_green_preserve_runtime_installed', area='MAPEAMENTO', status='OK', details={'format': 'Campo: valor real', 'version': PATCH_VERSION, 'responsible_file': RESPONSIBLE_FILE})


__all__ = ['install_mapping_green_preserve_runtime']
