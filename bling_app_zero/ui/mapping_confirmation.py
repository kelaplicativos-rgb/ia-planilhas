from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.credits import check_mapping_credit, consume_mapping_credit, credits_enabled
from bling_app_zero.ui.home_shared import df_signature
from bling_app_zero.ui.mapping_constants import CADASTRO_MAPPING_CONFIRMED_KEY, CADASTRO_MAPPING_SIGNATURE_KEY
from bling_app_zero.ui.mapping_widget_state import is_manual_value, manual_value_key, short_hash, target_widget_key


def manual_values_for_signature(mapping: dict[str, str], target_columns: list[str], mapping_key: str) -> list[str]:
    parts: list[str] = []
    for index, target in enumerate(target_columns):
        if is_manual_value(mapping.get(target, '')):
            widget_key = target_widget_key(mapping_key, index)
            parts.append(f'{target}:{st.session_state.get(manual_value_key(widget_key), "")}')
    return parts


def mapping_signature(
    mapping: dict[str, str],
    df_final: pd.DataFrame,
    target_columns: list[str] | None = None,
    mapping_key: str = '',
) -> str:
    parts = [f'{key}={mapping.get(key, "")}' for key in sorted(mapping)]
    if target_columns and mapping_key:
        parts.extend(manual_values_for_signature(mapping, target_columns, mapping_key))
    return short_hash('|'.join(parts) + ':' + df_signature(df_final), size=16)


def invalidate_confirmation_if_changed(
    mapping: dict[str, str],
    df_final: pd.DataFrame,
    target_columns: list[str],
    mapping_key: str,
) -> str:
    signature = mapping_signature(mapping, df_final, target_columns, mapping_key)
    confirmed_signature = st.session_state.get(CADASTRO_MAPPING_SIGNATURE_KEY)
    if confirmed_signature and confirmed_signature != signature:
        st.session_state.pop(CADASTRO_MAPPING_CONFIRMED_KEY, None)
        st.session_state.pop(CADASTRO_MAPPING_SIGNATURE_KEY, None)
    return signature


def _render_credit_status(signature: str) -> bool:
    check = check_mapping_credit(signature)
    if not check.enabled:
        return True
    if check.allowed:
        st.info(f'💳 {check.message} Saldo atual: {check.balance} crédito(s).')
        return True
    st.error(f'💳 {check.message} Saldo atual: {check.balance} crédito(s).')
    st.caption('Adicione créditos no sidebar para liberar a confirmação desta planilha mapeada.')
    return False


def render_confirm_mapping_button(
    mapping: dict[str, str],
    df_final: pd.DataFrame,
    mapping_key: str,
    target_columns: list[str],
) -> None:
    signature = invalidate_confirmation_if_changed(mapping, df_final, target_columns, mapping_key)
    confirmed = bool(st.session_state.get(CADASTRO_MAPPING_CONFIRMED_KEY)) and st.session_state.get(CADASTRO_MAPPING_SIGNATURE_KEY) == signature
    if confirmed:
        st.success('Mapeamento confirmado. Você já pode continuar para o preview final.')
        return

    has_credit = _render_credit_status(signature)
    st.info('Revise os campos necessários e clique em Confirmar mapeamento para liberar o Preview.')
    if st.button('Confirmar mapeamento', use_container_width=True, key=f'{mapping_key}_confirm', disabled=credits_enabled() and not has_credit):
        if not consume_mapping_credit(signature, operation='cadastro'):
            st.error('Créditos insuficientes para confirmar esta planilha mapeada.')
            return
        st.session_state[CADASTRO_MAPPING_CONFIRMED_KEY] = True
        st.session_state[CADASTRO_MAPPING_SIGNATURE_KEY] = signature
        st.success('Mapeamento confirmado.')
        st.rerun()


__all__ = [
    'invalidate_confirmation_if_changed',
    'manual_values_for_signature',
    'mapping_signature',
    'render_confirm_mapping_button',
]
