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
from bling_app_zero.ui.rules_center_step import render_rules_center_step
from bling_app_zero.ui.shared_pricing import render_shared_pricing


def _render_stock_ai_adjustments() -> None:
    with st.expander('Ajustes com IA e proteções do arquivo final', expanded=False):
        st.caption(
            'Use esta área apenas para proteções globais. Depósito, coluna de quantidade, preço/custo e valores fixos continuam no mapeamento de estoque.'
        )
        render_rules_center_step()


def render_estoque_gerar_step() -> None:
    st.markdown('### Mapeamento + IA do estoque')
    st.caption(
        'Mapeamento manual exclusivo de estoque. Se o modelo tiver campo de preço/custo, '
        'ele também pode ser preenchido junto com a atualização de saldo.'
    )

    df_modelo = st.session_state.get(ESTOQUE_MODELO_KEY)
    deposito = deposito_value()
    df_origem, source_name = current_stock_source()

    if deposito:
        st.success(f'Depósito que será aplicado na planilha: {deposito}')
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
    _render_stock_ai_adjustments()

    df_para_mapear = render_shared_pricing(df_origem, channel='estoque')
    if bool(st.session_state.get('cadastro_preco_calculado_ativo', False)):
        st.success(
            'Calculadora aplicada à origem de estoque. Se o modelo possuir campo de preço/custo, '
            'o valor calculado poderá ser enviado junto com o saldo.'
        )

    render_manual_estoque_mapping(df_para_mapear, df_modelo, deposito)

    if sync_manual_stock_output(source_name):
        st.success('Mapeamento de estoque gerado. Continue para conferir o preview final.')


__all__ = ['render_estoque_gerar_step']
