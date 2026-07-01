from __future__ import annotations

from typing import Any

RESPONSIBLE_FILE = 'bling_app_zero/ui/shared_mapping_contract_runtime.py'
_INSTALLED = False
_ORIGINALS: dict[str, Any] = {}
_WIDGET_VERSION_KEY = 'shared_mapping_contract_widget_version_v1'


def _next_widget_version(st_module: Any) -> None:
    try:
        current = int(st_module.session_state.get(_WIDGET_VERSION_KEY) or 0)
    except Exception:
        current = 0
    try:
        st_module.session_state[_WIDGET_VERSION_KEY] = current + 1
    except Exception:
        pass


def _origin_reference_fixed_value(shared_mapping: Any, value: object) -> bool:
    if not shared_mapping.is_fixed_value(value):
        return False
    fixed = shared_mapping.decode_fixed_value(value).strip().casefold()
    return bool(fixed.startswith('origem::') or fixed.startswith('origem:'))


def install_shared_mapping_contract_runtime() -> bool:
    """Corrige o mapeamento universal sem alterar o contrato final do modelo.

    O patch mantém as opções manuais no topo, vincula cabeçalhos verdes idênticos
    quando o toggle é ligado e substitui placeholders antigos do tipo
    ``origem::Campo`` por vínculo real da coluna de origem.
    """
    global _INSTALLED
    if _INSTALLED:
        return False

    try:
        from bling_app_zero.ui import shared_mapping as sm
    except Exception:
        return False

    _ORIGINALS.setdefault('mapping_widget_key', sm.mapping_widget_key)
    _ORIGINALS.setdefault('_ranked_source_options', sm._ranked_source_options)
    _ORIGINALS.setdefault('_auto_bind_exact_green_matches', sm._auto_bind_exact_green_matches)

    original_mapping_widget_key = _ORIGINALS['mapping_widget_key']
    original_ranked_source_options = _ORIGINALS['_ranked_source_options']

    def mapping_widget_key_with_contract_version(key_prefix: str, signature: str, index: int, target_name: str) -> str:
        base = original_mapping_widget_key(key_prefix, signature, index, target_name)
        try:
            version = int(sm.st.session_state.get(_WIDGET_VERSION_KEY) or 0)
        except Exception:
            version = 0
        return f'{base}_cv{version}'

    def ranked_source_options_manual_first(
        target_name: str,
        current_value: str,
        source_columns: list[str],
        suggestions_index: dict[str, dict[str, Any]],
        source_profiles: dict[str, dict[str, float]] | None = None,
    ) -> tuple[list[str], dict[str, str]]:
        options, labels = original_ranked_source_options(target_name, current_value, source_columns, suggestions_index, source_profiles)
        ordered: list[str] = [sm.EMPTY_OPTION, sm.WRITE_OPTION]
        ordered.extend(option for option in options if option not in {sm.EMPTY_OPTION, sm.WRITE_OPTION})
        return ordered, labels

    def auto_bind_exact_green_matches(current: dict[str, str], target_columns: list[str], source_columns: list[str]) -> tuple[dict[str, str], int]:
        lookup: dict[tuple[str, ...], str] = {}
        for source_column in source_columns:
            key = sm._word_tuple(source_column)
            if key and key not in lookup:
                lookup[key] = source_column

        updated = dict(current or {})
        applied = 0
        for target_name in target_columns:
            key = sm._word_tuple(target_name)
            source_column = lookup.get(key)
            if not source_column:
                continue

            current_value = str(updated.get(target_name, '') or '')
            if current_value == source_column:
                continue
            if sm.is_fixed_value(current_value) and not _origin_reference_fixed_value(sm, current_value):
                continue

            updated[target_name] = source_column
            applied += 1

        if applied:
            _next_widget_version(sm.st)
        return updated, applied

    sm.mapping_widget_key = mapping_widget_key_with_contract_version
    sm._ranked_source_options = ranked_source_options_manual_first
    sm._auto_bind_exact_green_matches = auto_bind_exact_green_matches
    _INSTALLED = True
    return True


__all__ = ['install_shared_mapping_contract_runtime']
