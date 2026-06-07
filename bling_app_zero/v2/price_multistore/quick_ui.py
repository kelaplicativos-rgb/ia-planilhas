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
PRICE_CALCULATOR_SAMPLE_PROFIT_KEY = 'price_calculator_sample_profit'
PRICE_CALCULATOR_SAMPLE_MARGIN_KEY = 'price_calculator_sample_margin'
PRICE_CALCULATOR_MODE_KEY = 'price_calculator_mode'
PRICE_CALCULATOR_MODE_WIDGET_KEY = 'price_calculator_mode_select'
PRICE_CALCULATOR_LEGACY_MODE_KEY = 'global_price_application_mode'

QUICK_MARKET_COST_WIDGET_KEY = 'quick_market_cost'
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


def _metric_card(label: str, value: str, extra: str = '') -> None:
    st.markdown(
        f'''
<div style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:16px;padding:1.05rem 1.15rem;margin:.35rem 0;">
  <div style="font-size:.9rem;color:#64748b;font-weight:900;letter-spacing:.01em;">{label}</div>
  <div style="font-size:1.55rem;color:#334155;font-weight:950;line-height:1.2;margin-top:.35rem;">{value} <span style="font-size:1rem;font-weight:700;color:#64748b;">{extra}</span></div>
</div>
''',
        unsafe_allow_html=True,
    )


def _primary_result_card(result: GlobalPriceResult, *, has_source: bool, calculation_mode: str, cost_column: str = '') -> None:
    mode_label = CALCULATION_MODE_LABELS.get(calculation_mode, calculation_mode or 'Não definido')
    if has_source and calculation_mode == 'nominal_profit':
        detail = f'Esta amostra definiu lucro de {money(result.profit)}. O próximo fluxo usa a coluna {cost_column or "selecionada"} e aplica o cálculo produto por produto.'
    elif has_source and calculation_mode == 'contribution_margin':
        detail = f'Esta amostra definiu margem de {percent(result.margin)}. O próximo fluxo usa a coluna {cost_column or "selecionada"} e aplica o cálculo produto por produto.'
    elif has_source:
        detail = 'Preço fixo: este valor será aplicado como referência para todos os produtos da origem.'
    else:
        detail = 'Simulação rápida sem origem: este é apenas o resultado da amostra informada manualmente.'
    st.markdown(
        f'''
<div style="background:#ecfdf5;border:1px solid #86efac;border-radius:20px;padding:1.2rem 1.25rem;margin:.8rem 0;color:#14532d;">
  <div style="font-size:.9rem;font-weight:950;letter-spacing:.02em;text-transform:uppercase;">Resultado principal da calculadora</div>
  <div style="font-size:2.05rem;font-weight:1000;line-height:1.15;margin:.35rem 0;">{money(result.sale_price)}</div>
  <div style="font-weight:850;margin-bottom:.35rem;">Preço de venda final da amostra · {mode_label}</div>
  <div style="line-height:1.5;">{detail}</div>
</div>
''',
        unsafe_allow_html=True,
    )


