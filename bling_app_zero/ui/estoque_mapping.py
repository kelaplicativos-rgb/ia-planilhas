from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.shared_mapping import render_shared_stock_mapping
from bling_app_zero.ui.shared_pricing import render_shared_pricing


def _prepare_stock_source_with_pricing(df_source: pd.DataFrame) -> pd.DataFrame:
    """Aplica o motor compartilhado de precificação antes do mapeamento de estoque.

    O Bling pode atualizar saldo e também preço/custo quando esses campos existem
    no modelo de importação. Por isso a calculadora permanece disponível no fluxo
    de estoque, sem amarrar a implementação ao nome do cadastro.
    """
    if not isinstance(df_source, pd.DataFrame) or df_source.empty:
        return df_source

    df_prepared = render_shared_pricing(df_source, channel='estoque')
    df_prepared = st.session_state.get('df_origem_cadastro_precificada', df_prepared)

    if isinstance(df_prepared, pd.DataFrame) and not df_prepared.empty:
        st.session_state['estoque_wizard_df_para_mapear'] = df_prepared
        if bool(st.session_state.get('cadastro_preco_calculado_ativo', False)):
            st.success('Precificação aplicada antes do mapeamento de estoque.')
        return df_prepared

    return df_source


def render_manual_estoque_mapping(df_source: pd.DataFrame, df_modelo: pd.DataFrame | None, deposito: str) -> None:
    """Entrada oficial do mapeamento de estoque.

    O estoque usa o mapeador compartilhado para manter a inteligência de sugestão,
    mas preserva regras próprias de depósito, saldo e campos de preço/custo.
    """
    df_source = _prepare_stock_source_with_pricing(df_source)
    render_shared_stock_mapping(df_source, df_modelo, deposito)


__all__ = ['render_manual_estoque_mapping']
