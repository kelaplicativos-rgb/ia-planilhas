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
PRICE_CALCULATOR_PROMO_DISCOUNT_KEY = 'price_calculator_promo_discount_percent_v2_zero_default'
PRICE_CALCULATOR_PROMO_DISCOUNT_STATE_KEY = 'price_calculator_promo_discount_percent_value'
PRICE_CALCULATOR_MODE_KEY = 'price_calculator_mode'
PRICE_CALCULATOR_MODE_WIDGET_KEY = 'price_calculator_mode_select'
PRICE_CALCULATOR_LEGACY_MODE_KEY = 'global_price_application_mode'

QUICK_MARKET_COST_WIDGET_KEY = 'quick_market_cost_v2_zero_default'
QUICK_MARKET_COST_SYNC_KEY = 'quick_market_cost_source_sync_signature'
QUICK_MARKET_HAS_CALCULATED_KEY = 'quick_market_has_calculated'

GLOBAL_PRICE_RESULT_KEY = 'global_price_calculator_last_result'
GLOBAL_PRICE_CONFIG_KEY = 'global_price_calculator_last_config'
GLOBAL_PRICE_READY_KEY = 'global_price_calculator_ready'
GLOBAL_PRICE_MODE_KEY = PRICE_CALCULATOR_LEGACY_MODE_KEY
GLOBAL_PRICE_WARNING_ACK_KEY = 'global_price_warning_acknowledged'
GLOBAL_PRICE_SOURCE_COST_COLUMN_KEY = 'global_price_source_cost_column'
GLOBAL_PRICE_WARNING_TEXT = (
    'Atenção: sem fonte de dados, este cálculo funciona apenas como simulação avulsa. '
    'Com planilha carregada, o sistema usa a coluna de custo detectada/selecionada e calcula o preço linha a linha.'
)

CALCULATION_MODE_OPTIONS = ('Lucro nominal', 'Margem de contribuição', 'Preço fixo')
CALCULATION_MODE_MAP = {
    'Lucro nominal': 'nominal_profit',
    'Margem de contribuição': 'contribution_margin',
    'Preço fixo': 'fixed_sale_price',
}
CALCULATION_MODE_LABELS = {value: key for key, value in CALCULATION_MODE_MAP.items()}
ZERO = 0.0


def _metric_card(label: str, value: str, extra: str = '') -> None:
    st.markdown(
        f'''
<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;padding:.78rem .9rem;margin:.25rem 0;">
  <div style="font-size:.82rem;color:#64748b;font-weight:850;letter-spacing:.01em;">{label}</div>
  <div style="font-size:1.22rem;color:#334155;font-weight:950;line-height:1.18;margin-top:.25rem;">{value} <span style="font-size:.9rem;font-weight:700;color:#64748b;">{extra}</span></div>
</div>
''',
        unsafe_allow_html=True,
    )


def _promo_price(sale_price: Decimal, promo_discount_percent: Decimal) -> Decimal:
    if sale_price <= 0 or promo_discount_percent <= 0:
        return Decimal('0')
    return sale_price * (Decimal('1') - (promo_discount_percent / Decimal('100')))


def _primary_result_card(
    result: GlobalPriceResult,
    *,
    has_source: bool,
    calculation_mode: str,
    cost_column: str = '',
    promo_discount_percent: Decimal = Decimal('0'),
) -> None:
    mode_label = CALCULATION_MODE_LABELS.get(calculation_mode, calculation_mode or 'Não definido')
    if has_source and calculation_mode == 'nominal_profit':
        detail = f'Linha a linha pela coluna {cost_column or "selecionada"}.'
    elif has_source and calculation_mode == 'contribution_margin':
        detail = f'Margem aplicada linha a linha pela coluna {cost_column or "selecionada"}.'
    elif has_source:
        detail = 'Mesmo preço aplicado em todos os produtos.'
    else:
        detail = 'Simulação avulsa, sem planilha carregada.'
    promo = _promo_price(result.sale_price, promo_discount_percent)
    promo_html = ''
    if promo > 0:
        promo_html = f'<div style="font-size:1.1rem;font-weight:950;margin-top:.38rem;">Preço promocional: {money(promo)} <span style="font-size:.85rem;font-weight:800;">(-{percent(promo_discount_percent)})</span></div>'
    st.markdown(
        f'''
<div style="background:#ecfdf5;border:1px solid #86efac;border-radius:18px;padding:1rem 1.05rem;margin:.7rem 0;color:#14532d;">
  <div style="font-size:.84rem;font-weight:950;letter-spacing:.02em;text-transform:uppercase;">Preço calculado para venda</div>
  <div style="font-size:1.78rem;font-weight:1000;line-height:1.1;margin:.25rem 0;">{money(result.sale_price)}</div>
  {promo_html}
  <div style="font-weight:800;line-height:1.35;margin-top:.35rem;">{mode_label} · {detail}</div>
</div>
''',
        unsafe_allow_html=True,
    )


