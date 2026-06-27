from __future__ import annotations

import pandas as pd

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/download_estoque_runtime_fix.py'
_PATCH_ATTR = '_download_universal_runtime_fix_v9_no_template_runtime'
_ORIGINAL_ATTR = '_download_universal_original_mismatch_error'
_DOWNLOAD_SPLIT_FIRST_ATTR = '_mapeiaai_download_split_first_v1'
DOWNLOAD_LABEL_TEXT = '⬇️ Download Modelo Mapeado'
UNIVERSAL_OPERATION = 'universal'
UNIVERSAL_STATE_KEYS = (
    'destination_model_contract_type',
    'model_contract_type',
    'home_slim_flow_operation',
    'home_detected_operation',
    'operacao_final',
    'tipo_operacao_final',
    'flow_spine_operation',
    'active_feature_operation',
    'tipo_operacao_site',
    'operation_site',
    'site_capture_operation',
    'final_download_operation',
    'df_final_download_operation',
    'df_final_preview_operation',
)


def _safe_state_set(st, key: str, value) -> None:
    try:
        st.session_state[key] = value
    except Exception:
        try:
            st.session_state.setdefault('universal_state_write_warnings', {})[key] = str(value)
        except Exception:
            pass


def _api_flow_active(st) -> bool:
    try:
        from bling_app_zero.ui.flow_context import CONTEXT_BLING_API, entry_context
        if entry_context() == CONTEXT_BLING_API:
            return True
    except Exception:
        pass
    try:
        return bool(
            st.session_state.get('home_bling_connected_same_flow_api_send')
            or st.session_state.get('bling_connected_api_flow_active')
            or st.session_state.get('direct_bling_api_contract_active')
            or str(st.session_state.get('flow_spine_final_destination') or '').strip().lower() == 'api_bling'
        )
    except Exception:
        return False


def _force_universal_state() -> None:
    try:
        import streamlit as st
    except Exception:
        return
    if _api_flow_active(st):
        add_audit_event('download_universal_force_skipped_for_api', area='DOWNLOAD', status='OK', details={'reason': 'api_flow_active', 'responsible_file': RESPONSIBLE_FILE})
        return
    for key in UNIVERSAL_STATE_KEYS:
        _safe_state_set(st, key, UNIVERSAL_OPERATION)
    _safe_state_set(st, 'destination_model_contract_label', 'Modelo para mapear')
    _safe_state_set(st, 'model_contract_label', 'Modelo para mapear')
    _safe_state_set(st, 'destination_model_contract_confidence', 1.0)
    _safe_state_set(st, 'destination_model_contract_reason', 'Modelo universal para mapear. Sem reconhecimento por tipo.')
    _safe_state_set(st, 'flow_spine_final_title', 'Download')
    _safe_state_set(st, 'flow_spine_primary_action_label', DOWNLOAD_LABEL_TEXT.replace('⬇️ ', ''))


def _install_retry_result_visual_fix() -> None:
    try:
        from bling_app_zero.ui.bling_retry_result_runtime_fix import install_bling_retry_result_runtime_fix
        install_bling_retry_result_runtime_fix()
    except Exception as exc:
        add_audit_event('retry_result_visual_fix_install_failed', area='BLING_ENVIO', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})


def _install_manual_mapping_consent_runtime() -> None:
    try:
        from bling_app_zero.ui.manual_mapping_consent_runtime import install_manual_mapping_consent_runtime
        install_manual_mapping_consent_runtime()
    except Exception as exc:
        add_audit_event('manual_mapping_consent_runtime_install_failed', area='MAPEAMENTO', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})


