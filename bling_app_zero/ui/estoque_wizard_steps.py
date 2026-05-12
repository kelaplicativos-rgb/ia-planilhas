from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.estoque_entry_step import render_deposito_missing_recovery, render_estoque_entrada_step
from bling_app_zero.ui.estoque_mapping import render_manual_estoque_mapping
from bling_app_zero.ui.estoque_outputs import render_stock_downloads, render_stock_preview
from bling_app_zero.ui.estoque_wizard_state import (
    BLING_IMPORTADOR_ESTOQUE_URL,
    ESTOQUE_MODELO_KEY,
    build_stock_outputs_if_possible,
    current_stock_source,
    deposito_value,
    estoque_context_ready,
    estoque_output_ready,
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


def render_estoque_preview_step() -> None:
    st.markdown('### Preview final do estoque')
    st.caption('Confira os dados antes de baixar. O download fica na próxima etapa.')

    if not build_stock_outputs_if_possible():
        st.warning('O preview de estoque ainda não foi gerado. Volte para o mapeamento do estoque.')
        return
    render_stock_preview()


def render_estoque_download_step() -> None:
    st.markdown('### Download do estoque')
    st.caption('Última etapa: baixe somente o CSV final de atualização de estoque.')

    if not build_stock_outputs_if_possible():
        st.warning('Ainda não há CSV de estoque. Volte para o mapeamento do estoque.')
        return
    render_stock_downloads()

    st.markdown('#### Próximo passo no Bling')
    st.caption('Depois de baixar o CSV, abra direto o importador de saldos de estoque do Bling e envie o arquivo gerado.')
    st.link_button(
        '🔗 Abrir importador de estoque no Bling',
        BLING_IMPORTADOR_ESTOQUE_URL,
        use_container_width=True,
    )


__all__ = [
    'estoque_context_ready',
    'estoque_output_ready',
    'render_estoque_download_step',
    'render_estoque_entrada_step',
    'render_estoque_gerar_step',
    'render_estoque_preview_step',
]
