from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_api_contract import OP_ATUALIZACAO_PRECO as PRICE_UPDATE_OPERATION
from bling_app_zero.ui.home_wizard_ui import render_pending_notice
from bling_app_zero.ui.universal_wizard_state import (
    UNIVERSAL_MODELO_KEY,
    UNIVERSAL_ORIGEM_KEY,
    UNIVERSAL_ORIGEM_PRICED_KEY,
    store_universal_context,
)
from bling_app_zero.universal.model_contract_detector import MODEL_CONTRACT_TYPE_KEY

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_wizard_price_update.py'


def is_price_update_contract(operation: str) -> bool:
    return str(operation or '').strip() == PRICE_UPDATE_OPERATION


def price_update_model_df() -> pd.DataFrame | None:
    for key in (
        'home_modelo_atualizacao_preco_df',
        'df_modelo_atualizacao_preco',
        'modelo_atualizacao_preco_df',
        UNIVERSAL_MODELO_KEY,
    ):
        df = st.session_state.get(key)
        if isinstance(df, pd.DataFrame) and len(df.columns):
            return df.copy().fillna('')
    return None


def bind_price_update_single_sheet() -> bool:
    df_modelo = price_update_model_df()
    if not isinstance(df_modelo, pd.DataFrame) or not len(df_modelo.columns):
        return False

    df_origem = df_modelo.copy().fillna('')
    store_universal_context(df_origem, df_modelo, None)
    st.session_state[UNIVERSAL_ORIGEM_PRICED_KEY] = df_origem.copy().fillna('')
    st.session_state['home_slim_flow_origin'] = 'arquivo'
    st.session_state['origem_final'] = 'arquivo'
    st.session_state['operacao_final'] = PRICE_UPDATE_OPERATION
    st.session_state['tipo_operacao_final'] = PRICE_UPDATE_OPERATION
    st.session_state['home_detected_operation'] = PRICE_UPDATE_OPERATION
    st.session_state['home_slim_flow_operation'] = PRICE_UPDATE_OPERATION
    st.session_state[MODEL_CONTRACT_TYPE_KEY] = PRICE_UPDATE_OPERATION
    add_audit_event(
        'price_update_single_sheet_bound',
        area='PRECOS',
        step='entrada',
        status='OK',
        details={
            'rows': len(df_origem),
            'columns': len(df_origem.columns),
            'mode': 'same_sheet_as_source_and_contract',
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return True


def render_price_update_single_sheet_notice() -> None:
    if bind_price_update_single_sheet():
        st.success('Atualização de preços detectada: a planilha anexada será usada como origem e como modelo final. Não é necessário enviar outra planilha.')
        df = st.session_state.get(UNIVERSAL_ORIGEM_KEY)
        if isinstance(df, pd.DataFrame):
            st.caption(f'Planilha única vinculada · {len(df)} linha(s) · {len(df.columns)} coluna(s).')
    else:
        render_pending_notice('Anexe a planilha de atualização de preços para continuar.')


__all__ = [
    'PRICE_UPDATE_OPERATION',
    'bind_price_update_single_sheet',
    'is_price_update_contract',
    'price_update_model_df',
    'render_price_update_single_sheet_notice',
]
