from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_direct_sender_safe import (
    API_STOCK_DEPOSIT_ID_KEY,
    API_STOCK_DEPOSIT_KEY,
    API_STOCK_DEPOSIT_OPTIONS_KEY,
    _load_stock_deposits,
)
from bling_app_zero.core.bling_token_store import load_token

RESPONSIBLE_FILE = 'bling_app_zero/ui/bling_stock_target_panel.py'
MANUAL_DEPOSIT_CONFIRMED_KEY = 'api_stock_deposit_manual_confirmed'
MANUAL_DEPOSIT_ID_INPUT_KEY = 'api_stock_deposit_manual_id'
MANUAL_DEPOSIT_NAME_INPUT_KEY = 'api_stock_deposit_manual_name'


def _option_label(item: dict[str, str]) -> str:
    name = str(item.get('nome') or '').strip() or 'Sem nome'
    deposit_id = str(item.get('id') or '').strip() or 'sem id'
    return f'{name} · ID {deposit_id}'


def _safe_rerun() -> None:
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass


def _clear_deposit_cache() -> None:
    for key in (API_STOCK_DEPOSIT_OPTIONS_KEY, API_STOCK_DEPOSIT_ID_KEY, API_STOCK_DEPOSIT_KEY, MANUAL_DEPOSIT_CONFIRMED_KEY):
        st.session_state.pop(key, None)


def _render_retry_button(button_key: str) -> None:
    if st.button('Buscar depósitos novamente', use_container_width=True, key=button_key):
        _clear_deposit_cache()
        add_audit_event(
            'stock_target_retry_load_deposits_clicked',
            area='BLING_ENVIO',
            status='INFO',
            details={'responsible_file': RESPONSIBLE_FILE, 'button_key': button_key},
        )
        _safe_rerun()


def _render_manual_deposit_controls() -> None:
    _render_retry_button('api_stock_retry_load_deposits_manual_top')

    current_id = str(st.session_state.get(API_STOCK_DEPOSIT_ID_KEY) or st.session_state.get(MANUAL_DEPOSIT_ID_INPUT_KEY) or '').strip()
    current_name = str(st.session_state.get(API_STOCK_DEPOSIT_KEY) or st.session_state.get(MANUAL_DEPOSIT_NAME_INPUT_KEY) or '').strip()

    manual_id = st.text_input('ID do depósito no Bling', value=current_id, key=MANUAL_DEPOSIT_ID_INPUT_KEY).strip()
    manual_name = st.text_input('Nome do depósito', value=current_name, key=MANUAL_DEPOSIT_NAME_INPUT_KEY).strip()

    if st.button('Usar este depósito e continuar', use_container_width=True, key='api_stock_confirm_manual_deposit'):
        if not manual_id:
            st.warning('Informe o ID do depósito antes de continuar.')
            return
        st.session_state[API_STOCK_DEPOSIT_ID_KEY] = manual_id
        st.session_state[API_STOCK_DEPOSIT_KEY] = manual_name or manual_id
        st.session_state[MANUAL_DEPOSIT_CONFIRMED_KEY] = True
        add_audit_event(
            'stock_target_manual_deposit_confirmed',
            area='BLING_ENVIO',
            status='OK',
            details={'deposit_id': manual_id, 'deposit_name': manual_name or manual_id, 'responsible_file': RESPONSIBLE_FILE},
        )
        _safe_rerun()

    if manual_id and not bool(st.session_state.get(MANUAL_DEPOSIT_CONFIRMED_KEY)):
        st.info('Toque em “Usar este depósito e continuar” para confirmar o ID digitado.')


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
        st.session_state[MANUAL_DEPOSIT_CONFIRMED_KEY] = False
        _render_retry_button('api_stock_retry_load_deposits_loaded')
    else:
        st.warning('Não consegui carregar os depósitos automaticamente.')
        _render_manual_deposit_controls()

    deposit_id = str(st.session_state.get(API_STOCK_DEPOSIT_ID_KEY) or '').strip()
    deposit_name = str(st.session_state.get(API_STOCK_DEPOSIT_KEY) or '').strip()
    if not deposit_id:
        st.warning('Selecione ou informe o depósito antes de continuar.')
        return None

    out = df.copy().fillna('')
    out['Bling depósito id'] = deposit_id
    out['Bling depósito nome'] = deposit_name or deposit_id
    st.success(f'Estoque será atualizado no depósito: {deposit_name or deposit_id}.')
    add_audit_event(
        'stock_target_selected_before_api_send',
        area='BLING_ENVIO',
        status='OK',
        details={'deposit_id': deposit_id, 'deposit_name': deposit_name, 'responsible_file': RESPONSIBLE_FILE},
    )
    return out


__all__ = ['render_stock_target_panel']
