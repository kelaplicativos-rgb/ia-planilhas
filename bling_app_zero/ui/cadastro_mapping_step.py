from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.cadastro_wizard_state import (
    CADASTRO_MODELO_KEY,
    CADASTRO_ORIGEM_KEY,
    CADASTRO_ORIGEM_PRICED_KEY,
    cadastro_mapping_ready,
    enforce_cadastro_model_columns,
    render_row_count_blocker,
    store_expected_source_rows,
    valid_df,
    valid_model,
)
from bling_app_zero.ui.shared_mapping import render_shared_cadastro_mapping

RESPONSIBLE_FILE = 'bling_app_zero/ui/cadastro_mapping_step.py'


def _render_post_mapping_notice() -> None:
    """Mantém o usuário no fluxo seguro: revisão, preview e só depois download."""
    if not cadastro_mapping_ready():
        st.info('Confirme o mapeamento para liberar a revisão, o preview e o download final.')
        return

    st.success('Mapeamento confirmado. O download será liberado no final, após a revisão e o preview blindado.')
    st.caption(
        'BLINGFIX: o download imediato foi removido desta etapa para evitar arquivo baixado antes da conferência final.'
    )


def _df_for_mapping(df_origem: pd.DataFrame) -> pd.DataFrame:
    """Retorna a origem que o mapeamento deve consumir.

    BLINGMODULAR 2: a calculadora não roda mais nesta tela. Se a etapa Preço
    gerou uma origem precificada, ela é usada; caso contrário, o mapeamento usa a
    origem bruta do fornecedor.
    """
    df_precificado = st.session_state.get(CADASTRO_ORIGEM_PRICED_KEY)
    if isinstance(df_precificado, pd.DataFrame) and not df_precificado.empty:
        return df_precificado
    return df_origem


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

    df_para_mapear = _df_for_mapping(df_origem)

    col_a, col_b = st.columns(2)
    with col_a:
        st.metric('Produtos encontrados', len(df_origem))
    with col_b:
        st.metric('Colunas para preencher', len(df_modelo.columns))

    if bool(st.session_state.get('cadastro_preco_calculado_ativo', False)):
        st.success('Preço calculado na etapa Preço. O campo Preço de venda está disponível para o mapeamento.')

    render_shared_cadastro_mapping(df_para_mapear, df_modelo)

    df_final = enforce_cadastro_model_columns(st.session_state.get('df_final_cadastro'))
    if isinstance(df_final, pd.DataFrame) and len(df_final) != len(df_origem):
        if render_row_count_blocker(df_final):
            return

    _render_post_mapping_notice()


__all__ = ['render_cadastro_mapeamento_step']
