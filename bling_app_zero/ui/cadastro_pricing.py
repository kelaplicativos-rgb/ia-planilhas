from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.price_calculator_plugin import (
    PRICE_TARGET_ALIASES,
    apply_price_aliases,
    apply_price_calculator_plugin,
    best_cost_column,
)
from bling_app_zero.ui.home_pricing_config import get_home_pricing_config
from bling_app_zero.ui.home_shared import df_signature


def apply_calculated_price_aliases(df: pd.DataFrame, calculated_column: str = 'Preço de venda') -> pd.DataFrame:
    return apply_price_aliases(df, calculated_column, PRICE_TARGET_ALIASES)


def _pricing_config() -> dict:
    return get_home_pricing_config()


def _pricing_enabled() -> bool:
    return bool(_pricing_config().get('enabled', False))


def _store_pricing_state(signature: str, selected_cost_column: str) -> None:
    st.session_state['cadastro_preco_calculado_ativo'] = True
    st.session_state[f'cadastro_coluna_custo_{signature}'] = selected_cost_column
    st.session_state['shared_price_calculator_source'] = 'price_calculator_plugin'


def _clear_pricing_state() -> None:
    st.session_state['cadastro_preco_calculado_ativo'] = False
    st.session_state.pop('df_origem_cadastro_precificada', None)


def render_cadastro_pricing(df_origem: pd.DataFrame, *, channel: str = 'cadastro_estoque') -> pd.DataFrame:
    """Aplica a calculadora plugável em qualquer origem tabular.

    A configuração visual fica na etapa Preço da Home. Esta função é apenas uma
    ponte de compatibilidade para cadastro/estoque chamarem o plugin universal.
    """
    if not isinstance(df_origem, pd.DataFrame) or df_origem.empty:
        return df_origem

    config = _pricing_config()
    result = apply_price_calculator_plugin(
        df_origem,
        enabled=_pricing_enabled(),
        config=config,
        output_column='Preço de venda',
        channel=channel,
        aliases=PRICE_TARGET_ALIASES,
    )

    if not result.applied:
        _clear_pricing_state()
        return result.df

    origem_signature = df_signature(df_origem)
    _store_pricing_state(origem_signature, result.source_column)
    st.session_state['df_origem_cadastro_precificada'] = result.df
    return result.df


__all__ = [
    'PRICE_TARGET_ALIASES',
    'apply_calculated_price_aliases',
    'best_cost_column',
    'render_cadastro_pricing',
]
