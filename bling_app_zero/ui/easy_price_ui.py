from __future__ import annotations

from decimal import Decimal

import pandas as pd
import streamlit as st

from bling_app_zero.core.easy_reprice import calc_easy_promo_price, calc_easy_sale_price
from bling_app_zero.core.price_calculator_plugin import best_cost_column
from bling_app_zero.v2.marketplace_calculator import D, money
from bling_app_zero.v2.price_multistore.quick_ui import (
    GLOBAL_PRICE_CONFIG_KEY,
    GLOBAL_PRICE_READY_KEY,
    GLOBAL_PRICE_SOURCE_COST_COLUMN_KEY,
    PRICE_CALCULATOR_CONFIG_KEY,
    PRICE_CALCULATOR_PROMO_DISCOUNT_KEY,
    PRICE_CALCULATOR_READY_KEY,
    PRICE_CALCULATOR_SOURCE_COST_COLUMN_KEY,
)

EASY_PRICE_MODE_KEY = 'easy_price_mode_v1'
EASY_PRICE_MARKUP_KEY = 'easy_price_markup_percent_v1'
EASY_PRICE_TAX_KEY = 'easy_price_tax_percent_v1'
EASY_PRICE_FEE_KEY = 'easy_price_fee_percent_v1'
EASY_PRICE_PROFIT_KEY = 'easy_price_profit_percent_v1'
EASY_PRICE_FIXED_KEY = 'easy_price_fixed_value_v1'
EASY_PRICE_PROMO_ACTION_KEY = 'easy_price_promo_action_v1'
EASY_PRICE_PROMO_BASE_KEY = 'easy_price_promo_base_v1'

PROMO_ACTION_KEEP = 'Não alterar promocional'
PROMO_ACTION_CLEAR = 'Limpar promocional'
PROMO_ACTION_DISCOUNT = 'Aplicar desconto promocional'
PROMO_BASE_ADJUSTED = 'Preço ajustado'
PROMO_BASE_ORIGINAL = 'Preço original'


def _has_df(df: pd.DataFrame | None) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0


def _to_decimal(value) -> Decimal:
    return D(value)


def _first_value(df: pd.DataFrame, column: str) -> Decimal:
    if not _has_df(df) or column not in df.columns:
        return Decimal('0')
    for value in df[column].tolist():
        parsed = _to_decimal(value)
        if parsed > 0:
            return parsed
    return Decimal('0')


def _selected_column(source_df: pd.DataFrame | None) -> tuple[str, Decimal]:
    if not _has_df(source_df):
        return '', Decimal('0')
    columns = [str(column) for column in source_df.columns]
    detected = best_cost_column(columns)
    saved = st.session_state.get(PRICE_CALCULATOR_SOURCE_COST_COLUMN_KEY) or st.session_state.get(GLOBAL_PRICE_SOURCE_COST_COLUMN_KEY) or detected
    if saved not in columns:
        saved = detected if detected in columns else columns[0]
    selected = st.selectbox('Coluna base dos preços', columns, index=columns.index(saved), key=PRICE_CALCULATOR_SOURCE_COST_COLUMN_KEY)
    st.session_state[GLOBAL_PRICE_SOURCE_COST_COLUMN_KEY] = selected
    return selected, _first_value(source_df, selected)


def _config(mode: str, markup: float, tax: float, fee: float, profit: float, fixed: float, promo: float, promo_action: str, promo_base: str) -> dict:
    if mode == 'Preço mínimo real':
        return {
            'enabled': True,
            'quick_reprice_mode': 'net_margin',
            'quick_markup_percent': float(profit or 0.0),
            'tax_percent': float(tax or 0.0),
            'marketplace_fee_percent': float(fee or 0.0),
            'quick_fixed_addition': float(fixed or 0.0),
            'promo_discount_percent': float(promo or 0.0),
            'promo_action': str(promo_action or PROMO_ACTION_DISCOUNT),
            'promo_base': str(promo_base or PROMO_BASE_ADJUSTED),
        }
    return {
        'enabled': True,
        'quick_reprice_mode': 'markup',
        'quick_markup_percent': float(markup or 0.0),
        'tax_percent': 0.0,
        'marketplace_fee_percent': float(fee or 0.0),
        'quick_fixed_addition': float(fixed or 0.0),
        'promo_discount_percent': float(promo or 0.0),
        'promo_action': str(promo_action or PROMO_ACTION_KEEP),
        'promo_base': str(promo_base or PROMO_BASE_ADJUSTED),
    }


def _render_promo_controls() -> tuple[str, float, str]:
    promo_action = st.selectbox(
        'O que fazer com Preco Promocional?',
        [PROMO_ACTION_KEEP, PROMO_ACTION_CLEAR, PROMO_ACTION_DISCOUNT],
        key=EASY_PRICE_PROMO_ACTION_KEY,
        help='Escolha se o sistema deve preservar, apagar ou recalcular a coluna promocional.',
    )
    promo = 0.0
    promo_base = PROMO_BASE_ADJUSTED
    if promo_action == PROMO_ACTION_DISCOUNT:
        c1, c2 = st.columns(2)
        promo = c1.number_input('Desconto promocional (%)', min_value=0.0, max_value=100.0, value=0.0, step=1.0, key=PRICE_CALCULATOR_PROMO_DISCOUNT_KEY)
        promo_base = c2.selectbox('Base do desconto', [PROMO_BASE_ADJUSTED, PROMO_BASE_ORIGINAL], key=EASY_PRICE_PROMO_BASE_KEY)
    elif promo_action == PROMO_ACTION_KEEP:
        st.caption('Preco Promocional será preservado como veio na origem/modelo.')
    else:
        st.caption('Preco Promocional será limpo no resultado final.')
    return promo_action, float(promo or 0.0), promo_base


