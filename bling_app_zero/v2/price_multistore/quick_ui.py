from __future__ import annotations

from decimal import Decimal

import pandas as pd
import streamlit as st

from bling_app_zero.core.global_price_calculator import (
    AD_TYPES,
    GlobalPriceResult,
    build_input_from_values,
    calculate_global_price,
    money,
    percent,
    to_decimal,
)
from bling_app_zero.core.price_calculator_plugin import best_cost_column

PRICE_CALCULATOR_RESULT_KEY = 'price_calculator_last_result'
PRICE_CALCULATOR_CONFIG_KEY = 'price_calculator_last_config'
PRICE_CALCULATOR_READY_KEY = 'price_calculator_ready'
PRICE_CALCULATOR_CONTEXT_KEY = 'price_calculator_context'
PRICE_CALCULATOR_SOURCE_COST_COLUMN_KEY = 'price_calculator_source_cost_column'
PRICE_CALCULATOR_SAMPLE_SALE_PRICE_KEY = 'price_calculator_sample_sale_price'
PRICE_CALCULATOR_SAMPLE_PROMO_PRICE_KEY = 'price_calculator_sample_promo_price'
PRICE_CALCULATOR_SAMPLE_PROFIT_KEY = 'price_calculator_sample_profit'
PRICE_CALCULATOR_SAMPLE_MARGIN_KEY = 'price_calculator_sample_margin'
PRICE_CALCULATOR_PROMO_DISCOUNT_KEY = 'price_calculator_promo_discount_percent_v3'
PRICE_CALCULATOR_PROMO_DISCOUNT_STATE_KEY = 'price_calculator_promo_discount_percent_value'
PRICE_CALCULATOR_MODE_KEY = 'price_calculator_mode'
PRICE_CALCULATOR_MODE_WIDGET_KEY = 'price_calculator_mode_select'
PRICE_CALCULATOR_LEGACY_MODE_KEY = 'global_price_application_mode'

QUICK_MARKET_COST_WIDGET_KEY = 'quick_market_cost_v3'
QUICK_MARKET_HAS_CALCULATED_KEY = 'quick_market_has_calculated'

GLOBAL_PRICE_RESULT_KEY = 'global_price_calculator_last_result'
GLOBAL_PRICE_CONFIG_KEY = 'global_price_calculator_last_config'
GLOBAL_PRICE_READY_KEY = 'global_price_calculator_ready'
GLOBAL_PRICE_MODE_KEY = PRICE_CALCULATOR_LEGACY_MODE_KEY
GLOBAL_PRICE_WARNING_ACK_KEY = 'global_price_warning_acknowledged'
GLOBAL_PRICE_SOURCE_COST_COLUMN_KEY = 'global_price_source_cost_column'
GLOBAL_PRICE_WARNING_TEXT = 'Com planilha carregada, o sistema calcula o preço linha a linha pela coluna selecionada.'

CALCULATION_MODE_OPTIONS = ('Lucro nominal', 'Margem de contribuição', 'Preço fixo')
CALCULATION_MODE_MAP = {
    'Lucro nominal': 'nominal_profit',
    'Margem de contribuição': 'contribution_margin',
    'Preço fixo': 'fixed_sale_price',
}
CALCULATION_MODE_LABELS = {value: key for key, value in CALCULATION_MODE_MAP.items()}
ZERO = 0.0


def _promo_price(sale_price: Decimal, promo_discount_percent: Decimal) -> Decimal:
    if sale_price <= 0 or promo_discount_percent <= 0:
        return Decimal('0')
    return sale_price * (Decimal('1') - (promo_discount_percent / Decimal('100')))


def _has_source_data(source_df: pd.DataFrame | None) -> bool:
    return isinstance(source_df, pd.DataFrame) and not source_df.empty and len(source_df.columns) > 0


def _source_columns(source_df: pd.DataFrame | None) -> list[str]:
    if not _has_source_data(source_df):
        return []
    return [str(column) for column in source_df.columns]


def _first_valid_decimal_from_column(source_df: pd.DataFrame | None, column: str) -> Decimal:
    if not _has_source_data(source_df) or not column or column not in source_df.columns:
        return Decimal('0')
    for value in source_df[column].tolist():
        parsed = to_decimal(value)
        if parsed > 0:
            return parsed
    return Decimal('0')


