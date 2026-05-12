from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.cadastro_pricing import render_cadastro_pricing
from bling_app_zero.ui.cadastro_wizard_state import (
    CADASTRO_MODELO_KEY,
    CADASTRO_ORIGEM_KEY,
    CADASTRO_ORIGEM_PRICED_KEY,
    enforce_cadastro_model_columns,
    render_row_count_blocker,
    store_expected_source_rows,
    valid_df,
    valid_model,
)
from bling_app_zero.ui.shared_mapping import render_shared_cadastro_mapping


def render_cadastro_mapeamento_step() -> None:
    st.markdown('### Mapeamento do cadastro')
    st.caption('Conferência das colunas. Preview final e download ficam separados para deixar esta tela mais leve.')

    df_origem = st.session_state.get(CADASTRO_ORIGEM_KEY)
    df_modelo = st.session_state.get(CADASTRO_MODELO_KEY)

    if not valid_df(df_origem):
        st.warning('Nenhuma origem de cadastro carregada. Volte para a etapa Entrada.')
        return
    if not valid_model(df_modelo):
        st.warning('Modelo de cadastro ausente. Volte para a etapa Modelo.')
        return

    store_expected_source_rows(df_origem)
    st.caption(f'Origem em uso no mapeamento: {len(df_origem)} produto(s).')

    df_para_mapear = render_cadastro_pricing(df_origem)
    df_para_mapear = st.session_state.get('df_origem_cadastro_precificada', df_para_mapear)
    if isinstance(df_para_mapear, pd.DataFrame):
        st.session_state[CADASTRO_ORIGEM_PRICED_KEY] = df_para_mapear
    if bool(st.session_state.get('cadastro_preco_calculado_ativo', False)):
        st.success('Precificação aplicada. O campo Preço de venda será usado como base para os campos de preço do Bling.')

    render_shared_cadastro_mapping(df_para_mapear, df_modelo)

    df_final = enforce_cadastro_model_columns(st.session_state.get('df_final_cadastro'))
    if isinstance(df_final, pd.DataFrame) and len(df_final) != len(df_origem):
        render_row_count_blocker(df_final)


__all__ = ['render_cadastro_mapeamento_step']
