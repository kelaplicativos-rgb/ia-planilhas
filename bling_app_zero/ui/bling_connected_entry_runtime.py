from __future__ import annotations

from typing import Any, Callable

import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/bling_connected_entry_runtime.py'
_PATCH_KEY = 'bling_connected_entry_runtime_installed_v1'

STALE_EXACT_KEYS = (
    'frontpage_origin_radio_universal', 'origem_final', 'origem_dados', 'origem_tipo',
    'source_first_selected_operation', 'source_first_operation_user_confirmed', 'source_first_operation_pending_choice',
    'direct_bling_operation_choice', 'direct_bling_operation_applied', 'direct_bling_api_contract_df', 'direct_bling_api_contract_active',
    'bling_api_locked_contract_signature', 'bling_api_locked_contract_engine', 'bling_api_locked_contract_ready',
    'mapping_bling_api', 'mapping_confidence_bling_api', 'mapping_cadastro', 'mapping_confidence_cadastro',
    'cadastro_mapping_confirmed', 'cadastro_mapping_confirmed_signature',
    'df_final_bling_api', 'df_final_universal', 'df_final_cadastro', 'df_final_download_operation', 'df_final_preview_operation',
    'final_download_df_snapshot', 'final_download_operation', 'final_download_signature', 'final_download_rules_signature',
    'bling_api_nuclei_download_blocking_validation', 'bling_api_nuclei_validation', 'bling_api_nuclei_overview',
    'category_conference_confirmed_v1', 'category_conference_skipped_v1', 'category_conference_values_signature_v1',
    'cadastro_wizard_df_origem', 'df_origem', 'df_origem_planilha', 'df_produtos_origem', 'df_origem_site_como_planilha', 'df_site_bruto',
)

STALE_PREFIXES = (
    'df_final_', 'df_site_bruto_', 'df_origem_site_como_planilha_', 'site_source_urls_',
    'site_requested_columns_', 'blingsmartscan_', 'final_download_', 'mapping_',
)


def _clear_api_entry_stale_state() -> list[str]:
    removed: list[str] = []
    for key in STALE_EXACT_KEYS:
        if key in st.session_state:
            st.session_state.pop(key, None)
            removed.append(key)
    for key in list(st.session_state.keys()):
        text = str(key)
        if text in removed:
            continue
        if any(text.startswith(prefix) for prefix in STALE_PREFIXES):
            st.session_state.pop(key, None)
            removed.append(text)
    return removed


def _patch_connected_entry_cleanup() -> None:
    import bling_app_zero.ui.home_official as official

    if getattr(official, '_bling_connected_entry_cleanup_patch_installed', False):
        return
    original: Callable[..., Any] = official._prime_bling_api_runtime

    def wrapped_prime_bling_api_runtime(*, force_origin: bool) -> None:
        removed = _clear_api_entry_stale_state() if force_origin else []
        original(force_origin=force_origin)
        st.session_state['bling_api_entry_started_clean'] = True
        st.session_state['bling_api_manual_mapping_required'] = False
        st.session_state['bling_api_mapping_locked_by_api'] = True
        add_audit_event(
            'bling_connected_entry_clean_state_applied',
            area='HOME',
            status='OK',
            details={
                'force_origin': force_origin,
                'removed_count': len(removed),
                'removed_keys': removed[:80],
                'next_step': st.session_state.get('bling_wizard_step'),
                'responsible_file': RESPONSIBLE_FILE,
            },
        )

    official._bling_connected_entry_original_prime_bling_api_runtime = original
    official._prime_bling_api_runtime = wrapped_prime_bling_api_runtime
    official._bling_connected_entry_cleanup_patch_installed = True


def _patch_compact_connected_banner() -> None:
    import bling_app_zero.ui.home_bling_api_flow as api_flow

    if getattr(api_flow, '_bling_connected_compact_banner_patch_installed', False):
        return
    original: Callable[..., Any] = api_flow.render_bling_connection_step

    def wrapped_render_bling_connection_step(section_title) -> None:
        try:
            connected = bool(api_flow.connection_status().get('connected')) or api_flow._connected_via_backend()
        except Exception:
            connected = False
        if not connected:
            return original(section_title)
        st.success('✅ Bling conectado · destino final: API Bling')
        st.caption('Próxima etapa: Origem dos dados. Escolha Arquivo ou Site para carregar os produtos.')
        with st.expander('Gerenciar conexão Bling', expanded=False):
            original(section_title)
        add_audit_event(
            'bling_connected_compact_banner_rendered',
            area='BLING_API',
            status='OK',
            details={'next_step': 'origem', 'responsible_file': RESPONSIBLE_FILE},
        )

    api_flow._bling_connected_compact_banner_original = original
    api_flow.render_bling_connection_step = wrapped_render_bling_connection_step
    api_flow._bling_connected_compact_banner_patch_installed = True


def install_bling_connected_entry_runtime() -> bool:
    if st.session_state.get(_PATCH_KEY):
        return False
    _patch_connected_entry_cleanup()
    _patch_compact_connected_banner()
    st.session_state[_PATCH_KEY] = True
    add_audit_event(
        'bling_connected_entry_runtime_installed',
        area='APP',
        status='OK',
        details={
            'clean_stale_state_on_use_connected': True,
            'compact_connected_banner': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return True


__all__ = ['install_bling_connected_entry_runtime']
