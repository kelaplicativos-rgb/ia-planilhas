from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_api_flow_nuclei import validate_api_dataframe
from bling_app_zero.ui.cadastro_download_step_v2 import render_cadastro_download_step

RESPONSIBLE_FILE = 'bling_app_zero/ui/universal_download_step.py'
STOCK_DEPOSIT_ID_COLUMN = 'Bling depósito id'


def _api_flow_active() -> bool:
    return bool(
        st.session_state.get('home_bling_connected_same_flow_api_send')
        or st.session_state.get('bling_connected_api_flow_active')
        or st.session_state.get('direct_bling_api_contract_active')
        or str(st.session_state.get('bling_finish_mode') or '').strip() == 'api_direct'
    )


def _api_operation() -> str:
    for key in (
        'source_first_selected_operation', 'direct_bling_operation_applied', 'api_operation', 'bling_api_operation',
        'flow_spine_sender_operation', 'flow_spine_operation_resolved_for_api', 'flow_spine_api_batch_operation',
        'final_download_operation', 'df_final_download_operation', 'operacao_final', 'tipo_operacao_final',
    ):
        value = str(st.session_state.get(key) or '').strip()
        if value in {'cadastro', 'estoque', 'atualizacao_preco'}:
            return value
    return 'cadastro'


def _first_api_dataframe() -> pd.DataFrame:
    for key in (
        'df_final_bling_api', 'df_final_universal', 'df_final_cadastro', 'final_download_df_snapshot',
        'df_final_download_snapshot', 'cadastro_wizard_df_origem', 'df_origem', 'df_origem_planilha',
        'df_produtos_origem', 'df_origem_site_como_planilha', 'df_site_bruto', 'mapeiaai_universal_source_df',
    ):
        value = st.session_state.get(key)
        if isinstance(value, pd.DataFrame) and not value.empty:
            return value.copy().fillna('')
    return pd.DataFrame()


def _deposit_selected() -> bool:
    return bool(str(st.session_state.get('bling_api_stock_deposit_id') or st.session_state.get('bling_api_stock_deposit_name') or '').strip())


def _has_stock_deposit_id(df: pd.DataFrame) -> bool:
    if not isinstance(df, pd.DataFrame) or df.empty or STOCK_DEPOSIT_ID_COLUMN not in df.columns:
        return False
    return bool(df[STOCK_DEPOSIT_ID_COLUMN].fillna('').astype(str).str.strip().ne('').any())


def _clear_stale_stock_send_state() -> int:
    removed = 0
    fixed_keys = (
        'bling_api_batch_send_state_v2',
        'neutral_bling_send_state_v1',
        'neutral_bling_send_report_v1',
        'bling_api_preflight_cache_v1',
        'bling_api_payload_preview_cache_v2',
        'bling_background_job_created_v1',
        'bling_api_failed_retry_rows_v1',
        'bling_api_failed_retry_result_v1',
        'bling_api_live_progress_v2',
        'bling_api_intelligent_batch_plan_v1',
        'bling_api_last_batch_seconds_v1',
    )
    for key in fixed_keys:
        if key in st.session_state:
            st.session_state.pop(key, None)
            removed += 1
    for key in list(st.session_state.keys()):
        text_key = str(key)
        if text_key.startswith('background_job_create_estoque::'):
            st.session_state.pop(key, None)
            removed += 1
    return removed


def _store_targeted_stock_dataframe(df: pd.DataFrame) -> None:
    targeted = df.copy().fillna('')
    st.session_state['df_final_bling_api'] = targeted.copy()
    st.session_state['df_final_universal'] = targeted.copy()
    st.session_state['final_download_df_snapshot'] = targeted.copy()
    st.session_state['df_final_download_snapshot'] = targeted.copy()
    st.session_state['mapeiaai_universal_output_df'] = targeted.copy()
    removed_cache_keys = _clear_stale_stock_send_state()
    try:
        from bling_app_zero.ui.cadastro_wizard_state import set_context_final_df
        set_context_final_df(targeted.copy())
    except Exception as exc:
        st.caption(f'Depósito selecionado, mas o contexto final não foi sincronizado agora: {exc}')
    add_audit_event(
        'universal_download_stock_deposit_target_synced',
        area='BLING_API',
        status='OK',
        details={
            'rows': int(len(targeted)),
            'columns': int(len(targeted.columns)),
            'has_deposit_id_column': _has_stock_deposit_id(targeted),
            'deposit_id': str(st.session_state.get('bling_api_stock_deposit_id') or '').strip(),
            'cleared_stale_send_state_keys': int(removed_cache_keys),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _stock_target_ready(df: pd.DataFrame) -> bool:
    from bling_app_zero.ui.bling_stock_target_panel import render_stock_target_panel

    st.warning('Depósito obrigatório: selecione o depósito real do Bling antes de atualizar estoque pela API.')
    targeted_df = render_stock_target_panel(df)
    if not isinstance(targeted_df, pd.DataFrame) or targeted_df.empty:
        st.info('O envio de estoque fica bloqueado até o depósito ser selecionado ou informado com ID.')
        return False
    if not _deposit_selected() or not _has_stock_deposit_id(targeted_df):
        st.error('Depósito ainda não confirmado com ID técnico do Bling. Selecione ou informe o ID antes de continuar.')
        return False
    _store_targeted_stock_dataframe(targeted_df)
    return True


def _api_nuclei_ready() -> bool:
    op = _api_operation()
    df = _first_api_dataframe()
    try:
        from bling_app_zero.ui.bling_api_nuclei_panel import render_api_nuclei_panel
        render_api_nuclei_panel(op, df if not df.empty else None, compact=True)
    except Exception as exc:
        st.caption(f'Núcleos API ativos; painel indisponível agora: {exc}')
    result = validate_api_dataframe(df, op)
    st.session_state['bling_api_nuclei_download_blocking_validation'] = result.to_dict()
    if not result.ok:
        st.error('Envio ao Bling bloqueado pelos núcleos obrigatórios da API.')
        for message in result.messages:
            st.warning(message)
        return False
    if op == 'estoque':
        return _stock_target_ready(df)
    return True


def render_universal_download_step() -> None:
    if _api_flow_active() and not _api_nuclei_ready():
        st.info('Corrija os pontos acima e volte para esta etapa para liberar o painel de envio ao Bling.')
        return
    render_cadastro_download_step()


__all__ = ['render_universal_download_step']
