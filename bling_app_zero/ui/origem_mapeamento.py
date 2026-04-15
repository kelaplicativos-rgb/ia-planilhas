
from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import ir_para_etapa, safe_df_dados, safe_df_estrutura
from bling_app_zero.ui.origem_mapeamento_core import (
    obter_df_base_para_mapeamento,
    obter_modelo_destino,
    salvar_resultado_mapeamento,
)
from bling_app_zero.ui.origem_mapeamento_ui import render_bloco_mapeamento


def render_origem_mapeamento(
    df_origem: pd.DataFrame | None = None,
    df_modelo: pd.DataFrame | None = None,
) -> pd.DataFrame | None:
    df_base = df_origem if safe_df_dados(df_origem) else obter_df_base_para_mapeamento()
    df_destino = df_modelo if safe_df_estrutura(df_modelo) else obter_modelo_destino()

    if not safe_df_dados(df_base):
        st.warning("Carregue uma origem válida antes de abrir o mapeamento.")
        return None

    if not safe_df_estrutura(df_destino):
        st.warning("Nenhum modelo de destino disponível para mapear.")
        return None

    mapping_novo, defaults_novos, df_preview = render_bloco_mapeamento(df_base, df_destino)

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("⬅️ Voltar para precificação", use_container_width=True, key="btn_map_voltar"):
            ir_para_etapa("precificacao")

    with col2:
        if st.button("Salvar mapeamento", use_container_width=True, key="btn_map_salvar"):
            st.session_state["mapping_origem"] = mapping_novo.copy()
            st.session_state["mapping_origem_defaults"] = defaults_novos.copy()
            salvar_resultado_mapeamento(df_preview)
            st.success("Mapeamento salvo.")

    with col3:
        if st.button(
            "Continuar para preview final ➡️",
            use_container_width=True,
            key="btn_map_continuar",
            type="primary",
        ):
            st.session_state["mapping_origem"] = mapping_novo.copy()
            st.session_state["mapping_origem_defaults"] = defaults_novos.copy()
            salvar_resultado_mapeamento(df_preview)
            ir_para_etapa("final")

    return df_preview