def _preview_promo_value(sample: Decimal, sale: Decimal, promo: float, promo_action: str, promo_base: str) -> Decimal:
    if promo_action != PROMO_ACTION_DISCOUNT or promo <= 0:
        return Decimal('0')
    base = sample if promo_base == PROMO_BASE_ORIGINAL else sale
    return calc_easy_promo_price(base, promo)


def render_easy_price_calculator(source_df: pd.DataFrame | None = None) -> dict:
    st.markdown('#### Calculadora fácil')
    column, sample = _selected_column(source_df)
    if sample > 0:
        st.caption(f'Amostra da coluna escolhida: {money(sample)}')

    mode = st.radio('O que você quer fazer?', ['Reajuste simples', 'Preço mínimo real'], horizontal=False, key=EASY_PRICE_MODE_KEY)

    if mode == 'Reajuste simples':
        st.caption('Mais rápido: ajusta o preço atual e permite preservar, limpar ou recalcular o promocional.')
        markup = st.number_input('Ajustar preço em (%)', min_value=-99.0, max_value=1000.0, value=0.0, step=1.0, key=EASY_PRICE_MARKUP_KEY, help='Use positivo para aumentar e negativo para diminuir. Ex.: -20 reduz 20%.')
        promo_action, promo, promo_base = _render_promo_controls()
        c3, c4 = st.columns(2)
        fee = c3.number_input('Taxa extra (%)', min_value=0.0, value=0.0, step=0.5, key=EASY_PRICE_FEE_KEY)
        fixed = c4.number_input('Somar valor fixo (R$)', min_value=0.0, value=0.0, step=1.0, key=EASY_PRICE_FIXED_KEY)
        tax = 0.0
        profit = 0.0
    else:
        st.caption('Mais seguro: calcula preço para cobrir imposto, taxa, desconto promocional e lucro desejado.')
        c1, c2 = st.columns(2)
        tax = c1.number_input('Imposto (%)', min_value=0.0, value=0.0, step=0.5, key=EASY_PRICE_TAX_KEY)
        promo = c2.number_input('Desconto promocional (%)', min_value=0.0, max_value=100.0, value=0.0, step=1.0, key=PRICE_CALCULATOR_PROMO_DISCOUNT_KEY)
        c3, c4 = st.columns(2)
        profit = c3.number_input('Lucro líquido desejado (%)', min_value=0.0, value=0.0, step=1.0, key=EASY_PRICE_PROFIT_KEY)
        fee = c4.number_input('Taxa/marketplace (%)', min_value=0.0, value=0.0, step=0.5, key=EASY_PRICE_FEE_KEY)
        fixed = st.number_input('Somar valor fixo (R$)', min_value=0.0, value=0.0, step=1.0, key=EASY_PRICE_FIXED_KEY)
        markup = 0.0
        promo_action = PROMO_ACTION_DISCOUNT if float(promo or 0.0) > 0 else PROMO_ACTION_KEEP
        promo_base = PROMO_BASE_ADJUSTED

    config = _config(mode, markup, tax, fee, profit, fixed, promo, promo_action, promo_base)
    sale = calc_easy_sale_price(sample, config)
    promo_value = _preview_promo_value(sample, sale, promo, promo_action, promo_base)

    st.markdown('##### Resultado da amostra')
    st.success(f'Preço de venda: {money(sale)}')
    if promo_action == PROMO_ACTION_DISCOUNT and promo_value > 0:
        st.success(f'Preço promocional: {money(promo_value)}')
    elif promo_action == PROMO_ACTION_KEEP:
        st.info('Preço promocional: não será alterado.')
    elif promo_action == PROMO_ACTION_CLEAR:
        st.warning('Preço promocional: será limpo.')

    can_apply = bool(column and sale > 0)
    if st.button('✅ Aplicar preços na planilha', use_container_width=True, disabled=not can_apply, key='easy_price_apply_v1'):
        st.session_state[PRICE_CALCULATOR_CONFIG_KEY] = config
        st.session_state[GLOBAL_PRICE_CONFIG_KEY] = config
        st.session_state[PRICE_CALCULATOR_READY_KEY] = True
        st.session_state[GLOBAL_PRICE_READY_KEY] = True
        st.session_state['home_precificacao_inicial'] = True
        st.session_state['cadastro_preco_calculado_ativo'] = True
        st.success('Preços aplicados. Continue para o mapeamento.')
    elif not can_apply:
        st.warning('Escolha a coluna base e preencha uma regra de preço.')

    return config


__all__ = ['render_easy_price_calculator']
