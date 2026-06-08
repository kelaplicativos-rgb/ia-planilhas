from __future__ import annotations

from decimal import Decimal

import pandas as pd
import streamlit as st

from bling_app_zero.core.easy_reprice import calc_easy_promo_price, calc_easy_sale_price
from bling_app_zero.core.price_calculator_plugin import best_cost_column
from bling_app_zero.v2.marketplace_calculator import money
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


def _has_df(df: pd.DataFrame | None) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0


def _to_decimal(value) -> Decimal:
    text = str(value or '').replace('R$', '').replace('.', '').replace(',', '.').strip()
    try:
        return Decimal(text)
    except Exception:
        return Decimal('0')


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


def _config(mode: str, markup: float, tax: float, fee: float, profit: float, fixed: float, promo: float) -> dict:
    if mode == 'Preço mínimo real':
        return {
            'enabled': True,
            'quick_reprice_mode': 'net_margin',
            'quick_markup_percent': float(profit or 0.0),
            'tax_percent': float(tax or 0.0),
            'marketplace_fee_percent': float(fee or 0.0),
            'quick_fixed_addition': float(fixed or 0.0),
            'promo_discount_percent': float(promo or 0.0),
        }
    return {
        'enabled': True,
        'quick_reprice_mode': 'markup',
        'quick_markup_percent': float(markup or 0.0),
        'tax_percent': 0.0,
        'marketplace_fee_percent': float(fee or 0.0),
        'quick_fixed_addition': float(fixed or 0.0),
        'promo_discount_percent': float(promo or 0.0),
    }


def render_easy_price_calculator(source_df: pd.DataFrame | None = None) -> dict:
    st.markdown('#### Calculadora fácil')
    column, sample = _selected_column(source_df)
    if sample > 0:
        st.caption(f'Amostra da coluna escolhida: {money(sample)}')

    mode = st.radio('O que você quer fazer?', ['Reajuste simples', 'Preço mínimo real'], horizontal=False, key=EASY_PRICE_MODE_KEY)

    if mode == 'Reajuste simples':
        st.caption('Mais rápido: aumenta o preço atual e calcula o promocional. Não faz conta por dentro de imposto/lucro.')
        c1, c2 = st.columns(2)
        markup = c1.number_input('Aumentar preço em (%)', min_value=0.0, value=0.0, step=1.0, key=EASY_PRICE_MARKUP_KEY)
        promo = c2.number_input('Desconto promocional (%)', min_value=0.0, max_value=100.0, value=0.0, step=1.0, key=PRICE_CALCULATOR_PROMO_DISCOUNT_KEY)
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

    config = _config(mode, markup, tax, fee, profit, fixed, promo)
    sale = calc_easy_sale_price(sample, config)
    promo_value = calc_easy_promo_price(sale, promo)

    st.markdown('##### Resultado da amostra')
    st.success(f'Preço de venda: {money(sale)}')
    if promo_value > 0:
        st.success(f'Preço promocional: {money(promo_value)}')

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
