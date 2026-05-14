from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.shared_price_calculator import apply_shared_pricing
from bling_app_zero.ui.home_pricing_config import get_home_pricing_config
from bling_app_zero.ui.home_shared import df_signature

PRICE_TARGET_ALIASES = [
    'Preço de venda',
    'Preço unitário (OBRIGATÓRIO)',
    'Preço unitário',
    'Preço',
    'Valor',
]

COST_STRONG_TERMS = ['preço custo', 'preco custo', 'valor custo', 'custo', 'cost', 'preco compra', 'preço compra', 'valor compra']
COST_WEAK_TERMS = ['valor produto', 'valor', 'preço', 'preco', 'price']
BAD_COST_TERMS = ['venda', 'unitario', 'unitário', 'marketplace', 'comissao', 'comissão', 'taxa', 'lucro']


def apply_calculated_price_aliases(df: pd.DataFrame, calculated_column: str = 'Preço de venda') -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty or calculated_column not in df.columns:
        return df
    out = df.copy().fillna('')
    calculated_values = out[calculated_column]
    for column in PRICE_TARGET_ALIASES:
        out[column] = calculated_values
    return out


def _column_score_for_cost(column: str) -> int:
    text = str(column or '').lower()
    score = 0
    for term in COST_STRONG_TERMS:
        if term in text:
            score += 100
    for term in COST_WEAK_TERMS:
        if term in text:
            score += 35
    for term in BAD_COST_TERMS:
        if term in text:
            score -= 60
    return score


def best_cost_column(columns: list[str]) -> int:
    if not columns:
        return 0
    scored = [(index, _column_score_for_cost(column)) for index, column in enumerate(columns)]
    best_index, best_score = max(scored, key=lambda item: item[1])
    return best_index if best_score > 0 else 0


def _pricing_config() -> dict:
    return get_home_pricing_config()


def _pricing_enabled() -> bool:
    return bool(_pricing_config().get('enabled', False))


def _store_pricing_state(signature: str, selected_cost_column: str) -> None:
    st.session_state['cadastro_preco_calculado_ativo'] = True
    st.session_state[f'cadastro_coluna_custo_{signature}'] = selected_cost_column
    st.session_state['shared_price_calculator_source'] = 'cadastro_estoque'


def render_cadastro_pricing(df_origem: pd.DataFrame) -> pd.DataFrame:
    """Aplica a calculadora compartilhada do multiloja no cadastro.

    Serve para origem por site ou anexo. A tela de configuração fica na etapa
    Preço da Home; aqui apenas aplicamos o motor único sobre a coluna de custo.
    """
    if not isinstance(df_origem, pd.DataFrame) or df_origem.empty:
        return df_origem

    if not _pricing_enabled():
        st.session_state['cadastro_preco_calculado_ativo'] = False
        st.session_state.pop('df_origem_cadastro_precificada', None)
        return df_origem

    columns = [str(c) for c in df_origem.columns]
    if not columns:
        st.session_state['cadastro_preco_calculado_ativo'] = False
        st.session_state.pop('df_origem_cadastro_precificada', None)
        return df_origem

    origem_signature = df_signature(df_origem)
    config = _pricing_config()
    cost_column = columns[best_cost_column(columns)]
    _store_pricing_state(origem_signature, cost_column)

    df_precificado = apply_shared_pricing(
        df_origem,
        cost_column=cost_column,
        output_column='Preço de venda',
        config=config,
        channel='cadastro_estoque',
    )
    df_precificado = apply_calculated_price_aliases(df_precificado, 'Preço de venda')
    st.session_state['df_origem_cadastro_precificada'] = df_precificado
    return df_precificado


__all__ = [
    'PRICE_TARGET_ALIASES',
    'apply_calculated_price_aliases',
    'best_cost_column',
    'render_cadastro_pricing',
]
