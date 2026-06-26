from __future__ import annotations

from typing import Any

import pandas as pd

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/mapping_dropdown_preview_runtime.py'
PATCH_VERSION = 'dropdown_preview_source_or_model_v2'
BLANKS = {'', 'nan', 'none', 'null', '<na>'}
_CONTEXT: dict[str, Any] = {'source': None, 'target': None}


def _blank(value: object) -> bool:
    return str(value or '').strip().casefold() in BLANKS


def _samples(df: Any, column: str, limit: int = 2) -> list[str]:
    if not isinstance(df, pd.DataFrame) or not column or column not in df.columns:
        return []
    out: list[str] = []
    try:
        for value in df[column].dropna().astype(str).tolist():
            text = str(value or '').replace('\t', ' ').replace('\n', ' ').strip()
            while '  ' in text:
                text = text.replace('  ', ' ')
            if _blank(text):
                continue
            if text not in out:
                out.append(text)
            if len(out) >= limit:
                break
    except Exception:
        return []
    return out


def _short(values: list[str], size: int = 72) -> str:
    text = ' | '.join(values)
    return text if len(text) <= size else text[: size - 1].rstrip() + '…'


def _icon(label: object) -> str:
    text = str(label or '').strip()
    for mark in ('🟢', '🟡', '🔴', '⚪'):
        if text.startswith(mark):
            return mark
    return '🟡'


def _model_samples(column: str, target_name: str = '') -> tuple[str, list[str]]:
    model = _CONTEXT.get('target')
    checked: list[str] = []
    for candidate in (column, target_name):
        candidate = str(candidate or '').strip()
        if candidate and candidate not in checked:
            checked.append(candidate)
    for candidate in checked:
        values = _samples(model, candidate)
        if values:
            return candidate, values
    return '', []


def _preview_label(column: str, current_label: object, target_name: str = '') -> str:
    preview = _short(_samples(_CONTEXT.get('source'), column))
    icon = _icon(current_label)
    if preview:
        return f'{icon} {column}: {preview}'
    model_column, model_values = _model_samples(column, target_name)
    if model_values:
        label = column if model_column == column else f'{column} -> modelo {model_column}'
        return f'{icon} {label}: modelo {_short(model_values)}'
    return f'🟡 {column}: sem previa na origem/modelo'


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

    def ranked_with_real_preview(target_name, current_value, source_columns, suggestions_index, source_profiles=None):
        options, labels = original_ranked(target_name, current_value, source_columns, suggestions_index, source_profiles)
        labels = dict(labels or {})
        for column in list(source_columns or []):
            if column in labels:
                labels[column] = _preview_label(str(column), labels[column], str(target_name or ''))
        return options, labels

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
    shared_mapping.render_shared_contract_mapping = render_with_context
    shared_mapping._mapeiaai_dropdown_preview_runtime_version = PATCH_VERSION
    add_audit_event('mapping_dropdown_preview_runtime_installed', area='MAPEAMENTO', status='OK', details={'format': 'Campo: valor real da origem; fallback para modelo anexado', 'version': PATCH_VERSION, 'responsible_file': RESPONSIBLE_FILE})


__all__ = ['install_mapping_dropdown_preview_runtime']
