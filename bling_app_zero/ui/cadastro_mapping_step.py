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
    df_origem = st.session_state.get(CADASTRO_ORIGEM_KEY)
    df_modelo = st.session_state.get(CADASTRO_MODELO_KEY)

    if not valid_df(df_origem):
        st.warning('Nenhuma planilha com dados carregada. Volte para Enviar dados.')
        return
    if not valid_model(df_modelo):
        st.warning('Planilha modelo ausente. Volte para Enviar modelo.')
        return

    store_expected_source_rows(df_origem)

    col_a, col_b = st.columns(2)
    with col_a:
        st.metric('Produtos encontrados', len(df_origem))
    with col_b:
        st.metric('Colunas para preencher', len(df_modelo.columns))

    df_para_mapear = render_cadastro_pricing(df_origem)
    df_para_mapear = st.session_state.get('df_origem_cadastro_precificada', df_para_mapear)
    if isinstance(df_para_mapear, pd.DataFrame):
        st.session_state[CADASTRO_ORIGEM_PRICED_KEY] = df_para_mapear
    if bool(st.session_state.get('cadastro_preco_calculado_ativo', False)):
        st.success('Preço calculado. O campo Preço de venda será usado nas colunas de preço.')

    render_shared_cadastro_mapping(df_para_mapear, df_modelo)

    df_final = enforce_cadastro_model_columns(st.session_state.get('df_final_cadastro'))
    if isinstance(df_final, pd.DataFrame) and len(df_final) != len(df_origem):
        render_row_count_blocker(df_final)


__all__ = ['render_cadastro_mapeamento_step']