def _profit_card(profit: Decimal, margin: Decimal) -> None:
    color = '#22c55e' if profit >= 0 else '#ef4444'
    st.markdown(
        f'''
<div style="background:{color};border-radius:18px;padding:1.45rem 1rem;margin:.75rem 0;color:white;text-align:center;">
  <div style="font-size:1.08rem;font-weight:850;">Lucro Líquido da amostra</div>
  <div style="font-size:1.85rem;font-weight:950;margin:.35rem 0;">{money(profit)}</div>
  <div style="font-size:1rem;font-weight:650;">Margem da amostra: {percent(margin)}</div>
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
    st.markdown('#### Modo de cálculo')
    selected_label = st.selectbox('Como calcular o preço de venda?', CALCULATION_MODE_OPTIONS, index=default_index, key=PRICE_CALCULATOR_MODE_WIDGET_KEY)
    mode = CALCULATION_MODE_MAP[selected_label]
    st.session_state[PRICE_CALCULATOR_MODE_KEY] = mode
    if mode == 'nominal_profit':
        st.caption('A amostra define o lucro em R$. Depois, cada linha usa o custo da origem + esse lucro e as taxas.')
    elif mode == 'contribution_margin':
        st.caption('A amostra define a margem em %. Depois, cada linha usa o custo da origem e busca essa margem.')
    else:
        st.caption('Usa o preço de venda informado na amostra. Com origem, esse modo aplica o mesmo preço em todas as linhas.')
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
    st.markdown('#### Fonte de custo da planilha')
    st.caption('Escolha qual coluna da origem será usada como custo para calcular todos os produtos.')
    selected = st.selectbox('Coluna de custo detectada', columns, index=default_index, key=PRICE_CALCULATOR_SOURCE_COST_COLUMN_KEY)
    st.session_state[GLOBAL_PRICE_SOURCE_COST_COLUMN_KEY] = selected
    sample_cost = _first_valid_decimal_from_column(source_df, selected)
    if selected:
        st.success(f'Coluna de custo usada para cálculo linha a linha: {selected}')
    if sample_cost > 0:
        st.caption(f'Amostra enviada para a calculadora: {money(sample_cost)}')
    return selected, sample_cost


def _sync_cost_sample_widget(*, selected_cost_column: str, detected_sample_cost: Decimal) -> None:
    next_cost = float(detected_sample_cost) if detected_sample_cost > 0 else 65.0
    signature = f'{selected_cost_column}|{next_cost:.6f}'
    previous_signature = str(st.session_state.get(QUICK_MARKET_COST_SYNC_KEY, '') or '')
    if QUICK_MARKET_COST_WIDGET_KEY not in st.session_state:
        st.session_state[QUICK_MARKET_COST_WIDGET_KEY] = next_cost
        st.session_state[QUICK_MARKET_COST_SYNC_KEY] = signature
        return
    if signature != previous_signature:
        st.session_state[QUICK_MARKET_COST_WIDGET_KEY] = next_cost
        st.session_state[QUICK_MARKET_COST_SYNC_KEY] = signature


def _sale_price_sample_label(*, has_source: bool, calculation_mode: str) -> str:
    if has_source and calculation_mode == 'nominal_profit':
        return 'Preço de venda da amostra (define o lucro em R$)'
    if has_source and calculation_mode == 'contribution_margin':
        return 'Preço de venda da amostra (define a margem %)'
    if has_source:
        return 'Preço fixo para aplicar nos produtos (R$)'
    return 'Preço de venda desejado para cálculo rápido (R$)'


def _render_mode_notice(has_source: bool, calculation_mode: str) -> None:
    if has_source:
        extra = 'Este modo calcula linha a linha.' if calculation_mode != 'fixed_sale_price' else 'Atenção: preço fixo aplica o mesmo preço em todas as linhas.'
        st.markdown(
            f'''
<div style="background:#ecfdf5;border:1px solid #bbf7d0;border-radius:16px;padding:1rem 1.2rem;color:#14532d;margin:.8rem 0;">
  <div style="font-weight:950;margin-bottom:.4rem;">✅ Modo com origem de produtos</div>
  <div style="line-height:1.55;">A calculadora usa a coluna de custo da origem e grava o resultado em <b>Preço de venda</b>. {extra}</div>
</div>
''',
            unsafe_allow_html=True,
        )
        return
    st.markdown(
        f'''
<div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:16px;padding:1rem 1.2rem;color:#7c2d12;margin:.8rem 0;">
  <div style="font-weight:950;margin-bottom:.4rem;">⚠️ Cálculo rápido sem origem</div>
  <div style="line-height:1.55;">{GLOBAL_PRICE_WARNING_TEXT}</div>
</div>
''',
        unsafe_allow_html=True,
    )


def _render_observations(result: GlobalPriceResult, *, has_source: bool, cost_column: str = '', calculation_mode: str = '') -> None:
    mode_label = CALCULATION_MODE_LABELS.get(calculation_mode, calculation_mode or 'Não definido')
    source_text = f'Origem: coluna de custo <b>{cost_column}</b>. Resultado gerado na coluna <b>Preço de venda</b>.' if has_source and cost_column else 'Sem origem: resultado usado apenas como simulação rápida.'
    st.markdown(
        f'''
<div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:16px;padding:1rem 1.2rem;color:#334155;margin-top:.8rem;">
  <div style="font-weight:900;margin-bottom:.55rem;">Leitura da calculadora</div>
  <ul style="margin:.2rem 0 0 1.15rem;padding:0;line-height:1.65;">
    <li>Modo selecionado: <b>{mode_label}</b>.</li>
    <li>Tipo/taxa selecionado: <b>{result.ad_type}</b> · <b>{percent(result.marketplace_fee_percent)}</b>.</li>
    <li>{source_text}</li>
  </ul>
</div>
''',
        unsafe_allow_html=True,
    )


def _save_global_result(result: GlobalPriceResult, *, has_source: bool, cost_column: str = '', calculation_mode: str = '') -> None:
    normalized_mode = _normalize_calculation_mode(calculation_mode, has_source=has_source)
    context = 'source_cost_line_by_line' if has_source and normalized_mode != 'fixed_sale_price' else 'source_fixed_price_all_rows' if has_source else 'standalone_simulation'
    st.session_state[PRICE_CALCULATOR_RESULT_KEY] = result
    st.session_state[PRICE_CALCULATOR_READY_KEY] = True
    st.session_state[PRICE_CALCULATOR_CONTEXT_KEY] = context
    st.session_state[PRICE_CALCULATOR_MODE_KEY] = normalized_mode
    st.session_state[PRICE_CALCULATOR_SAMPLE_SALE_PRICE_KEY] = float(result.sale_price)
    st.session_state[PRICE_CALCULATOR_SAMPLE_PROFIT_KEY] = float(result.profit)
    st.session_state[PRICE_CALCULATOR_SAMPLE_MARGIN_KEY] = float(result.margin)
    st.session_state[GLOBAL_PRICE_RESULT_KEY] = result
    st.session_state[GLOBAL_PRICE_READY_KEY] = True
    st.session_state[GLOBAL_PRICE_MODE_KEY] = context
    st.session_state['global_price_calculator_sale_price'] = float(result.sale_price)
    st.session_state['global_price_calculator_profit'] = float(result.profit)
    st.session_state['global_price_calculator_margin'] = float(result.margin)
    st.session_state['preco_calculado_global'] = float(result.sale_price)
    st.session_state['preco_unitario_calculado'] = float(result.sale_price)
    st.session_state['preco_global_aplicado_em_todos_produtos'] = bool(has_source and normalized_mode == 'fixed_sale_price')
    st.session_state['preco_global_alerta_texto'] = GLOBAL_PRICE_WARNING_TEXT
    if cost_column:
        st.session_state[GLOBAL_PRICE_SOURCE_COST_COLUMN_KEY] = cost_column


def _render_saved_result_notice() -> None:
    result = _result_from_state()
    mode = str(_legacy_or_new_state(PRICE_CALCULATOR_CONTEXT_KEY, GLOBAL_PRICE_MODE_KEY, '') or '')
    if isinstance(result, GlobalPriceResult):
        if mode in {'source_cost_line_by_line', 'source_fixed_price_all_rows'}:
            cost_column = str(_legacy_or_new_state(PRICE_CALCULATOR_SOURCE_COST_COLUMN_KEY, GLOBAL_PRICE_SOURCE_COST_COLUMN_KEY, '') or '')
            st.success(f'Calculadora pronta usando a coluna {cost_column}: preço da amostra {money(result.sale_price)}')
        else:
            st.info(f'Cálculo rápido disponível: {money(result.sale_price)}')


def render_quick_price_calculator(*, embedded: bool = False, source_df: pd.DataFrame | None = None) -> None:
    has_source = _has_source_data(source_df)
    title = 'Calculadora única de preço' if embedded else 'Calculadora rápida de preço'
    st.markdown(f'### {title}')
    st.caption('Com origem, calcula todos os produtos usando a coluna de custo. Sem origem, funciona como cálculo rápido avulso.')

    with st.container(border=True):
        st.markdown('## Configurações')
        st.caption('Defina os parâmetros para o cálculo')
        selected_cost_column, detected_sample_cost = _render_source_cost_selector(source_df)
        _sync_cost_sample_widget(selected_cost_column=selected_cost_column, detected_sample_cost=detected_sample_cost)
        calculation_mode = _render_calculation_mode_selector(has_source=has_source)

        st.markdown('#### Taxas do marketplace')
        st.caption('Informe manualmente as porcentagens cobradas pelo canal, marketplace ou loja.')
        c_fee_1, c_fee_2 = st.columns(2)
        classic_fee = c_fee_1.number_input('Taxa Clássico (%)', min_value=0.0, value=11.5, step=0.5, key='quick_market_classic_fee')
        premium_fee = c_fee_2.number_input('Taxa Premium (%)', min_value=0.0, value=16.5, step=0.5, key='quick_market_premium_fee')
        ad_type = st.selectbox('Tipo de taxa / anúncio', list(AD_TYPES), index=0, key='quick_market_ad_type')
        cost = st.number_input('Custo do Produto / Amostra', min_value=0.0, step=1.0, key=QUICK_MARKET_COST_WIDGET_KEY)
        sale_price = st.number_input(_sale_price_sample_label(has_source=has_source, calculation_mode=calculation_mode), min_value=0.0, value=130.0, step=1.0, key='quick_market_sale_price')
        tax_percent = st.number_input('Imposto (%)', min_value=0.0, value=6.0, step=0.5, key='quick_market_tax')
        freight = st.number_input('Custo do Frete (R$)', min_value=0.0, value=0.0, step=1.0, key='quick_market_freight')
        fixed_fee = st.number_input('Taxa Fixa (R$)', min_value=0.0, value=0.0, step=0.5, key='quick_market_fixed_fee')
        extra_cost = st.number_input('Outros Custos (R$)', min_value=0.0, value=0.0, step=0.5, key='quick_market_extra_cost')
        _render_mode_notice(has_source, calculation_mode)

        data = build_input_from_values(ad_type=ad_type, classic_fee_percent=classic_fee, premium_fee_percent=premium_fee, cost=cost, sale_price=sale_price, tax_percent=tax_percent, freight=freight, fixed_fee=fixed_fee, extra_cost=extra_cost)
        result = calculate_global_price(data)
        auto_apply_source_calculation = bool(has_source and selected_cost_column)
        button_label = '🧮 Recalcular e aplicar' if has_source else '🧮 Calcular simulação avulsa'
        clicked = st.button(button_label, use_container_width=True, key='quick_market_calculate')
        if clicked or auto_apply_source_calculation:
            st.session_state[QUICK_MARKET_HAS_CALCULATED_KEY] = True
            st.session_state[PRICE_CALCULATOR_CONFIG_KEY] = data
            st.session_state[GLOBAL_PRICE_CONFIG_KEY] = data
            _save_global_result(result, has_source=has_source, cost_column=selected_cost_column, calculation_mode=calculation_mode)

        if not st.session_state.get(QUICK_MARKET_HAS_CALCULATED_KEY):
            st.info('Preencha os valores e toque em Calcular para ver a simulação.')
            _render_saved_result_notice()
            return

        st.session_state[PRICE_CALCULATOR_CONFIG_KEY] = data
        st.session_state[GLOBAL_PRICE_CONFIG_KEY] = data
        _save_global_result(result, has_source=has_source, cost_column=selected_cost_column, calculation_mode=calculation_mode)
        st.markdown('## Resultado da Precificação')
        _primary_result_card(result, has_source=has_source, calculation_mode=calculation_mode, cost_column=selected_cost_column)
        _metric_card('Taxa Marketplace', money(result.marketplace_fee), f'({percent(result.marketplace_fee_percent)})')
        _metric_card('Taxa Fixa', money(result.fixed_fee))
        _metric_card('Frete', money(result.freight))
        _metric_card('Imposto', money(result.tax))
        _metric_card('Outros Custos', money(result.extra_cost))
        _metric_card('Custo Total da amostra', money(result.total_cost))
        _profit_card(result.profit, result.margin)
        _render_observations(result, has_source=has_source, cost_column=selected_cost_column, calculation_mode=calculation_mode)

        if to_decimal(sale_price) <= 0:
            st.warning('Informe o preço de venda da amostra para calcular lucro e margem.')
        elif result.profit < 0 and calculation_mode != 'fixed_sale_price':
            st.warning('Atenção: o lucro líquido ficou negativo. Revise custo, preço, frete, imposto ou taxas.')
        elif has_source:
            st.success('Precificação pronta. O resultado será gravado como Preço de venda e seguirá para o próximo fluxo.')
        else:
            st.success('Cálculo rápido concluído. Sem origem carregada, o resultado fica apenas como simulação avulsa.')


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
    'PRICE_CALCULATOR_READY_KEY',
    'PRICE_CALCULATOR_RESULT_KEY',
    'PRICE_CALCULATOR_SAMPLE_MARGIN_KEY',
    'PRICE_CALCULATOR_SAMPLE_PROFIT_KEY',
    'PRICE_CALCULATOR_SAMPLE_SALE_PRICE_KEY',
    'PRICE_CALCULATOR_SOURCE_COST_COLUMN_KEY',
    'QUICK_MARKET_COST_WIDGET_KEY',
    'render_quick_price_calculator',
]