def _result_from_state() -> GlobalPriceResult | None:
    result = st.session_state.get(PRICE_CALCULATOR_RESULT_KEY)
    if isinstance(result, GlobalPriceResult):
        return result
    legacy = st.session_state.get(GLOBAL_PRICE_RESULT_KEY)
    return legacy if isinstance(legacy, GlobalPriceResult) else None


def _normalize_calculation_mode(value: object, *, has_source: bool) -> str:
    text = str(value or '').strip()
    if text in CALCULATION_MODE_MAP:
        return CALCULATION_MODE_MAP[text]
    if text in CALCULATION_MODE_LABELS:
        return text
    return 'nominal_profit' if has_source else 'fixed_sale_price'


def _render_calculation_mode_selector(*, has_source: bool) -> str:
    default_mode = _normalize_calculation_mode(st.session_state.get(PRICE_CALCULATOR_MODE_KEY), has_source=has_source)
    default_label = CALCULATION_MODE_LABELS.get(default_mode, 'Lucro nominal' if has_source else 'Preço fixo')
    try:
        default_index = list(CALCULATION_MODE_OPTIONS).index(default_label)
    except ValueError:
        default_index = 0 if has_source else 2
    selected_label = st.selectbox('Modo de cálculo', CALCULATION_MODE_OPTIONS, index=default_index, key=PRICE_CALCULATOR_MODE_WIDGET_KEY)
    mode = CALCULATION_MODE_MAP[selected_label]
    st.session_state[PRICE_CALCULATOR_MODE_KEY] = mode
    return mode


def _render_source_cost_selector(source_df: pd.DataFrame | None) -> tuple[str, Decimal]:
    columns = _source_columns(source_df)
    if not columns:
        return '', Decimal('0')
    detected = best_cost_column(columns)
    selected_default = st.session_state.get(PRICE_CALCULATOR_SOURCE_COST_COLUMN_KEY) or st.session_state.get(GLOBAL_PRICE_SOURCE_COST_COLUMN_KEY) or detected
    if selected_default not in columns:
        selected_default = detected if detected in columns else columns[0]
    selected = st.selectbox('Coluna de custo', columns, index=columns.index(selected_default), key=PRICE_CALCULATOR_SOURCE_COST_COLUMN_KEY)
    st.session_state[GLOBAL_PRICE_SOURCE_COST_COLUMN_KEY] = selected
    sample_cost = _first_valid_decimal_from_column(source_df, selected)
    if selected and sample_cost > 0:
        st.caption(f'Custo detectado na origem: {money(sample_cost)}. Os campos da calculadora começam zerados.')
    return selected, sample_cost


def _sale_price_sample_label(*, has_source: bool, calculation_mode: str) -> str:
    if has_source and calculation_mode == 'fixed_sale_price':
        return 'Preço fixo'
    if has_source:
        return 'Preço da amostra'
    return 'Preço de venda'


def _save_global_result(result: GlobalPriceResult, *, has_source: bool, cost_column: str = '', calculation_mode: str = '', promo_discount_percent: Decimal = Decimal('0')) -> None:
    normalized_mode = _normalize_calculation_mode(calculation_mode, has_source=has_source)
    context = 'source_cost_line_by_line' if has_source and normalized_mode != 'fixed_sale_price' else 'source_fixed_price_all_rows' if has_source else 'standalone_simulation'
    promo = _promo_price(result.sale_price, promo_discount_percent)
    st.session_state[PRICE_CALCULATOR_RESULT_KEY] = result
    st.session_state[PRICE_CALCULATOR_READY_KEY] = True
    st.session_state[PRICE_CALCULATOR_CONTEXT_KEY] = context
    st.session_state[PRICE_CALCULATOR_MODE_KEY] = normalized_mode
    st.session_state[PRICE_CALCULATOR_PROMO_DISCOUNT_STATE_KEY] = float(promo_discount_percent)
    st.session_state[PRICE_CALCULATOR_SAMPLE_SALE_PRICE_KEY] = float(result.sale_price)
    st.session_state[PRICE_CALCULATOR_SAMPLE_PROMO_PRICE_KEY] = float(promo)
    st.session_state[PRICE_CALCULATOR_SAMPLE_PROFIT_KEY] = float(result.profit)
    st.session_state[PRICE_CALCULATOR_SAMPLE_MARGIN_KEY] = float(result.margin)
    st.session_state[GLOBAL_PRICE_RESULT_KEY] = result
    st.session_state[GLOBAL_PRICE_READY_KEY] = True
    st.session_state[GLOBAL_PRICE_MODE_KEY] = context
    st.session_state['global_price_calculator_sale_price'] = float(result.sale_price)
    st.session_state['global_price_calculator_promo_price'] = float(promo)
    st.session_state['global_price_calculator_promo_discount_percent'] = float(promo_discount_percent)
    st.session_state['global_price_calculator_profit'] = float(result.profit)
    st.session_state['global_price_calculator_margin'] = float(result.margin)
    st.session_state['preco_calculado_global'] = float(result.sale_price)
    st.session_state['preco_promocional_calculado_global'] = float(promo)
    st.session_state['preco_unitario_calculado'] = float(result.sale_price)
    st.session_state['preco_global_aplicado_em_todos_produtos'] = bool(has_source and normalized_mode == 'fixed_sale_price')
    st.session_state['preco_global_alerta_texto'] = GLOBAL_PRICE_WARNING_TEXT
    if cost_column:
        st.session_state[GLOBAL_PRICE_SOURCE_COST_COLUMN_KEY] = cost_column


