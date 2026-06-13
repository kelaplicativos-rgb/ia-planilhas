from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_direct_sender_safe import (
    API_STOCK_DEPOSIT_ID_KEY,
    API_STOCK_DEPOSIT_KEY,
    _load_stock_deposits,
)
from bling_app_zero.core.bling_token_store import load_token

RESPONSIBLE_FILE = 'bling_app_zero/ui/bling_stock_target_panel.py'


def _option_label(item: dict[str, str]) -> str:
    name = str(item.get('nome') or '').strip() or 'Sem nome'
    deposit_id = str(item.get('id') or '').strip() or 'sem id'
    return f'{name} · ID {deposit_id}'


def render_stock_target_panel(df: pd.DataFrame) -> pd.DataFrame | None:
    st.markdown('### Depósito do estoque no Bling')
    st.caption('Escolha o depósito que receberá a atualização de saldo nesta operação.')

    token, _meta = load_token()
    deposits = _load_stock_deposits(token) if isinstance(token, dict) and token.get('access_token') else []

    if deposits:
        labels = [_option_label(item) for item in deposits]
        current_id = str(st.session_state.get(API_STOCK_DEPOSIT_ID_KEY) or '').strip()
        index = 0
        for pos, item in enumerate(deposits):
            if current_id and str(item.get('id') or '').strip() == current_id:
                index = pos
                break
        selected_label = st.selectbox('Depósito que receberá o estoque', labels, index=index, key='api_stock_deposit_select')
        selected = deposits[labels.index(selected_label)]
        st.session_state[API_STOCK_DEPOSIT_ID_KEY] = str(selected.get('id') or '').strip()
        st.session_state[API_STOCK_DEPOSIT_KEY] = str(selected.get('nome') or '').strip()
    else:
        st.warning('Não consegui carregar os depósitos automaticamente. Informe o ID do depósito para continuar.')
        st.session_state[API_STOCK_DEPOSIT_ID_KEY] = st.text_input('ID do depósito no Bling', value=str(st.session_state.get(API_STOCK_DEPOSIT_ID_KEY) or ''), key='api_stock_deposit_manual_id').strip()
        st.session_state[API_STOCK_DEPOSIT_KEY] = st.text_input('Nome do depósito', value=str(st.session_state.get(API_STOCK_DEPOSIT_KEY) or ''), key='api_stock_deposit_manual_name').strip()

    deposit_id = str(st.session_state.get(API_STOCK_DEPOSIT_ID_KEY) or '').strip()
    deposit_name = str(st.session_state.get(API_STOCK_DEPOSIT_KEY) or '').strip()
    if not deposit_id:
        st.warning('Selecione ou informe o depósito antes de continuar.')
        return None

    out = df.copy().fillna('')
    out['Bling depósito id'] = deposit_id
    out['Bling depósito nome'] = deposit_name or deposit_id
    st.success(f'Estoque será atualizado no depósito: {deposit_name or deposit_id}.')
    add_audit_event('stock_target_selected_before_api_send', area='BLING_ENVIO', status='OK', details={'deposit_id': deposit_id, 'deposit_name': deposit_name, 'responsible_file': RESPONSIBLE_FILE})
    return out


__all__ = ['render_stock_target_panel']
