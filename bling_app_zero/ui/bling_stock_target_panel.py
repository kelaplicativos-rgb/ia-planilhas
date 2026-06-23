from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_direct_sender_safe import (
    API_STOCK_DEPOSIT_ID_KEY,
    API_STOCK_DEPOSIT_KEY,
    API_STOCK_DEPOSIT_OPTIONS_KEY,
)
from bling_app_zero.core.bling_token_store import load_token

RESPONSIBLE_FILE = 'bling_app_zero/ui/bling_stock_target_panel.py'
MANUAL_DEPOSIT_CONFIRMED_KEY = 'api_stock_deposit_manual_confirmed'
MANUAL_DEPOSIT_ID_INPUT_KEY = 'api_stock_deposit_manual_id'
MANUAL_DEPOSIT_NAME_INPUT_KEY = 'api_stock_deposit_manual_name'
PLACEHOLDER_SELECT_DEPOSIT = 'Selecione o depósito do Bling...'


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
        st.session_state.pop('api_stock_deposit_select', None)
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


def _load_deposits_with_correct_endpoint_order() -> list[dict[str, str]]:
    """Busca depósitos pelo fluxo oficial da UI.

    O diagnóstico confirmou que `/depositos` responde corretamente e que
    `/estoques/depositos` pode retornar 404. Por isso este painel usa a busca
    de `home_bling_api_flow`, que já tenta `/depositos` antes dos fallbacks.
    """
    try:
        from bling_app_zero.ui.home_bling_api_flow import _fetch_stock_deposits

        deposits, error = _fetch_stock_deposits()
        if error:
            st.caption(error)
        return deposits or []
    except Exception as exc:
        add_audit_event(
            'stock_target_corrected_deposit_lookup_failed',
            area='BLING_ENVIO',
            status='AVISO',
            details={'error': str(exc)[:300], 'responsible_file': RESPONSIBLE_FILE},
        )
        return []


def _load_deposits_automatically() -> list[dict[str, str]]:
    token, meta = load_token()
    if not isinstance(token, dict) or not token.get('access_token'):
        st.warning('Bling conectado não encontrado nesta sessão. Reconecte o Bling para buscar depósitos automaticamente.')
        add_audit_event(
            'stock_target_auto_deposit_lookup_blocked_no_token',
            area='BLING_ENVIO',
            status='BLOQUEADO',
            details={'token_meta': meta, 'responsible_file': RESPONSIBLE_FILE},
        )
        return []

    with st.spinner('Buscando depósitos automaticamente dentro do Bling...'):
        deposits = _load_deposits_with_correct_endpoint_order()

    if deposits:
        add_audit_event(
            'stock_target_auto_deposit_lookup_loaded',
            area='BLING_ENVIO',
            status='OK',
            details={'count': len(deposits), 'lookup_order': 'depositos_first', 'responsible_file': RESPONSIBLE_FILE},
        )
        st.success(f'{len(deposits)} depósito(s) encontrado(s) automaticamente no Bling.')
    else:
        add_audit_event(
            'stock_target_auto_deposit_lookup_empty',
            area='BLING_ENVIO',
            status='BLOQUEADO',
            details={'lookup_order': 'depositos_first', 'responsible_file': RESPONSIBLE_FILE},
        )
    return deposits or []


def _select_detected_deposit(deposits: list[dict[str, str]]) -> bool:
    if not deposits:
        return False

    if len(deposits) == 1:
        selected = deposits[0]
        st.session_state[API_STOCK_DEPOSIT_ID_KEY] = str(selected.get('id') or '').strip()
        st.session_state[API_STOCK_DEPOSIT_KEY] = str(selected.get('nome') or '').strip()
        st.session_state[MANUAL_DEPOSIT_CONFIRMED_KEY] = False
        st.info('Depósito único detectado no Bling; ele foi selecionado automaticamente.')
        _render_retry_button('api_stock_retry_load_deposits_single')
        return True

    labels = [_option_label(item) for item in deposits]
    options = [PLACEHOLDER_SELECT_DEPOSIT] + labels

    # BLINGFIX: quando existem múltiplos depósitos, não reutilizar seleção gravada
    # por telas antigas com index=0. O widget final tem chave própria e exige uma
    # escolha explícita do usuário antes de salvar `Bling depósito id`.
    selected_label = st.selectbox('Depósito que receberá o estoque', options, index=0, key='api_stock_deposit_select')
    if selected_label == PLACEHOLDER_SELECT_DEPOSIT:
        st.session_state.pop(API_STOCK_DEPOSIT_ID_KEY, None)
        st.session_state.pop(API_STOCK_DEPOSIT_KEY, None)
        st.warning('Mais de um depósito foi encontrado. Escolha explicitamente qual depósito receberá a atualização de estoque.')
        _render_retry_button('api_stock_retry_load_deposits_multiple')
        return False

    selected = deposits[labels.index(selected_label)]
    st.session_state[API_STOCK_DEPOSIT_ID_KEY] = str(selected.get('id') or '').strip()
    st.session_state[API_STOCK_DEPOSIT_KEY] = str(selected.get('nome') or '').strip()
    st.session_state[MANUAL_DEPOSIT_CONFIRMED_KEY] = False
    _render_retry_button('api_stock_retry_load_deposits_loaded')
    return True


def render_stock_target_panel(df: pd.DataFrame) -> pd.DataFrame | None:
    st.markdown('### Depósito do estoque no Bling')
    st.caption('Operação estoque detectada: o sistema busca automaticamente os depósitos reais do Bling antes de liberar qualquer envio.')

    deposits = _load_deposits_automatically()

    if deposits:
        selected_ok = _select_detected_deposit(deposits)
        if not selected_ok:
            return None
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