def _profit_card(profit: Decimal, margin: Decimal) -> None:
    color = '#22c55e' if profit >= 0 else '#ef4444'
    st.markdown(
        f'''
<div style="background:{color};border-radius:16px;padding:1rem .9rem;margin:.55rem 0;color:white;text-align:center;">
  <div style="font-size:.95rem;font-weight:850;">Lucro líquido da amostra</div>
  <div style="font-size:1.45rem;font-weight:950;margin:.22rem 0;">{money(profit)}</div>
  <div style="font-size:.92rem;font-weight:650;">Margem: {percent(margin)}</div>
</div>
''',
        unsafe_allow_html=True,
    )


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


def _legacy_or_new_state(new_key: str, legacy_key: str = '', default: object = '') -> object:
    if new_key in st.session_state:
        return st.session_state.get(new_key, default)
    if legacy_key and legacy_key in st.session_state:
        return st.session_state.get(legacy_key, default)
    return default


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
    if not has_source:
        return 'fixed_sale_price'
    return 'nominal_profit'


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
    existing = str(_legacy_or_new_state(PRICE_CALCULATOR_SOURCE_COST_COLUMN_KEY, GLOBAL_PRICE_SOURCE_COST_COLUMN_KEY, detected) or '')
    selected_default = existing if existing in columns else detected
    try:
        default_index = columns.index(selected_default) if selected_default in columns else 0
    except Exception:
        default_index = 0
    selected = st.selectbox('Coluna de custo', columns, index=default_index, key=PRICE_CALCULATOR_SOURCE_COST_COLUMN_KEY)
    st.session_state[GLOBAL_PRICE_SOURCE_COST_COLUMN_KEY] = selected
    sample_cost = _first_valid_decimal_from_column(source_df, selected)
    if selected and sample_cost > 0:
        st.caption(f'Custo detectado na origem: {money(sample_cost)}. O campo Custo / amostra começa zerado para você decidir quando aplicar.')
    return selected, sample_cost


def _sync_cost_sample_widget(*, selected_cost_column: str, detected_sample_cost: Decimal) -> None:
    """Mantém o campo de custo zerado ao abrir a calculadora.

    Antes o sistema preenchia automaticamente o custo/amostra com o primeiro valor
    detectado na origem, como 56,00. Isso confundia o usuário porque parecia que a
    calculadora já estava configurada. Agora o valor detectado aparece só como
    legenda, e o input nasce 0,00.
    """
    if QUICK_MARKET_COST_WIDGET_KEY not in st.session_state:
        st.session_state[QUICK_MARKET_COST_WIDGET_KEY] = ZERO
    st.session_state[QUICK_MARKET_COST_SYNC_KEY] = f'{selected_cost_column}|zero-default'


def _sale_price_sample_label(*, has_source: bool, calculation_mode: str) -> str:
    if has_source and calculation_mode == 'nominal_profit':
        return 'Preço da amostra'
    if has_source and calculation_mode == 'contribution_margin':
        return 'Preço da amostra'
    if has_source:
        return 'Preço fixo'
    return 'Preço de venda'


def _render_mode_notice(has_source: bool, calculation_mode: str) -> None:
    if has_source and calculation_mode == 'fixed_sale_price':
        st.warning('Preço fixo aplica o mesmo valor em todos os produtos. Confira se nenhum custo é maior que o preço.')
    elif has_source:
        st.caption('A planilha será calculada linha a linha pela coluna de custo somente depois que você preencher os valores da calculadora.')
    else:
        st.caption('Sem planilha, este cálculo funciona apenas como simulação avulsa.')


