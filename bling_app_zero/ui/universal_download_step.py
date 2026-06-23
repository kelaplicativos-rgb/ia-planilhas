from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.bling_api_flow_nuclei import validate_api_dataframe
from bling_app_zero.ui.cadastro_download_step_v2 import render_cadastro_download_step


def _api_flow_active() -> bool:
    return bool(
        st.session_state.get('home_bling_connected_same_flow_api_send')
        or st.session_state.get('bling_connected_api_flow_active')
        or st.session_state.get('direct_bling_api_contract_active')
        or str(st.session_state.get('bling_finish_mode') or '').strip() == 'api_direct'
    )


def _api_operation() -> str:
    for key in ('source_first_selected_operation', 'direct_bling_operation_applied', 'api_operation', 'bling_api_operation', 'operacao_final', 'tipo_operacao_final'):
        value = str(st.session_state.get(key) or '').strip()
        if value in {'cadastro', 'estoque', 'atualizacao_preco'}:
            return value
    return 'cadastro'


def _first_api_dataframe() -> pd.DataFrame:
    for key in ('df_final_bling_api', 'df_final_universal', 'df_final_cadastro', 'final_download_df_snapshot', 'cadastro_wizard_df_origem', 'df_origem', 'df_origem_planilha', 'df_produtos_origem', 'df_origem_site_como_planilha', 'df_site_bruto'):
        value = st.session_state.get(key)
        if isinstance(value, pd.DataFrame) and not value.empty:
            return value.copy().fillna('')
    return pd.DataFrame()


def _deposit_selected() -> bool:
    return bool(str(st.session_state.get('bling_api_stock_deposit_id') or st.session_state.get('bling_api_stock_deposit_name') or '').strip())


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
    if op == 'estoque' and not _deposit_selected():
        st.error('Envio ao Bling bloqueado: selecione o depósito antes de atualizar estoque pela API.')
        return False
    return True


def render_universal_download_step() -> None:
    if _api_flow_active() and not _api_nuclei_ready():
        st.info('Corrija os pontos acima e volte para esta etapa para liberar o painel de envio ao Bling.')
        return
    render_cadastro_download_step()


__all__ = ['render_universal_download_step']
