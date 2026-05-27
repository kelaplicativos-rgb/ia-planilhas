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

GLOBAL_PRICE_RESULT_KEY = 'global_price_calculator_last_result'
GLOBAL_PRICE_CONFIG_KEY = 'global_price_calculator_last_config'
GLOBAL_PRICE_READY_KEY = 'global_price_calculator_ready'
GLOBAL_PRICE_MODE_KEY = 'global_price_application_mode'
GLOBAL_PRICE_WARNING_ACK_KEY = 'global_price_warning_acknowledged'
GLOBAL_PRICE_SOURCE_COST_COLUMN_KEY = 'global_price_source_cost_column'
GLOBAL_PRICE_WARNING_TEXT = (
    'Atenção: sem fonte de dados, este cálculo funciona apenas como simulação avulsa. '
    'Com planilha carregada, o sistema usa a coluna de custo detectada/selecionada e calcula o preço linha a linha.'
)


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


def _profit_card(profit: Decimal, margin: Decimal) -> None:
    color = '#22c55e' if profit >= 0 else '#ef4444'
    st.markdown(
        f'''
<div style="background:{color};border-radius:18px;padding:1.45rem 1rem;margin:.75rem 0;color:white;text-align:center;">
  <div style="font-size:1.08rem;font-weight:850;">Lucro Líquido</div>
  <div style="font-size:1.85rem;font-weight:950;margin:.35rem 0;">{money(profit)}</div>
  <div style="font-size:1rem;font-weight:650;">Margem de Lucro: {percent(margin)}</div>
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


def _render_source_cost_selector(source_df: pd.DataFrame | None) -> tuple[str, Decimal]:
    columns = _source_columns(source_df)
    if not columns:
        return '', Decimal('0')
    detected = best_cost_column(columns)
    try:
        default_index = columns.index(detected) if detected in columns else 0
    except Exception:
        default_index = 0
    st.markdown('#### Fonte de custo da planilha')
    st.caption('O sistema tenta localizar automaticamente a coluna de custo da planilha fornecedora. Você pode trocar se quiser.')
    selected = st.selectbox('Coluna de custo detectada', columns, index=default_index, key=GLOBAL_PRICE_SOURCE_COST_COLUMN_KEY)
    sample_cost = _first_valid_decimal_from_column(source_df, selected)
    if selected:
        st.success(f'Coluna de custo usada para cálculo linha a linha: {selected}')
    if sample_cost > 0:
        st.caption(f'Amostra usada para simular na tela: {money(sample_cost)}')
    return selected, sample_cost


def _render_mode_notice(has_source: bool) -> None:
    if has_source:
        st.markdown(
            '''
<div style="background:#ecfdf5;border:1px solid #bbf7d0;border-radius:16px;padding:1rem 1.2rem;color:#14532d;margin:.8rem 0;">
  <div style="font-weight:950;margin-bottom:.4rem;">✅ Modo com fonte de dados</div>
  <div style="line-height:1.55;">A calculadora usa a coluna de custo da planilha e grava o resultado em <b>Preço de venda</b> para todas as linhas calculadas.</div>
</div>
''',
            unsafe_allow_html=True,
        )
        return
    st.markdown(
        f'''
<div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:16px;padding:1rem 1.2rem;color:#7c2d12;margin:.8rem 0;">
  <div style="font-weight:950;margin-bottom:.4rem;">⚠️ Simulação sem fonte de dados</div>
  <div style="line-height:1.55;">{GLOBAL_PRICE_WARNING_TEXT}</div>
</div>
''',
        unsafe_allow_html=True,
    )


def _render_observations(result: GlobalPriceResult, *, has_source: bool, cost_column: str = '') -> None:
    source_text = (
        f'Com planilha, será usada a coluna de custo <b>{cost_column}</b> e o preço será calculado linha a linha.'
        if has_source and cost_column
        else 'Sem planilha, o resultado é apenas uma simulação avulsa exibida nesta tela.'
    )
    st.markdown(
        f'''
<div style="background:#dbeafe;border:1px solid #bfdbfe;border-radius:16px;padding:1rem 1.2rem;color:#1e3a5f;margin-top:.8rem;">
  <div style="font-weight:900;margin-bottom:.55rem;">Observações:</div>
  <ul style="margin:.2rem 0 0 1.15rem;padding:0;line-height:1.65;">
    <li>Tipo selecionado: <b>{result.ad_type}</b>.</li>
    <li>Taxa informada para este cálculo: <b>{percent(result.marketplace_fee_percent)}</b>.</li>
    <li>{source_text}</li>
  </ul>
</div>
''',
        unsafe_allow_html=True,
    )


def _save_global_result(result: GlobalPriceResult, *, has_source: bool, cost_column: str = '') -> None:
    st.session_state[GLOBAL_PRICE_RESULT_KEY] = result
    st.session_state[GLOBAL_PRICE_READY_KEY] = True
    st.session_state[GLOBAL_PRICE_MODE_KEY] = 'source_cost_line_by_line' if has_source else 'standalone_simulation'
    st.session_state['global_price_calculator_sale_price'] = float(result.sale_price)
    st.session_state['global_price_calculator_profit'] = float(result.profit)
    st.session_state['global_price_calculator_margin'] = float(result.margin)
    st.session_state['preco_calculado_global'] = float(result.sale_price)
    st.session_state['preco_unitario_calculado'] = float(result.sale_price)
    st.session_state['preco_global_aplicado_em_todos_produtos'] = False
    st.session_state['preco_global_alerta_texto'] = GLOBAL_PRICE_WARNING_TEXT
    if cost_column:
        st.session_state[GLOBAL_PRICE_SOURCE_COST_COLUMN_KEY] = cost_column


def _render_saved_result_notice() -> None:
    result = st.session_state.get(GLOBAL_PRICE_RESULT_KEY)
    mode = str(st.session_state.get(GLOBAL_PRICE_MODE_KEY) or '')
    if isinstance(result, GlobalPriceResult):
        if mode == 'source_cost_line_by_line':
            cost_column = str(st.session_state.get(GLOBAL_PRICE_SOURCE_COST_COLUMN_KEY) or '')
            st.success(f'Calculadora pronta para aplicar linha a linha usando a coluna {cost_column}: amostra {money(result.sale_price)}')
        else:
            st.info(f'Simulação avulsa disponível na tela: {money(result.sale_price)}')


def render_quick_price_calculator(*, embedded: bool = False, source_df: pd.DataFrame | None = None) -> None:
    has_source = _has_source_data(source_df)
    title = 'Calculadora única de preço' if embedded else 'Calculadora rápida de preço'
    st.markdown(f'### {title}')
    st.caption('Com planilha, calcula preço por linha usando a coluna de custo. Sem planilha, funciona como simulação avulsa.')

    with st.container(border=True):
        st.markdown('## Configurações')
        st.caption('Defina os parâmetros para o cálculo')

        selected_cost_column, detected_sample_cost = _render_source_cost_selector(source_df)

        st.markdown('#### Taxas do marketplace')
        st.caption('Informe manualmente as porcentagens cobradas pelo canal, marketplace ou loja.')
        c_fee_1, c_fee_2 = st.columns(2)
        classic_fee = c_fee_1.number_input('Taxa Clássico (%)', min_value=0.0, value=11.5, step=0.5, key='quick_market_classic_fee')
        premium_fee = c_fee_2.number_input('Taxa Premium (%)', min_value=0.0, value=16.5, step=0.5, key='quick_market_premium_fee')

        ad_type = st.selectbox('Tipo de taxa / anúncio', list(AD_TYPES), index=0, key='quick_market_ad_type')
        default_cost = float(detected_sample_cost) if detected_sample_cost > 0 else 65.0
        cost = st.number_input('Custo do Produto / Amostra', min_value=0.0, value=default_cost, step=1.0, key='quick_market_cost')
        sale_price = st.number_input('Preço de Venda desejado para a amostra (R$)', min_value=0.0, value=130.0, step=1.0, key='quick_market_sale_price')
        tax_percent = st.number_input('Imposto (%)', min_value=0.0, value=6.0, step=0.5, key='quick_market_tax')
        freight = st.number_input('Custo do Frete (R$)', min_value=0.0, value=0.0, step=1.0, key='quick_market_freight')
        fixed_fee = st.number_input('Taxa Fixa (R$)', min_value=0.0, value=0.0, step=0.5, key='quick_market_fixed_fee')
        extra_cost = st.number_input('Outros Custos (R$)', min_value=0.0, value=0.0, step=0.5, key='quick_market_extra_cost')

        _render_mode_notice(has_source)

        data = build_input_from_values(
            ad_type=ad_type,
            classic_fee_percent=classic_fee,
            premium_fee_percent=premium_fee,
            cost=cost,
            sale_price=sale_price,
            tax_percent=tax_percent,
            freight=freight,
            fixed_fee=fixed_fee,
            extra_cost=extra_cost,
        )
        result = calculate_global_price(data)

        button_label = '🧮 Calcular e aplicar linha a linha' if has_source else '🧮 Calcular simulação avulsa'
        clicked = st.button(button_label, use_container_width=True, key='quick_market_calculate')
        if clicked:
            st.session_state['quick_market_has_calculated'] = True
            st.session_state[GLOBAL_PRICE_CONFIG_KEY] = data
            _save_global_result(result, has_source=has_source, cost_column=selected_cost_column)

        if not st.session_state.get('quick_market_has_calculated'):
            st.info('Preencha os valores e toque em Calcular para ver a simulação.')
            _render_saved_result_notice()
            return

        _save_global_result(result, has_source=has_source, cost_column=selected_cost_column)
        st.markdown('## Resultado da Precificação')
        st.caption('Simulação dos cálculos')
        _metric_card('Taxa Marketplace', money(result.marketplace_fee), f'({percent(result.marketplace_fee_percent)})')
        _metric_card('Taxa Fixa', money(result.fixed_fee))
        _metric_card('Frete', money(result.freight))
        _metric_card('Imposto', money(result.tax))
        _metric_card('Outros Custos', money(result.extra_cost))
        _metric_card('Custo Total da amostra', money(result.total_cost))
        _profit_card(result.profit, result.margin)
        _render_observations(result, has_source=has_source, cost_column=selected_cost_column)

        if to_decimal(sale_price) <= 0:
            st.warning('Informe o preço de venda para calcular lucro e margem.')
        elif result.profit < 0:
            st.warning('Atenção: o lucro líquido ficou negativo. Revise custo, preço, frete, imposto ou taxas.')
        elif has_source:
            st.success('Simulação concluída. O cálculo será aplicado linha a linha usando a coluna de custo selecionada.')
        else:
            st.success('Simulação avulsa concluída. Quando houver fonte de dados, a calculadora poderá aplicar o preço linha a linha.')


__all__ = [
    'GLOBAL_PRICE_CONFIG_KEY',
    'GLOBAL_PRICE_MODE_KEY',
    'GLOBAL_PRICE_READY_KEY',
    'GLOBAL_PRICE_RESULT_KEY',
    'GLOBAL_PRICE_SOURCE_COST_COLUMN_KEY',
    'GLOBAL_PRICE_WARNING_ACK_KEY',
    'GLOBAL_PRICE_WARNING_TEXT',
    'render_quick_price_calculator',
]