def _render_observations(result: GlobalPriceResult, *, has_source: bool, cost_column: str = '', calculation_mode: str = '') -> None:
    mode_label = CALCULATION_MODE_LABELS.get(calculation_mode, calculation_mode or 'Não definido')
    source_text = f'Origem: {cost_column}. Resultado: Preço de venda + Preço promocional.' if has_source and cost_column else 'Sem origem: simulação avulsa.'
    st.caption(f'{mode_label} · {result.ad_type} · {percent(result.marketplace_fee_percent)} · {source_text}')


def _save_global_result(
    result: GlobalPriceResult,
    *,
    has_source: bool,
    cost_column: str = '',
    calculation_mode: str = '',
    promo_discount_percent: Decimal = Decimal('0'),
) -> None:
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
    mode = str(_legacy_or_new_state(PRICE_CALCULATOR_CONTEXT_KEY, GLOBAL_PRICE_MODE_KEY, '') or '')
    promo_discount = _current_promo_discount()
    if isinstance(result, GlobalPriceResult):
        promo = _promo_price(result.sale_price, promo_discount)
        promo_text = f' · promocional {money(promo)}' if promo > 0 else ''
        if mode in {'source_cost_line_by_line', 'source_fixed_price_all_rows'}:
            cost_column = str(_legacy_or_new_state(PRICE_CALCULATOR_SOURCE_COST_COLUMN_KEY, GLOBAL_PRICE_SOURCE_COST_COLUMN_KEY, '') or '')
            st.success(f'Calculadora pronta usando {cost_column}: venda {money(result.sale_price)}{promo_text}')
        else:
            st.info(f'Cálculo rápido disponível: venda {money(result.sale_price)}{promo_text}')


