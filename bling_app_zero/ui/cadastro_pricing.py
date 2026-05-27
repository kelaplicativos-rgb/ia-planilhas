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

PRICED_SOURCE_KEY = 'df_origem_cadastro_precificada'
PRICING_ACTIVE_KEY = 'cadastro_preco_calculado_ativo'
PRICING_SOURCE_KEY = 'shared_price_calculator_source'
PRICING_SELECTED_COST_COLUMN_KEY = 'price_calculator_source_cost_column'
PRICING_SELECTED_COST_COLUMN_LEGACY_KEY = 'global_price_source_cost_column'
CADASTRO_ORIGEM_PRICED_STATE_KEY = 'cadastro_wizard_df_para_mapear'


def apply_calculated_price_aliases(df: pd.DataFrame, calculated_column: str = 'Preço de venda') -> pd.DataFrame:
    return apply_price_aliases(df, calculated_column, PRICE_TARGET_ALIASES)


def _pricing_config() -> dict:
    return get_home_pricing_config()


def _pricing_enabled() -> bool:
    return bool(_pricing_config().get('enabled', False))


def _selected_cost_column(df_origem: pd.DataFrame) -> str:
    selected = str(st.session_state.get(PRICING_SELECTED_COST_COLUMN_KEY) or '').strip()
    if selected and selected in list(map(str, df_origem.columns)):
        return selected

    legacy_selected = str(st.session_state.get(PRICING_SELECTED_COST_COLUMN_LEGACY_KEY) or '').strip()
    if legacy_selected and legacy_selected in list(map(str, df_origem.columns)):
        st.session_state[PRICING_SELECTED_COST_COLUMN_KEY] = legacy_selected
        return legacy_selected

    return best_cost_column(list(map(str, df_origem.columns)))


def _store_pricing_state(signature: str, selected_cost_column: str) -> None:
    st.session_state[PRICING_ACTIVE_KEY] = True
    st.session_state[f'cadastro_coluna_custo_{signature}'] = selected_cost_column
    st.session_state[PRICING_SELECTED_COST_COLUMN_KEY] = selected_cost_column
    st.session_state[PRICING_SELECTED_COST_COLUMN_LEGACY_KEY] = selected_cost_column
    st.session_state[PRICING_SOURCE_KEY] = 'price_step_plugin'


def clear_cadastro_pricing_state() -> None:
    st.session_state[PRICING_ACTIVE_KEY] = False
    st.session_state.pop(PRICED_SOURCE_KEY, None)
    st.session_state.pop(CADASTRO_ORIGEM_PRICED_STATE_KEY, None)


def apply_cadastro_pricing(df_origem: pd.DataFrame, *, channel: str = 'etapa_preco') -> pd.DataFrame:
    """Aplica a precificação configurada na etapa Preço.

    BLINGMODULAR 2:
    - a calculadora visual pertence à etapa Preço;
    - o mapeamento não deve abrir nem recalcular a calculadora;
    - esta função apenas transforma a origem em origem precificada e salva o
      resultado em session_state para as próximas etapas consumirem.
    """
    if not isinstance(df_origem, pd.DataFrame) or df_origem.empty:
        return df_origem

    config = _pricing_config()
    selected_cost_column = _selected_cost_column(df_origem)
    result = apply_price_calculator_plugin(
        df_origem,
        enabled=_pricing_enabled(),
        config=config,
        cost_column=selected_cost_column,
        output_column='Preço de venda',
        channel=channel,
        aliases=PRICE_TARGET_ALIASES,
    )

    if not result.applied:
        clear_cadastro_pricing_state()
        return result.df

    origem_signature = df_signature(df_origem)
    _store_pricing_state(origem_signature, result.source_column)
    st.session_state[PRICED_SOURCE_KEY] = result.df
    st.session_state[CADASTRO_ORIGEM_PRICED_STATE_KEY] = result.df
    return result.df


def render_cadastro_pricing(df_origem: pd.DataFrame, *, channel: str = 'compatibilidade') -> pd.DataFrame:
    """Compatibilidade legado.

    Mantido para imports antigos, mas o fluxo principal agora chama
    `apply_cadastro_pricing()` diretamente na etapa Preço.
    """
    return apply_cadastro_pricing(df_origem, channel=channel)


__all__ = [
    'PRICE_TARGET_ALIASES',
    'PRICED_SOURCE_KEY',
    'PRICING_ACTIVE_KEY',
    'PRICING_SELECTED_COST_COLUMN_KEY',
    'PRICING_SELECTED_COST_COLUMN_LEGACY_KEY',
    'apply_calculated_price_aliases',
    'apply_cadastro_pricing',
    'best_cost_column',
    'clear_cadastro_pricing_state',
    'render_cadastro_pricing',
]
