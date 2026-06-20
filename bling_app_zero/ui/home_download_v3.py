from __future__ import annotations

import pandas as pd
import streamlit as st

import bling_app_zero.ui.home_download_v2 as _impl
from bling_app_zero.core.send_validation_v2 import validate_before_bling_send

_impl.validate_before_bling_send = validate_before_bling_send

from bling_app_zero.ui.home_download_v2 import *  # noqa: F401,F403,E402


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
    is_api = bool(
        _impl._is_api_context()
        or st.session_state.get('home_bling_connected_same_flow_api_send')
        or st.session_state.get('bling_connected_api_flow_active')
        or st.session_state.get('direct_bling_api_contract_active')
        or str(st.session_state.get('flow_spine_final_destination') or '').strip().lower() == 'api_bling'
    )
    return bool(is_stock and is_api)


def _stock_operation(operation: object) -> str:
    try:
        resolved = _impl._spine_operation_or(str(operation or 'estoque'))
    except Exception:
        resolved = str(operation or 'estoque')
    return 'estoque' if 'estoque' in str(resolved or '').strip().lower() else 'estoque'


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


def download_final(df_final: pd.DataFrame, operation: str, key: str = 'final') -> None:
    render_download(df_final, operation, key)
