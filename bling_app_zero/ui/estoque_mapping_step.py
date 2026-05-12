from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.estoque_entry_step import render_deposito_missing_recovery
from bling_app_zero.ui.estoque_mapping import render_manual_estoque_mapping
from bling_app_zero.ui.estoque_wizard_state import (
    ESTOQUE_MODELO_KEY,
    current_stock_source,
    deposito_value,
    sync_manual_stock_output,
    valid_model,
)


def render_estoque_gerar_step() -> None:
    st.markdown('### Mapeamento do estoque')
    st.caption('Mapeamento manual exclusivo de estoque. Nada deve ser criado sem você ver o campo correspondente.')

    df_modelo = st.session_state.get(ESTOQUE_MODELO_KEY)
    deposito = deposito_value()
    df_origem, source_name = current_stock_source()

    if deposito:
        st.success(f'Depósito que será aplicado no CSV: {deposito}')
    else:
        deposito = render_deposito_missing_recovery()
        if not deposito:
            return

    if not valid_model(df_modelo):
        st.error('Modelo de estoque ausente. Volte para a entrada.')
        return
    if not isinstance(df_origem, pd.DataFrame) or df_origem.empty:
        st.warning('Nenhuma origem de estoque carregada. Volte para a entrada.')
        return

    st.info(f'Origem em uso no mapeamento: {source_name or "Origem de estoque"}')
    render_manual_estoque_mapping(df_origem, df_modelo, deposito)

    if sync_manual_stock_output(source_name):
        st.success('Mapeamento de estoque gerado. Continue para conferir o preview final.')


__all__ = ['render_estoque_gerar_step']
