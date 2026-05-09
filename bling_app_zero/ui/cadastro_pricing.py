from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.home_pricing_config import get_home_pricing_config
from bling_app_zero.ui.home_shared import df_signature, load_apply_pricing

DEFAULT_PROFIT_PERCENT = 50.0

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


def _pricing_values() -> dict[str, float]:
    config = _pricing_config()
    return {
        'profit_percent': float(config.get('profit_percent', DEFAULT_PROFIT_PERCENT) or 0.0),
        'tax_percent': float(config.get('tax_percent', 0.0) or 0.0),
        'fee_percent': float(config.get('fee_percent', 0.0) or 0.0),
        'discount_percent': float(config.get('discount_percent', 0.0) or 0.0),
        'fixed_value': float(config.get('fixed_value', 0.0) or 0.0),
    }


def _store_pricing_state(signature: str, selected_cost_column: str, values: dict[str, float]) -> None:
    st.session_state['cadastro_preco_calculado_ativo'] = True
    st.session_state[f'cadastro_coluna_custo_{signature}'] = selected_cost_column
    st.session_state[f'cadastro_margem_{signature}'] = values['profit_percent']
    st.session_state[f'cadastro_imposto_{signature}'] = values['tax_percent']
    st.session_state[f'cadastro_taxa_{signature}'] = values['fee_percent']
    st.session_state['cadastro_desconto_comissao'] = values['discount_percent']
    st.session_state[f'cadastro_fixo_{signature}'] = values['fixed_value']


def render_cadastro_pricing(df_origem: pd.DataFrame) -> pd.DataFrame:
    """Aplica a precificação configurada na Home sem duplicar campos na tela de cadastro."""
    if not isinstance(df_origem, pd.DataFrame) or df_origem.empty:
        return df_origem

    if not _pricing_enabled():
        st.session_state['cadastro_preco_calculado_ativo'] = False
        st.session_state.pop('df_origem_cadastro_precificada', None)
        return df_origem

    colunas = [str(c) for c in df_origem.columns]
    if not colunas:
        st.session_state['cadastro_preco_calculado_ativo'] = False
        st.session_state.pop('df_origem_cadastro_precificada', None)
        return df_origem

    origem_signature = df_signature(df_origem)
    values = _pricing_values()
    coluna_custo = colunas[best_cost_column(colunas)]
    _store_pricing_state(origem_signature, coluna_custo, values)

    apply_pricing = load_apply_pricing()
    df_precificado = apply_pricing(
        df_origem,
        coluna_custo,
        'Preço de venda',
        values['profit_percent'],
        values['tax_percent'],
        values['fee_percent'],
        values['fixed_value'],
        values['discount_percent'],
    )
    df_precificado = apply_calculated_price_aliases(df_precificado, 'Preço de venda')
    st.session_state['df_origem_cadastro_precificada'] = df_precificado
    return df_precificado