def render_quick_price_calculator(*, embedded: bool = False, source_df: pd.DataFrame | None = None) -> None:
    has_source = _has_source_data(source_df)
    if not embedded:
        st.markdown('### Calculadora rápida de preço')
        st.caption('Calcule preço de venda, preço promocional, lucro e margem em uma tela simples.')

    with st.container(border=True):
        st.markdown('#### Configurações de preço')
        selected_cost_column, detected_sample_cost = _render_source_cost_selector(source_df)
        _sync_cost_sample_widget(selected_cost_column=selected_cost_column, detected_sample_cost=detected_sample_cost)
        calculation_mode = _render_calculation_mode_selector(has_source=has_source)
        _render_mode_notice(has_source, calculation_mode)

        c_fee_1, c_fee_2 = st.columns(2)
        classic_fee = c_fee_1.number_input('Taxa Clássico (%)', min_value=0.0, value=ZERO, step=0.5, key='quick_market_classic_fee_v2_zero_default')
        premium_fee = c_fee_2.number_input('Taxa Premium (%)', min_value=0.0, value=ZERO, step=0.5, key='quick_market_premium_fee_v2_zero_default')

        c_base_1, c_base_2 = st.columns(2)
        ad_type = c_base_1.selectbox('Tipo de taxa', list(AD_TYPES), index=0, key='quick_market_ad_type')
        cost = c_base_2.number_input('Custo / amostra', min_value=0.0, value=ZERO, step=1.0, key=QUICK_MARKET_COST_WIDGET_KEY)

        c_price_1, c_price_2 = st.columns(2)
        sale_price = c_price_1.number_input(_sale_price_sample_label(has_source=has_source, calculation_mode=calculation_mode), min_value=0.0, value=ZERO, step=1.0, key='quick_market_sale_price_v2_zero_default')
        tax_percent = c_price_2.number_input('Imposto (%)', min_value=0.0, value=ZERO, step=0.5, key='quick_market_tax_v2_zero_default')

        c_cost_1, c_cost_2, c_cost_3 = st.columns(3)
        freight = c_cost_1.number_input('Frete (R$)', min_value=0.0, value=ZERO, step=1.0, key='quick_market_freight_v2_zero_default')
        fixed_fee = c_cost_2.number_input('Taxa fixa (R$)', min_value=0.0, value=ZERO, step=0.5, key='quick_market_fixed_fee_v2_zero_default')
        extra_cost = c_cost_3.number_input('Outros (R$)', min_value=0.0, value=ZERO, step=0.5, key='quick_market_extra_cost_v2_zero_default')

        promo_default = float(st.session_state.get(PRICE_CALCULATOR_PROMO_DISCOUNT_STATE_KEY, ZERO) or ZERO)
        promo_discount = st.number_input('Desconto promocional (%)', min_value=0.0, max_value=100.0, value=promo_default, step=1.0, key=PRICE_CALCULATOR_PROMO_DISCOUNT_KEY)
        promo_discount_decimal = to_decimal(promo_discount)

        data = build_input_from_values(ad_type=ad_type, classic_fee_percent=classic_fee, premium_fee_percent=premium_fee, cost=cost, sale_price=sale_price, tax_percent=tax_percent, freight=freight, fixed_fee=fixed_fee, extra_cost=extra_cost)
        result = calculate_global_price(data)
        auto_apply_source_calculation = bool(has_source and selected_cost_column and (to_decimal(cost) > 0 or to_decimal(sale_price) > 0))
        button_label = '🧮 Recalcular e aplicar' if has_source else '🧮 Calcular simulação'
        clicked = st.button(button_label, use_container_width=True, key='quick_market_calculate')
        if clicked or auto_apply_source_calculation:
            st.session_state[QUICK_MARKET_HAS_CALCULATED_KEY] = True
            st.session_state[PRICE_CALCULATOR_CONFIG_KEY] = data
            st.session_state[GLOBAL_PRICE_CONFIG_KEY] = data
            _save_global_result(result, has_source=has_source, cost_column=selected_cost_column, calculation_mode=calculation_mode, promo_discount_percent=promo_discount_decimal)

        if not st.session_state.get(QUICK_MARKET_HAS_CALCULATED_KEY):
            st.info('Preencha os valores e toque em Calcular.')
            _render_saved_result_notice()
            return

        st.session_state[PRICE_CALCULATOR_CONFIG_KEY] = data
        st.session_state[GLOBAL_PRICE_CONFIG_KEY] = data
        _save_global_result(result, has_source=has_source, cost_column=selected_cost_column, calculation_mode=calculation_mode, promo_discount_percent=promo_discount_decimal)
        st.markdown('#### Resultado')
        _primary_result_card(result, has_source=has_source, calculation_mode=calculation_mode, cost_column=selected_cost_column, promo_discount_percent=promo_discount_decimal)

        c_result_1, c_result_2 = st.columns(2)
        with c_result_1:
            _metric_card('Taxa marketplace', money(result.marketplace_fee), f'({percent(result.marketplace_fee_percent)})')
            _metric_card('Imposto', money(result.tax))
            _metric_card('Custo total', money(result.total_cost))
        with c_result_2:
            _metric_card('Taxa fixa', money(result.fixed_fee))
            _metric_card('Frete', money(result.freight))
            _metric_card('Outros custos', money(result.extra_cost))
            promo_value = _promo_price(result.sale_price, promo_discount_decimal)
            if promo_value > 0:
                _metric_card('Preço promocional', money(promo_value), f'(-{percent(promo_discount_decimal)})')

        _profit_card(result.profit, result.margin)
        _render_observations(result, has_source=has_source, cost_column=selected_cost_column, calculation_mode=calculation_mode)

        sale_price_decimal = to_decimal(sale_price)
        if has_source and calculation_mode == 'fixed_sale_price' and selected_cost_column:
            try:
                cost_series = source_df[selected_cost_column].apply(to_decimal)
                max_cost = cost_series.max()
            except Exception:
                max_cost = detected_sample_cost
            if sale_price_decimal <= to_decimal(detected_sample_cost) and sale_price_decimal > 0:
                st.warning('Preço fixo é igual ou inferior ao custo da amostra; isso resultará em prejuízo.')
            elif sale_price_decimal < max_cost and sale_price_decimal > 0:
                st.warning(f'O preço fixo informado ({money(sale_price_decimal)}) é inferior ao custo máximo ({money(max_cost)}). Alguns produtos terão prejuízo.')

        if sale_price_decimal <= 0:
            st.warning('Informe o preço de venda para calcular lucro e margem.')
        elif result.profit < 0 and calculation_mode != 'fixed_sale_price':
            st.warning('Lucro líquido negativo. Revise custo, preço, frete, imposto ou taxas.')
        elif has_source:
            st.success('Precificação pronta para seguir no fluxo com Preço de venda e Preço promocional.')
        else:
            st.success('Cálculo concluído.')


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
