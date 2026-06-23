from __future__ import annotations

import pandas as pd
import streamlit as st

import bling_app_zero.ui.home_download_v2 as _impl
from bling_app_zero.core.bling_oauth import build_authorization_url, connection_status
from bling_app_zero.core.oauth_return_snapshot import prepare_download_oauth_return
from bling_app_zero.core.operation_contract import OP_UNIVERSAL, normalize_operation
from bling_app_zero.core.send_validation_v2 import validate_before_bling_send
from bling_app_zero.ui.home_bling_api_flow import render_new_tab_connect_button

_impl.validate_before_bling_send = validate_before_bling_send

from bling_app_zero.ui.home_download_v2 import *  # noqa: F401,F403,E402


def _is_api_like_final() -> bool:
    return bool(
        _impl._is_api_context()
        or st.session_state.get('home_bling_connected_same_flow_api_send')
        or st.session_state.get('bling_connected_api_flow_active')
        or st.session_state.get('direct_bling_api_contract_active')
        or str(st.session_state.get('flow_spine_final_destination') or '').strip().lower() == 'api_bling'
    )


def _is_api_stock_final(operation: object) -> bool:
    values = [
        operation,
        st.session_state.get('flow_spine_operation'),
        st.session_state.get('flow_spine_sender_operation'),
        st.session_state.get('flow_spine_api_batch_operation'),
        st.session_state.get('operacao_final'),
        st.session_state.get('tipo_operacao_final'),
        st.session_state.get('active_feature_operation'),
    ]
    is_stock = any('estoque' in str(value or '').strip().lower() for value in values)
    return bool(is_stock and _is_api_like_final())


def _stock_operation(operation: object) -> str:
    try:
        resolved = _impl._spine_operation_or(str(operation or 'estoque'))
    except Exception:
        resolved = str(operation or 'estoque')
    return 'estoque' if 'estoque' in str(resolved or '').strip().lower() else 'estoque'


def _resolved_operation(operation: object) -> str:
    for value in (
        st.session_state.get('final_download_operation'),
        st.session_state.get('df_final_download_operation'),
        st.session_state.get('flow_spine_sender_operation'),
        st.session_state.get('operacao_final'),
        st.session_state.get('tipo_operacao_final'),
        st.session_state.get('home_slim_flow_operation'),
        operation,
    ):
        op = normalize_operation(value)
        if op != OP_UNIVERSAL:
            return op
    return normalize_operation(operation)


def _render_final_bling_bridge(operation: str, key: str) -> None:
    df_snapshot = st.session_state.get('final_download_df_snapshot')
    if not isinstance(df_snapshot, pd.DataFrame) or df_snapshot.empty:
        return
    op = _resolved_operation(operation)
    if op == OP_UNIVERSAL:
        return
    signature = _impl.df_signature(df_snapshot)
    status = connection_status()
    with st.container(border=True):
        st.markdown('### Bling no final da operação')
        st.caption('O download continua disponível. Esta opção usa a mesma planilha final validada para envio direto.')
        if status.get('connected'):
            st.success('Bling conectado. O envio direto foi liberado para esta planilha final.')
            st.session_state['flow_spine_sender_operation'] = op
            st.session_state['flow_spine_sender_destination'] = 'api_bling'
            st.session_state['home_bling_connected_same_flow_api_send'] = True
            _impl._render_direct_bling_send(df_snapshot.copy().fillna(''), op, f'final_bling_{key}', signature, _impl.rules_signature())
            return
        st.warning('Conecte o Bling para liberar o envio direto desta planilha final.')
        context = prepare_download_oauth_return(df_snapshot.copy().fillna(''), op, signature=signature)
        context.update({'return_to': 'download_panel', 'source_step': 'download_panel', 'operation': op, 'signature': signature})
        st.session_state['bling_oauth_return_context'] = dict(context)
        auth_url = build_authorization_url(context)
        render_new_tab_connect_button(auth_url)


def render_download(df_final: pd.DataFrame, operation: str, key: str = 'final') -> None:
    if _is_api_stock_final(operation) and isinstance(df_final, pd.DataFrame) and not df_final.empty:
        df_api = df_final.copy().fillna('')
        st.info('Envio final via API Bling: o sistema usará a base revisada do fluxo e atualizará o estoque no depósito selecionado.')
        _impl._render_direct_bling_send(
            df_api,
            _stock_operation(operation),
            key,
            _impl.df_signature(df_api),
            _impl.rules_signature(),
        )
        return
    _impl.render_download(df_final, operation, key)
    if not _is_api_like_final():
        _render_final_bling_bridge(operation, key)


def download_final(df_final: pd.DataFrame, operation: str, key: str = 'final') -> None:
    render_download(df_final, operation, key)
