from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.cadastro_pricing import render_cadastro_pricing
from bling_app_zero.ui.shared_mapping import render_shared_stock_mapping


def _prepare_stock_source_with_pricing(df_source: pd.DataFrame) -> pd.DataFrame:
    """Aplica no estoque o mesmo motor de precificação usado no cadastro.

    Não cria motor novo. A origem passa pelo módulo oficial de precificação antes
    do mapeamento, permitindo escolher preço calculado para venda e manter custo
    separado quando a calculadora estiver ativa.
    """
    if not isinstance(df_source, pd.DataFrame) or df_source.empty:
        return df_source

    df_prepared = render_cadastro_pricing(df_source)
    df_prepared = st.session_state.get('df_origem_cadastro_precificada', df_prepared)

    if isinstance(df_prepared, pd.DataFrame) and not df_prepared.empty:
        st.session_state['estoque_wizard_df_para_mapear'] = df_prepared
        if bool(st.session_state.get('cadastro_preco_calculado_ativo', False)):
            st.success('Precificação aplicada antes do mapeamento de estoque.')
        return df_prepared

    return df_source


def render_manual_estoque_mapping(df_source: pd.DataFrame, df_modelo: pd.DataFrame | None, deposito: str) -> None:
    """Entrada oficial do mapeamento de estoque.

    O estoque usa o mapeador compartilhado, baseado no motor potente do cadastro,
    para evitar dois mapeadores evoluindo separados e quebrando comportamento.
    """
    df_source = _prepare_stock_source_with_pricing(df_source)
    render_shared_stock_mapping(df_source, df_modelo, deposito)


__all__ = ['render_manual_estoque_mapping']
