from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.flow_spine import build_flow_spine_plan, is_api_destination
from bling_app_zero.ui.cadastro_wizard_state import get_context_final_df, set_context_final_df, valid_df
from bling_app_zero.ui.home_download import _render_api_final
from bling_app_zero.ui.home_shared import df_signature, download_final

RESPONSIBLE_FILE = 'bling_app_zero/ui/cadastro_download_step.py'
HOME_ENTRY_CONTEXT_KEY = 'home_entry_context'
DOWNLOAD_SIGNATURE_KEY = 'df_final_download_signature'


def _flow_plan():
    return build_flow_spine_plan()


def _entry_context() -> str:
    return str(st.session_state.get(HOME_ENTRY_CONTEXT_KEY) or 'universal').strip().lower() or 'universal'


def _current_operation() -> str:
    return 'universal'


def _final_df_for_context(operation: str) -> pd.DataFrame | None:
    df_final = get_context_final_df()
    if isinstance(df_final, pd.DataFrame) and not df_final.empty:
        return df_final.copy().fillna('')
    for key in (
        'df_final_universal',
        'df_final_cadastro',
        'df_final_estoque',
        'df_final_download_snapshot',
        'df_final_cadastro_preview_rules_applied',
    ):
        value = st.session_state.get(key)
        if isinstance(value, pd.DataFrame) and not value.empty:
            return value.copy().fillna('')
    return None


def _store_output_consistency(df_final: pd.DataFrame, operation: str) -> None:
    signature = df_signature(df_final)
    st.session_state['df_final_download_operation'] = 'universal'
    st.session_state['final_download_operation'] = 'universal'
    st.session_state[DOWNLOAD_SIGNATURE_KEY] = signature
    st.session_state['flow_spine_final_destination'] = _flow_plan().final_destination
    set_context_final_df(df_final.copy().fillna(''))


def render_cadastro_download_step() -> None:
    plan = _flow_plan()
    operation = _current_operation()
    st.markdown('### Download')
    st.caption('Baixe o modelo mapeado usando exatamente o layout anexado.')

    df_final = _final_df_for_context(operation)
    if not valid_df(df_final):
        st.warning('O resultado final ainda não foi gerado. Volte para a prévia final.')
        return

    _store_output_consistency(df_final, operation)

    if is_api_destination(plan):
        st.success('Base revisada pronta para envio.')
        _render_api_final(df_final, operation, f'{_entry_context()}_{operation}')
        return

    st.success('Modelo mapeado pronto para download.')
    download_final(df_final, operation, f'{_entry_context()}_{operation}')


__all__ = ['render_cadastro_download_step']
