from __future__ import annotations

from typing import Any

RESPONSIBLE_FILE = 'bling_app_zero/ui/critical_mapping_visual_patch.py'


def _audit(event: str, *, status: str = 'OK', details: dict[str, Any] | None = None) -> None:
    try:
        from bling_app_zero.core.audit import add_audit_event
        add_audit_event(event, area='UNIVERSAL', status=status, details={**(details or {}), 'responsible_file': RESPONSIBLE_FILE})
    except Exception:
        pass


def _is_critical_target(shared_mapping: Any, target_name: str) -> bool:
    try:
        return bool(
            shared_mapping._is_category_field(target_name)
            or shared_mapping._is_tag_field(target_name)
            or shared_mapping._is_parent_code_field(target_name)
        )
    except Exception:
        return False


def install() -> None:
    try:
        from bling_app_zero.ui import shared_mapping
    except Exception as exc:
        _audit('critical_mapping_visual_patch_import_failed', status='AVISO', details={'error': str(exc)[:220]})
        return

    if getattr(shared_mapping, '_mapeiaai_critical_mapping_visual_patched', False):
        return

    original_ranked = shared_mapping._ranked_source_options

    def _ranked_source_options_clean(
        target_name: str,
        current_value: str,
        source_columns: list[str],
        suggestions_index: dict[str, dict[str, Any]],
        source_profiles: dict[str, dict[str, float]] | None = None,
    ):
        options, labels = original_ranked(target_name, current_value, source_columns, suggestions_index, source_profiles)
        is_critical = _is_critical_target(shared_mapping, str(target_name))
        if is_critical:
            for column in source_columns:
                same = shared_mapping._same_words_case_insensitive(target_name, column)
                labels[column] = f'🟢⚠️ {column}' if same else f'⚠️ {column}'
        return options, labels

    def _auto_bind_green_only(current: dict[str, str], target_columns: list[str], source_columns: list[str]):
        lookup: dict[tuple[str, ...], str] = {}
        for source_column in source_columns:
            key = shared_mapping._word_tuple(source_column)
            if key and key not in lookup:
                lookup[key] = source_column
        updated = dict(current or {})
        applied = 0
        for target_name in target_columns:
            if _is_critical_target(shared_mapping, str(target_name)):
                continue
            key = shared_mapping._word_tuple(target_name)
            source_column = lookup.get(key)
            if not source_column:
                continue
            current_value = str(updated.get(target_name, '') or '')
            if shared_mapping.is_fixed_value(current_value) or current_value == source_column:
                continue
            updated[str(target_name)] = source_column
            applied += 1
        return updated, applied

    def _render_bling_import_guard_clean(*args: Any, **kwargs: Any) -> None:
        return None

    shared_mapping._ranked_source_options = _ranked_source_options_clean
    shared_mapping._auto_bind_exact_green_matches = _auto_bind_green_only
    shared_mapping._render_bling_import_guard = _render_bling_import_guard_clean
    shared_mapping._mapeiaai_critical_mapping_visual_patched = True
    _audit('critical_mapping_visual_patch_installed', details={'visual': 'compact', 'auto_bind_skips_critical': True})


__all__ = ['install']
