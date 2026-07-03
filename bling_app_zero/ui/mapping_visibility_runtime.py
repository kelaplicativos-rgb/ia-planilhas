from __future__ import annotations

from typing import Any

import pandas as pd

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.universal.internal_columns import is_generated_internal_column

RESPONSIBLE_FILE = 'bling_app_zero/ui/mapping_visibility_runtime.py'
PATCH_ATTR = '_mapeiaai_mapping_visibility_runtime_v2_gold_autonomy'


def _audit(event: str, **details: object) -> None:
    try:
        add_audit_event(event, area='MAPEAMENTO', status='OK', details={'responsible_file': RESPONSIBLE_FILE, **details})
    except Exception:
        pass


def _clean_df(df: pd.DataFrame | None) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    cols = [c for c in df.columns if not is_generated_internal_column(c)]
    return df.loc[:, cols].copy() if cols else pd.DataFrame(columns=[])


def _clean_columns(values: list[str]) -> list[str]:
    return [str(v) for v in list(values or []) if not is_generated_internal_column(v)]


def _install_gold_smart_rule_options() -> None:
    try:
        from bling_app_zero.ui.mapping_smart_rules_autonomy_runtime import install_mapping_smart_rules_autonomy_runtime
        install_mapping_smart_rules_autonomy_runtime()
    except Exception as exc:
        _audit('mapping_smart_rules_autonomy_install_warning', error=str(exc)[:220])


def install_mapping_visibility_runtime() -> bool:
    _install_gold_smart_rule_options()
    try:
        from bling_app_zero.ui import shared_mapping as sm
    except Exception as exc:
        _audit('mapping_visibility_import_failed', error=str(exc)[:220])
        return False

    if getattr(sm, PATCH_ATTR, False):
        _install_gold_smart_rule_options()
        return False

    original_render = sm.render_shared_contract_mapping
    original_ranked = getattr(sm, '_ranked_source_options', None)
    original_auto = getattr(sm, '_auto_bind_exact_green_matches', None)

    def render_without_internal_columns(
        source: pd.DataFrame,
        target: pd.DataFrame,
        *,
        signature: str,
        mapping_state_key: str,
        engine_state_key: str,
        key_prefix: str = 'mapeiaai_shared',
        ai_enabled: bool = True,
    ) -> dict[str, str]:
        _install_gold_smart_rule_options()
        clean_source = _clean_df(source)
        clean_target = _clean_df(target)
        try:
            current = dict(sm.st.session_state.get(mapping_state_key) or {})
            for key, value in list(current.items()):
                if is_generated_internal_column(key) or is_generated_internal_column(value):
                    current.pop(key, None)
            sm.st.session_state[mapping_state_key] = current
        except Exception:
            pass
        result = original_render(
            clean_source,
            clean_target,
            signature=signature,
            mapping_state_key=mapping_state_key,
            engine_state_key=engine_state_key,
            key_prefix=key_prefix,
            ai_enabled=ai_enabled,
        )
        return {str(k): str(v) for k, v in dict(result or {}).items() if not is_generated_internal_column(k) and not is_generated_internal_column(v)}

    if callable(original_ranked):
        def ranked_no_internal(target_name: str, current_value: str, source_columns: list[str], suggestions_index: dict[str, dict[str, Any]], source_profiles: dict[str, dict[str, float]] | None = None):
            options, labels = original_ranked(target_name, current_value, _clean_columns(source_columns), suggestions_index, source_profiles)
            options = [option for option in list(options or []) if not is_generated_internal_column(option)]
            labels = {option: label for option, label in dict(labels or {}).items() if not is_generated_internal_column(option)}
            return options, labels
        sm._ranked_source_options = ranked_no_internal

    if callable(original_auto):
        def auto_no_internal(current: dict[str, str], target_columns: list[str], source_columns: list[str]):
            return original_auto(current, _clean_columns(target_columns), _clean_columns(source_columns))
        sm._auto_bind_exact_green_matches = auto_no_internal

    sm.render_shared_contract_mapping = render_without_internal_columns
    setattr(sm, PATCH_ATTR, True)
    _audit('mapping_visibility_runtime_installed', hide_internal_columns=True, gold_smart_rule_options=True, user_can_override_smart_rules=True)
    return True


__all__ = ['install_mapping_visibility_runtime']
