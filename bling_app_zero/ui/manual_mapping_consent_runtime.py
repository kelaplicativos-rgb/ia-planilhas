from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/manual_mapping_consent_runtime.py'
PATCH_ATTR = '_mapeiaai_manual_mapping_consent_runtime_v1'
SESSION_INIT_KEY = 'mapeiaai_manual_mapping_consent_runtime_initialized_v1'


API_STATE_KEYS = (
    'home_bling_connected_same_flow_api_send',
    'bling_connected_api_flow_active',
    'direct_bling_api_contract_active',
    'flow_spine_api_batch_operation',
)


def _norm(value: object) -> str:
    text = str(value or '').strip().lower()
    for old, new in {'ã': 'a', 'á': 'a', 'à': 'a', 'â': 'a', 'é': 'e', 'ê': 'e', 'í': 'i', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ú': 'u', 'ç': 'c'}.items():
        text = text.replace(old, new)
    return ''.join(ch for ch in text if ch.isalnum() or ch == '_')


def _blank_mapping(target: Any) -> dict[str, str]:
    return {str(column): '' for column in getattr(target, 'columns', [])}


def _api_flow_active() -> bool:
    try:
        import streamlit as st
        if any(bool(st.session_state.get(key)) for key in API_STATE_KEYS):
            return True
        if str(st.session_state.get('flow_spine_final_destination') or '').strip().lower() == 'api_bling':
            return True
        finish_mode = str(st.session_state.get('bling_finish_mode') or '').strip().lower()
        if finish_mode in {'api_direct', 'api', 'bling_api'}:
            return True
        try:
            from bling_app_zero.ui.flow_context import CONTEXT_BLING_API, entry_context
            if entry_context() == CONTEXT_BLING_API:
                return True
        except Exception:
            pass
    except Exception:
        return False
    return False


def _manual_spreadsheet_mapping_active(operation: object = '') -> bool:
    op = _norm(operation)
    if 'api' in op or 'direct' in op:
        return False
    return not _api_flow_active()


def manual_mapping_should_start_blank(operation: object = '') -> bool:
    """Regra pública: planilha anexada em modo manual começa sempre sem automapeamento."""
    return _manual_spreadsheet_mapping_active(operation)


def _clear_auto_green_default_once() -> None:
    try:
        import streamlit as st
    except Exception:
        return
    if st.session_state.get(SESSION_INIT_KEY):
        return
    st.session_state[SESSION_INIT_KEY] = True
    changed = 0
    for key in list(st.session_state.keys()):
        text = str(key)
        if '_auto_green_' not in text:
            continue
        if text.endswith('_applied'):
            st.session_state.pop(key, None)
        else:
            st.session_state[key] = False
        changed += 1
    if changed:
        add_audit_event(
            'manual_mapping_auto_green_defaults_cleared',
            area='MAPEAMENTO',
            status='OK',
            details={'changed_keys': int(changed), 'reason': 'Nenhum automapeamento sem consentimento do usuario.', 'responsible_file': RESPONSIBLE_FILE},
        )


def _patch_preventive_bootstrap() -> None:
    try:
        from bling_app_zero.ui import preventive_bootstrap
    except Exception:
        return
    if getattr(preventive_bootstrap, '_mapeiaai_manual_mapping_auto_green_default_disabled', False):
        return

    def _disabled_auto_green_default() -> None:
        _clear_auto_green_default_once()
        add_audit_event(
            'mapping_auto_green_default_blocked_by_manual_consent_policy',
            area='MAPEAMENTO',
            status='OK',
            details={'manual_mapping_requires_user_consent': True, 'responsible_file': RESPONSIBLE_FILE},
        )

    preventive_bootstrap._install_auto_green_mapping_default = _disabled_auto_green_default
    preventive_bootstrap._mapeiaai_manual_mapping_auto_green_default_disabled = True


def _patch_shared_mapping() -> None:
    try:
        from bling_app_zero.ui import shared_mapping
    except Exception:
        return
    if getattr(shared_mapping, PATCH_ATTR, False):
        return

    original_suggest = getattr(shared_mapping, '_mapeiaai_original_suggest_shared_mapping_with_metadata', None) or shared_mapping._suggest_shared_mapping_with_metadata
    setattr(shared_mapping, '_mapeiaai_original_suggest_shared_mapping_with_metadata', original_suggest)

    def suggest_metadata_without_auto_apply(source: pd.DataFrame, target: pd.DataFrame, *, operation: str = 'universal'):
        mapping, engine, metadata = original_suggest(source, target, operation=operation)
        if manual_mapping_should_start_blank(operation):
            return _blank_mapping(target), 'manual_sugestoes_sem_autoaplicar', metadata
        return mapping, engine, metadata

    shared_mapping._suggest_shared_mapping_with_metadata = suggest_metadata_without_auto_apply
    shared_mapping._mapeiaai_manual_mapping_consent_runtime_v1 = True
    add_audit_event(
        'shared_mapping_manual_consent_runtime_installed',
        area='MAPEAMENTO',
        status='OK',
        details={'initial_mapping': 'blank', 'suggestions': 'visible_only_not_applied', 'responsible_file': RESPONSIBLE_FILE},
    )


def _patch_mapping_auto_suggestions() -> None:
    try:
        from bling_app_zero.ui import mapping_auto_suggestions
    except Exception:
        return
    if getattr(mapping_auto_suggestions, PATCH_ATTR, False):
        return

    original_super = getattr(mapping_auto_suggestions, '_mapeiaai_original_build_super_mapping', None) or mapping_auto_suggestions.build_super_mapping
    original_stock = getattr(mapping_auto_suggestions, '_mapeiaai_original_build_stock_auto_mapping', None) or mapping_auto_suggestions.build_stock_auto_mapping
    setattr(mapping_auto_suggestions, '_mapeiaai_original_build_super_mapping', original_super)
    setattr(mapping_auto_suggestions, '_mapeiaai_original_build_stock_auto_mapping', original_stock)

    def build_super_mapping_blank_until_user_choice(df_source: pd.DataFrame, model: pd.DataFrame, source_columns: list[str]) -> dict[str, str]:
        if manual_mapping_should_start_blank('universal'):
            return _blank_mapping(model)
        return original_super(df_source, model, source_columns)

    def build_stock_auto_mapping_blank_until_user_choice(df_source: pd.DataFrame, model: pd.DataFrame) -> dict[str, str]:
        if manual_mapping_should_start_blank('estoque'):
            return _blank_mapping(model)
        return original_stock(df_source, model)

    mapping_auto_suggestions.build_super_mapping = build_super_mapping_blank_until_user_choice
    mapping_auto_suggestions.build_stock_auto_mapping = build_stock_auto_mapping_blank_until_user_choice
    mapping_auto_suggestions._mapeiaai_manual_mapping_consent_runtime_v1 = True


def _patch_cadastro_tools() -> None:
    try:
        from bling_app_zero.flows import cadastro_tools
    except Exception:
        return
    if getattr(cadastro_tools, PATCH_ATTR, False):
        return

    original_super = getattr(cadastro_tools, '_mapeiaai_original_super_auto_map_columns', None) or cadastro_tools.super_auto_map_columns
    original_force_price = getattr(cadastro_tools, '_mapeiaai_original_force_price_suggestion', None) or cadastro_tools.force_price_suggestion
    setattr(cadastro_tools, '_mapeiaai_original_super_auto_map_columns', original_super)
    setattr(cadastro_tools, '_mapeiaai_original_force_price_suggestion', original_force_price)

    def super_auto_map_columns_blank_until_user_choice(df_source: pd.DataFrame, model: pd.DataFrame) -> dict[str, str]:
        if manual_mapping_should_start_blank('cadastro'):
            return _blank_mapping(model)
        return original_super(df_source, model)

    def force_price_suggestion_only_when_not_manual(target: str, source_columns: list[str], suggested: str) -> str:
        if manual_mapping_should_start_blank('cadastro'):
            return suggested
        return original_force_price(target, source_columns, suggested)

    cadastro_tools.super_auto_map_columns = super_auto_map_columns_blank_until_user_choice
    cadastro_tools.force_price_suggestion = force_price_suggestion_only_when_not_manual
    cadastro_tools._mapeiaai_manual_mapping_consent_runtime_v1 = True


def _patch_spreadsheet_mapping_center() -> None:
    try:
        from bling_app_zero.core import spreadsheet_mapping_center as center
    except Exception:
        return
    if getattr(center, PATCH_ATTR, False):
        return

    original_build_full = getattr(center, '_mapeiaai_original_build_full_mapping_result', None) or center.build_full_mapping_result
    original_auto_map = getattr(center, '_mapeiaai_original_auto_map_columns', None) or center.auto_map_columns
    setattr(center, '_mapeiaai_original_build_full_mapping_result', original_build_full)
    setattr(center, '_mapeiaai_original_auto_map_columns', original_auto_map)

    def build_full_mapping_result_blank_until_user_choice(df_source: pd.DataFrame, df_model: pd.DataFrame, *, operation: str = 'universal', signature: str = '', engine: str = 'local'):
        if manual_mapping_should_start_blank(operation):
            mapping = _blank_mapping(df_model)
            request = center.build_request_from_frames(df_source, df_model, operation=operation, signature=signature)
            return center.build_mapping_state(
                request,
                mapping,
                source=df_source,
                engine='manual_sem_automapeamento',
                message='Mapeamento manual iniciado vazio: escolha cada campo antes de gerar a saída.',
            )
        return original_build_full(df_source, df_model, operation=operation, signature=signature, engine=engine)

    def auto_map_columns_blank_until_user_choice(df_source: pd.DataFrame, df_model: pd.DataFrame) -> dict[str, str]:
        if manual_mapping_should_start_blank('universal'):
            return _blank_mapping(df_model)
        return original_auto_map(df_source, df_model)

    center.build_full_mapping_result = build_full_mapping_result_blank_until_user_choice
    center.auto_map_columns = auto_map_columns_blank_until_user_choice
    center._mapeiaai_manual_mapping_consent_runtime_v1 = True

    try:
        from bling_app_zero.core import mapping as mapping_bridge
        mapping_bridge.auto_map_columns = auto_map_columns_blank_until_user_choice
    except Exception:
        pass


def install_manual_mapping_consent_runtime() -> bool:
    _clear_auto_green_default_once()
    _patch_preventive_bootstrap()
    _patch_shared_mapping()
    _patch_mapping_auto_suggestions()
    _patch_cadastro_tools()
    _patch_spreadsheet_mapping_center()
    add_audit_event(
        'manual_mapping_consent_runtime_installed',
        area='MAPEAMENTO',
        status='OK',
        details={
            'manual_spreadsheet_mapping_initial_state': 'blank',
            'auto_green_default': 'disabled',
            'api_flow_preserved': True,
            'no_overwrite_without_user_choice': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return True


__all__ = ['install_manual_mapping_consent_runtime', 'manual_mapping_should_start_blank']