def _install_split_first_download_fix() -> None:
    try:
        import bling_app_zero.ui as ui_root
        from bling_app_zero.core.final_output_engine import build_final_output
        from bling_app_zero.ui import shared_final_csv
    except Exception:
        return
    if getattr(shared_final_csv, _DOWNLOAD_SPLIT_FIRST_ATTR, False):
        return
    render_split = getattr(ui_root, '_render_split_downloads', None)
    if not callable(render_split):
        return

    original_shared = getattr(shared_final_csv, '_mapeiaai_original_render_shared_final_csv', None) or shared_final_csv.render_shared_final_csv
    original_preview = getattr(shared_final_csv, '_mapeiaai_original_render_final_csv_preview', None) or shared_final_csv.render_final_csv_preview

    def shared_split_first(source, contract, mapping, *args, **kwargs):
        key_prefix = str(kwargs.get('key_prefix') or 'mapeiaai_shared_final')
        file_name = str(kwargs.get('file_name') or 'mapeiaai_planilha_final_mapeada.csv')
        try:
            result = build_final_output(source, contract, mapping, operation='universal', file_name=file_name, run_smart_features=bool(kwargs.get('run_smart_features', True)), smart_rules_config=kwargs.get('smart_rules_config'))
            render_split(result.output, key_prefix, file_name)
        except Exception:
            pass
        return original_shared(source, contract, mapping, *args, **kwargs)

    def preview_split_first(df_final, *args, **kwargs):
        key_prefix = str(kwargs.get('key_prefix') or 'mapeiaai_final_csv')
        render_split(df_final, key_prefix, 'mapeiaai_planilha_final_mapeada.csv')
        return original_preview(df_final, *args, **kwargs)

    shared_final_csv.render_shared_final_csv = shared_split_first
    shared_final_csv.render_final_csv_preview = preview_split_first
    try:
        from bling_app_zero.ui import universal_flow
        universal_flow.render_shared_final_csv = shared_split_first
    except Exception:
        pass
    setattr(shared_final_csv, _DOWNLOAD_SPLIT_FIRST_ATTR, True)
    add_audit_event('split_first_download_fix_installed', area='DOWNLOAD', status='OK', details={'responsible_file': RESPONSIBLE_FILE})


def install_download_estoque_runtime_fix() -> bool:
    try:
        import streamlit as st
        if _api_flow_active(st):
            add_audit_event('download_universal_runtime_fix_not_installed_for_api', area='DOWNLOAD', status='OK', details={'reason': 'api_flow_active', 'responsible_file': RESPONSIBLE_FILE})
            return False
    except Exception:
        pass

    _install_manual_mapping_consent_runtime()
    _force_universal_state()
    _install_retry_result_visual_fix()
    _install_split_first_download_fix()

    try:
        from bling_app_zero.ui.exact_model_download_runtime import install_exact_model_download_runtime
        install_exact_model_download_runtime()
    except Exception as exc:
        add_audit_event('download_exact_model_runtime_install_failed', area='DOWNLOAD', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})

    try:
        from bling_app_zero.ui import home_download
    except Exception as exc:
        add_audit_event('download_universal_runtime_import_failed', area='DOWNLOAD', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
        return False

    home_download.download_label = lambda: DOWNLOAD_LABEL_TEXT

    if getattr(home_download, _PATCH_ATTR, False):
        return False

    original = getattr(home_download, _ORIGINAL_ATTR, None)
    if original is None:
        original = home_download._operation_contract_mismatch_error
        setattr(home_download, _ORIGINAL_ATTR, original)

    def guarded_contract_mismatch(raw_df: pd.DataFrame, download_df: pd.DataFrame, operation: str) -> str:
        _force_universal_state()
        return ''

    home_download._operation_contract_mismatch_error = guarded_contract_mismatch
    setattr(home_download, _PATCH_ATTR, True)
    add_audit_event('download_universal_runtime_fix_installed', area='DOWNLOAD', status='OK', details={'exact_model_runtime': True, 'exact_template_file_runtime': False, 'template_runtime_removed': True, 'download_label': DOWNLOAD_LABEL_TEXT, 'safe_state_write': True, 'retry_result_visual_fix': True, 'split_first_download': True, 'manual_mapping_consent_runtime': True, 'responsible_file': RESPONSIBLE_FILE})
    return True


__all__ = ['install_download_estoque_runtime_fix']