def _current_promo_discount() -> Decimal:
    if PRICE_CALCULATOR_PROMO_DISCOUNT_KEY in st.session_state:
        return to_decimal(st.session_state.get(PRICE_CALCULATOR_PROMO_DISCOUNT_KEY, 0))
    return to_decimal(st.session_state.get(PRICE_CALCULATOR_PROMO_DISCOUNT_STATE_KEY, 0))


def _render_saved_result_notice() -> None:
    result = _result_from_state()
    if not isinstance(result, GlobalPriceResult):
        return
    promo = _promo_price(result.sale_price, _current_promo_discount())
    promo_text = f' · promocional {money(promo)}' if promo > 0 else ''
    st.info(f'Cálculo disponível: venda {money(result.sale_price)}{promo_text}')


def render_quick_price_calculator(*, embedded: bool = False, source_df: pd.DataFrame | None = None) -> None:
    has_source = _has_source_data(source_df)
    if not embedded:
        st.markdown('### Calculadora rápida de preço')
        st.caption('Calcule preço de venda, preço promocional, lucro e margem.')

    with st.container(border=True):
        st.markdown('#### Configurações de preço')
        selected_cost_column, detected_sample_cost = _render_source_cost_selector(source_df)
        calculation_mode = _render_calculation_mode_selector(has_source=has_source)
        if has_source and calculation_mode != 'fixed_sale_price':
            st.caption('A planilha será calculada linha a linha pela coluna de custo depois que você preencher os valores.')

        c_fee_1, c_fee_2 = st.columns(2)
        classic_fee = c_fee_1.number_input('Taxa Clássico (%)', min_value=0.0, value=ZERO, step=0.5, key='quick_market_classic_fee_v3')
        premium_fee = c_fee_2.number_input('Taxa Premium (%)', min_value=0.0, value=ZERO, step=0.5, key='quick_market_premium_fee_v3')

        c_base_1, c_base_2 = st.columns(2)
        ad_type = c_base_1.selectbox('Tipo de taxa', list(AD_TYPES), index=0, key='quick_market_ad_type')
        cost = c_base_2.number_input('Custo / amostra', min_value=0.0, value=ZERO, step=1.0, key=QUICK_MARKET_COST_WIDGET_KEY)

        c_price_1, c_price_2 = st.columns(2)
        sale_price = c_price_1.number_input(_sale_price_sample_label(has_source=has_source, calculation_mode=calculation_mode), min_value=0.0, value=ZERO, step=1.0, key='quick_market_sale_price_v3')
        tax_percent = c_price_2.number_input('Imposto (%)', min_value=0.0, value=ZERO, step=0.5, key='quick_market_tax_v3')

        c_cost_1, c_cost_2, c_cost_3 = st.columns(3)
        freight = c_cost_1.number_input('Frete (R$)', min_value=0.0, value=ZERO, step=1.0, key='quick_market_freight_v3')
        fixed_fee = c_cost_2.number_input('Taxa fixa (R$)', min_value=0.0, value=ZERO, step=0.5, key='quick_market_fixed_fee_v3')
        extra_cost = c_cost_3.number_input('Outros (R$)', min_value=0.0, value=ZERO, step=0.5, key='quick_market_extra_cost_v3')

        promo_default = float(st.session_state.get(PRICE_CALCULATOR_PROMO_DISCOUNT_STATE_KEY, ZERO) or ZERO)
        promo_discount = st.number_input('Desconto promocional (%)', min_value=0.0, max_value=100.0, value=promo_default, step=1.0, key=PRICE_CALCULATOR_PROMO_DISCOUNT_KEY)
        promo_discount_decimal = to_decimal(promo_discount)

        data = build_input_from_values(ad_type=ad_type, classic_fee_percent=classic_fee, premium_fee_percent=premium_fee, cost=cost, sale_price=sale_price, tax_percent=tax_percent, freight=freight, fixed_fee=fixed_fee, extra_cost=extra_cost)
        result = calculate_global_price(data)
        should_apply = bool(has_source and selected_cost_column and (to_decimal(cost) > 0 or to_decimal(sale_price) > 0))
        clicked = st.button('🧮 Recalcular e aplicar' if has_source else '🧮 Calcular simulação', use_container_width=True, key='quick_market_calculate')
        if clicked or should_apply:
            st.session_state[QUICK_MARKET_HAS_CALCULATED_KEY] = True
            st.session_state[PRICE_CALCULATOR_CONFIG_KEY] = data
            st.session_state[GLOBAL_PRICE_CONFIG_KEY] = data
            _save_global_result(result, has_source=has_source, cost_column=selected_cost_column, calculation_mode=calculation_mode, promo_discount_percent=promo_discount_decimal)

        if not st.session_state.get(QUICK_MARKET_HAS_CALCULATED_KEY):
            st.info('Preencha os valores e toque em Calcular.')
            _render_saved_result_notice()
            return

        _save_global_result(result, has_source=has_source, cost_column=selected_cost_column, calculation_mode=calculation_mode, promo_discount_percent=promo_discount_decimal)
        st.markdown('#### Resultado')
        st.success(f'Preço de venda: {money(result.sale_price)}')
        promo_value = _promo_price(result.sale_price, promo_discount_decimal)
        if promo_value > 0:
            st.success(f'Preço promocional: {money(promo_value)} (-{percent(promo_discount_decimal)})')
        st.caption(f'Taxa marketplace: {money(result.marketplace_fee)} ({percent(result.marketplace_fee_percent)}) · Imposto: {money(result.tax)} · Custo total: {money(result.total_cost)}')
        st.caption(f'Lucro líquido: {money(result.profit)} · Margem: {percent(result.margin)}')
        if to_decimal(sale_price) <= 0:
            st.warning('Informe o preço de venda para calcular lucro e margem.')
        elif has_source:
            st.success('Precificação pronta para seguir no fluxo com Preço de venda e Preço promocional.')


