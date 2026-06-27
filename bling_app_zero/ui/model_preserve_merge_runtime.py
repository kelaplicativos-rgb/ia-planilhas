from __future__ import annotations

from typing import Any, Mapping

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.universal.output_builder import build_universal_output as _raw_build_universal_output

RESPONSIBLE_FILE = 'bling_app_zero/ui/model_preserve_merge_runtime.py'
MODEL_PRESERVE_TOGGLE_KEY = 'mapeiaai_model_preserve_data_toggle_v1'
PRESERVE_MODEL_ENABLED_KEY = 'mapeiaai_preserve_model_data_enabled'
PRESERVE_MODEL_KEY_COLUMN_KEY = 'mapeiaai_preserve_model_data_key_column'
ORIGIN_REF_PREFIX = 'origem::'
MODEL_REF_PREFIX = 'modelo::'
FIXED_VALUE_PREFIX = '__mapeiaai_fixed_value__:'
_BLANK_MARKERS = {'', 'nan', 'none', 'null', '<na>'}


def _plain_key(value: object) -> str:
    text = str(value or '').strip().lower()
    for old, new in {'ã': 'a', 'á': 'a', 'à': 'a', 'â': 'a', 'é': 'e', 'ê': 'e', 'í': 'i', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ú': 'u', 'ç': 'c'}.items():
        text = text.replace(old, new)
    return ''.join(ch for ch in text if ch.isalnum())


def _is_blank(value: object) -> bool:
    return str(value or '').strip().casefold() in _BLANK_MARKERS


def _df_has_values(df: Any) -> bool:
    try:
        frame = df.fillna('').astype(str)
        return bool(frame.apply(lambda col: col.str.strip().ne('').any()).any())
    except Exception:
        return False


def _split_ref(value: object) -> tuple[str, str]:
    text = str(value or '').strip()
    if text.startswith(ORIGIN_REF_PREFIX):
        return 'origem', text[len(ORIGIN_REF_PREFIX):].strip()
    if text.startswith(MODEL_REF_PREFIX):
        return 'modelo', text[len(MODEL_REF_PREFIX):].strip()
    if text.startswith(FIXED_VALUE_PREFIX):
        return 'fixo', text
    if text:
        return 'origem', text
    return 'vazio', ''


def _mapping_for_origin_builder(mapping: Mapping[str, str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for target, selected in dict(mapping or {}).items():
        kind, column = _split_ref(selected)
        if kind == 'origem':
            out[str(target)] = column
        elif kind == 'fixo':
            out[str(target)] = column
        else:
            out[str(target)] = ''
    return out


def _origin_update_targets(mapping: Mapping[str, str] | None, columns: list[str]) -> set[str]:
    out: set[str] = set()
    data = dict(mapping or {})
    for column in columns:
        kind, selected = _split_ref(data.get(column, ''))
        if kind in {'origem', 'fixo'} and str(selected or '').strip():
            out.add(column)
    return out


def _model_copy_targets(mapping: Mapping[str, str] | None, columns: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    data = dict(mapping or {})
    for target in columns:
        kind, selected = _split_ref(data.get(target, ''))
        if kind == 'modelo' and selected:
            out[target] = selected
    return out


def _has_model_copy_choice(mapping: Mapping[str, str] | None, columns: list[str]) -> bool:
    return bool(_model_copy_targets(mapping, columns))


def _column_keys(df: pd.DataFrame, column: str) -> list[str]:
    if column not in df.columns:
        return []
    keys: list[str] = []
    try:
        for value in df[column].fillna('').astype(str).tolist():
            key = _plain_key(value)
            if key:
                keys.append(key)
    except Exception:
        return []
    return keys


def _key_priority(column: str) -> int:
    key = _plain_key(column)
    if key in {'codigo', 'codigosku', 'sku', 'codigoproduto', 'codproduto'}:
        return 0
    if key == 'idproduto':
        return 1
    if key in {'idnaloja', 'idloja', 'idprodutoexterno'}:
        return 2
    if key in {'gtin', 'ean'}:
        return 3
    if 'referencia' in key or key == 'ref':
        return 4
    if key == 'nome':
        return 20
    return 10


def _best_merge_key(base: pd.DataFrame, mapped: pd.DataFrame, current_key: str) -> str:
    common = [str(col) for col in base.columns if str(col) in mapped.columns]
    if not common:
        return ''

    def stats(column: str) -> tuple[int, int, int, int]:
        base_keys = _column_keys(base, column)
        mapped_keys = _column_keys(mapped, column)
        base_set = set(base_keys)
        mapped_set = set(mapped_keys)
        overlap = len(base_set & mapped_set)
        usable = min(len(base_keys), len(mapped_keys))
        priority = _key_priority(column)
        return overlap, usable, -priority, -common.index(column)

    current_key = str(current_key or '').strip()
    if current_key in common:
        overlap, usable, _priority, _pos = stats(current_key)
        if overlap > 0:
            return current_key
    ranked = sorted(common, key=stats, reverse=True)
    if not ranked:
        return current_key if current_key in common else ''
    best = ranked[0]
    best_overlap, best_usable, _priority, _pos = stats(best)
    if best_overlap > 0:
        return best
    if current_key in common and stats(current_key)[1] > 0:
        return current_key
    return best if best_usable > 0 else ''


def _append_missing_columns(base: pd.DataFrame, mapped: pd.DataFrame) -> pd.DataFrame:
    out = base.copy().fillna('')
    for column in mapped.columns:
        if column not in out.columns:
            out[column] = ''
    return out.loc[:, list(mapped.columns)].fillna('').reset_index(drop=True)


def _apply_model_choices_to_base(base: pd.DataFrame, mapping: Mapping[str, str] | None) -> pd.DataFrame:
    out = base.copy().fillna('')
    for target, model_column in _model_copy_targets(mapping, list(out.columns)).items():
        if model_column in out.columns and target in out.columns:
            out[target] = out[model_column].fillna('').astype(str).values
    return out


def _merge_preserving_model(df_source: pd.DataFrame, df_model: pd.DataFrame, mapping: Mapping[str, str] | None) -> pd.DataFrame:
    origin_mapping = _mapping_for_origin_builder(mapping)
    mapped = _raw_build_universal_output(df_source, df_model, origin_mapping).copy().fillna('')
    model_columns = [str(column) for column in getattr(df_model, 'columns', [])]
    model_choice_enabled = _has_model_copy_choice(mapping, model_columns)
    preserve_enabled = (bool(st.session_state.get(MODEL_PRESERVE_TOGGLE_KEY, False)) and _df_has_values(df_model)) or model_choice_enabled
    if not preserve_enabled:
        st.session_state[PRESERVE_MODEL_ENABLED_KEY] = False
        return mapped

    st.session_state[PRESERVE_MODEL_ENABLED_KEY] = True
    base = _append_missing_columns(df_model.copy().fillna(''), mapped)
    base = _apply_model_choices_to_base(base, mapping)
    if base.empty:
        return mapped

    selected_key = str(st.session_state.get(PRESERVE_MODEL_KEY_COLUMN_KEY) or '').strip()
    key_column = _best_merge_key(base, mapped, selected_key)
    if not key_column:
        add_audit_event('model_preserve_merge_no_key', area='UNIVERSAL', status='AVISO', details={'selected_key': selected_key, 'model_choice_enabled': bool(model_choice_enabled), 'responsible_file': RESPONSIBLE_FILE})
        return base
    if key_column != selected_key:
        st.session_state[PRESERVE_MODEL_KEY_COLUMN_KEY] = key_column
        add_audit_event('model_preserve_merge_key_auto_adjusted', area='UNIVERSAL', status='OK', details={'selected_key': selected_key, 'chosen_key': key_column, 'reason': 'melhor_chave_com_sobreposicao_real', 'responsible_file': RESPONSIBLE_FILE})

    update_columns = _origin_update_targets(mapping, list(mapped.columns))
    if not update_columns:
        return base

    index_by_key: dict[str, list[int]] = {}
    for idx, value in enumerate(base[key_column].tolist()):
        key = _plain_key(value)
        if key:
            index_by_key.setdefault(key, []).append(idx)

    out = base.copy().fillna('')
    matched_rows = 0
    appended_rows = 0
    skipped_blank_preserved = 0
    duplicate_key_updates = 0

    for _, row in mapped.iterrows():
        key = _plain_key(row.get(key_column, ''))
        if not key:
            continue
        target_rows = index_by_key.get(key) or []
        if target_rows:
            matched_rows += len(target_rows)
            if len(target_rows) > 1:
                duplicate_key_updates += len(target_rows)
            for target_row in target_rows:
                for column in update_columns:
                    new_value = '' if row.get(column) is None else str(row.get(column))
                    if _is_blank(new_value):
                        skipped_blank_preserved += 1
                        continue
                    out.at[target_row, column] = new_value
            continue
        new_row = {column: '' if row.get(column) is None else str(row.get(column)) for column in out.columns}
        out = pd.concat([out, pd.DataFrame([new_row], columns=list(out.columns))], ignore_index=True)
        index_by_key[key] = [len(out) - 1]
        appended_rows += 1

    add_audit_event('model_preserve_merge_runtime_applied', area='UNIVERSAL', status='OK', details={'rows_model': int(len(base)), 'rows_origin_mapped': int(len(mapped)), 'rows_output': int(len(out)), 'key_column': key_column, 'matched_rows': int(matched_rows), 'appended_rows': int(appended_rows), 'duplicate_key_updates': int(duplicate_key_updates), 'skipped_blank_preserved_fields': int(skipped_blank_preserved), 'model_choice_enabled': bool(model_choice_enabled), 'dual_source_mapping': True, 'responsible_file': RESPONSIBLE_FILE})
    return out


def _install_green_mapping_guard() -> None:
    try:
        from bling_app_zero.ui.mapping_dropdown_preview_runtime import install_mapping_dropdown_preview_runtime
        install_mapping_dropdown_preview_runtime()
    except Exception as exc:
        add_audit_event('model_preserve_preview_runtime_failed', area='MAPEAMENTO', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})


def install_model_preserve_merge_runtime() -> None:
    try:
        import bling_app_zero.ui as ui_root
        from bling_app_zero.core import final_output_engine
    except Exception as exc:
        add_audit_event('model_preserve_merge_runtime_import_failed', area='UNIVERSAL', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
        return

    final_output_engine.build_universal_output = lambda df_source, df_model, mapping=None: _merge_preserving_model(df_source, df_model, mapping)
    ui_root._apply_model_preserve = lambda df_source, df_model, mapping=None, original_builder=None: _merge_preserving_model(df_source, df_model, mapping)
    _install_green_mapping_guard()
    add_audit_event('model_preserve_merge_runtime_installed', area='UNIVERSAL', status='OK', details={'preserve_all_against_blank_source': True, 'duplicate_key_update': True, 'best_key_selection': True, 'model_choice_enables_preserve': True, 'dual_source_mapping': True, 'dropdown_preview_runtime': True, 'responsible_file': RESPONSIBLE_FILE})


__all__ = ['install_model_preserve_merge_runtime']