__all__ = [
    'CALCULATION_MODE_LABELS',
    'CALCULATION_MODE_MAP',
    'GLOBAL_PRICE_CONFIG_KEY',
    'GLOBAL_PRICE_MODE_KEY',
    'GLOBAL_PRICE_READY_KEY',
    'GLOBAL_PRICE_RESULT_KEY',
    'GLOBAL_PRICE_SOURCE_COST_COLUMN_KEY',
    'GLOBAL_PRICE_WARNING_ACK_KEY',
    'GLOBAL_PRICE_WARNING_TEXT',
    'PRICE_CALCULATOR_CONFIG_KEY',
    'PRICE_CALCULATOR_CONTEXT_KEY',
    'PRICE_CALCULATOR_MODE_KEY',
    'PRICE_CALCULATOR_PROMO_DISCOUNT_KEY',
    'PRICE_CALCULATOR_PROMO_DISCOUNT_STATE_KEY',
    'PRICE_CALCULATOR_READY_KEY',
    'PRICE_CALCULATOR_RESULT_KEY',
    'PRICE_CALCULATOR_SAMPLE_MARGIN_KEY',
    'PRICE_CALCULATOR_SAMPLE_PROFIT_KEY',
    'PRICE_CALCULATOR_SAMPLE_PROMO_PRICE_KEY',
    'PRICE_CALCULATOR_SAMPLE_SALE_PRICE_KEY',
    'PRICE_CALCULATOR_SOURCE_COST_COLUMN_KEY',
    'QUICK_MARKET_COST_WIDGET_KEY',
    'render_quick_price_calculator',
]
