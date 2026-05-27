from __future__ import annotations

from decimal import Decimal

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

GLOBAL_PRICE_RESULT_KEY = 'global_price_calculator_last_result'
GLOBAL_PRICE_CONFIG_KEY = 'global_price_calculator_last_config'
GLOBAL_PRICE_READY_KEY = 'global_price_calculator_ready'
GLOBAL_PRICE_MODE_KEY = 'global_price_application_mode'
GLOBAL_PRICE_WARNING_ACK_KEY = 'global_price_warning_acknowledged'
GLOBAL_PRICE_WARNING_TEXT = (
    'Atenção: este é um preço global. Se você usar esta opção em uma planilha, '
    'o mesmo preço de venda será aplicado em todos os produtos, independentemente do custo individual de cada item.'
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


def _render_global_price_warning() -> None:
    st.markdown(
        f'''
<div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:16px;padding:1rem 1.2rem;color:#7c2d12;margin:.8rem 0;">
  <div style="font-weight:950;margin-bottom:.4rem;">⚠️ Preço global para todos os produtos</div>
  <div style="line-height:1.55;">{GLOBAL_PRICE_WARNING_TEXT}</div>
</div>
''',
        unsafe_allow_html=True,
    )


def _render_observations(result: GlobalPriceResult) -> None:
    st.markdown(
        f'''
<div style="background:#dbeafe;border:1px solid #bfdbfe;border-radius:16px;padding:1rem 1.2rem;color:#1e3a5f;margin-top:.8rem;">
  <div style="font-weight:900;margin-bottom:.55rem;">Observações:</div>
  <ul style="margin:.2rem 0 0 1.15rem;padding:0;line-height:1.65;">
    <li>Tipo selecionado: <b>{result.ad_type}</b>.</li>
    <li>Taxa informada para este cálculo: <b>{percent(result.marketplace_fee_percent)}</b>.</li>
    <li>Esta é a calculadora única de preço usada como base global do sistema.</li>
    <li>Nos fluxos com planilha, o preço calculado pode preencher o preço final de todos os produtos.</li>
  </ul>
</div>
''',
        unsafe_allow_html=True,
    )


def _save_global_result(result: GlobalPriceResult) -> None:
    st.session_state[GLOBAL_PRICE_RESULT_KEY] = result
    st.session_state[GLOBAL_PRICE_READY_KEY] = True
    st.session_state[GLOBAL_PRICE_MODE_KEY] = 'global_fixed_price_all_products'
    st.session_state['global_price_calculator_sale_price'] = float(result.sale_price)
    st.session_state['global_price_calculator_profit'] = float(result.profit)
    st.session_state['global_price_calculator_margin'] = float(result.margin)
    st.session_state['preco_calculado_global'] = float(result.sale_price)
    st.session_state['preco_unitario_calculado'] = float(result.sale_price)
    st.session_state['preco_global_aplicado_em_todos_produtos'] = True
    st.session_state['preco_global_alerta_texto'] = GLOBAL_PRICE_WARNING_TEXT


def _render_saved_result_notice() -> None:
    result = st.session_state.get(GLOBAL_PRICE_RESULT_KEY)
    if isinstance(result, GlobalPriceResult):
        st.warning(f'Preço global disponível para os fluxos: {money(result.sale_price)}. Ele pode ser aplicado em todos os produtos da planilha.')


def render_quick_price_calculator(*, embedded: bool = False) -> None:
    title = 'Calculadora única de preço' if embedded else 'Calculadora rápida de preço'
    st.markdown(f'### {title}')
    st.caption('Simule preço, taxas e lucro sem anexar planilha. Esta é a base única de precificação do sistema.')

    with st.container(border=True):
        st.markdown('## Configurações')
        st.caption('Defina os parâmetros para o cálculo')

        st.markdown('#### Taxas do marketplace')
        st.caption('Informe manualmente as porcentagens cobradas pelo canal, marketplace ou loja.')
        c_fee_1, c_fee_2 = st.columns(2)
        classic_fee = c_fee_1.number_input('Taxa Clássico (%)', min_value=0.0, value=11.5, step=0.5, key='quick_market_classic_fee')
        premium_fee = c_fee_2.number_input('Taxa Premium (%)', min_value=0.0, value=16.5, step=0.5, key='quick_market_premium_fee')

        ad_type = st.selectbox('Tipo de taxa / anúncio', list(AD_TYPES), index=0, key='quick_market_ad_type')
        cost = st.number_input('Custo do Produto', min_value=0.0, value=65.0, step=1.0, key='quick_market_cost')
        sale_price = st.number_input('Preço de Venda (R$)', min_value=0.0, value=130.0, step=1.0, key='quick_market_sale_price')
        tax_percent = st.number_input('Imposto (%)', min_value=0.0, value=6.0, step=0.5, key='quick_market_tax')
        freight = st.number_input('Custo do Frete (R$)', min_value=0.0, value=0.0, step=1.0, key='quick_market_freight')
        fixed_fee = st.number_input('Taxa Fixa (R$)', min_value=0.0, value=0.0, step=0.5, key='quick_market_fixed_fee')
        extra_cost = st.number_input('Outros Custos (R$)', min_value=0.0, value=0.0, step=0.5, key='quick_market_extra_cost')

        _render_global_price_warning()
        acknowledged = st.checkbox(
            'Entendi que este valor pode ser usado como preço único para todos os produtos da planilha.',
            value=bool(st.session_state.get(GLOBAL_PRICE_WARNING_ACK_KEY)),
            key=GLOBAL_PRICE_WARNING_ACK_KEY,
        )

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

        clicked = st.button('🧮 Calcular e usar este preço', use_container_width=True, key='quick_market_calculate', disabled=not acknowledged)
        if clicked:
            st.session_state['quick_market_has_calculated'] = True
            st.session_state[GLOBAL_PRICE_CONFIG_KEY] = data
            _save_global_result(result)

        if not st.session_state.get('quick_market_has_calculated'):
            st.info('Preencha os valores, confirme o aviso de preço global e toque em Calcular para ver a simulação.')
            _render_saved_result_notice()
            return

        _save_global_result(result)
        st.markdown('## Resultado da Precificação')
        st.caption('Simulação dos cálculos')
        _metric_card('Taxa Marketplace', money(result.marketplace_fee), f'({percent(result.marketplace_fee_percent)})')
        _metric_card('Taxa Fixa', money(result.fixed_fee))
        _metric_card('Frete', money(result.freight))
        _metric_card('Imposto', money(result.tax))
        _metric_card('Outros Custos', money(result.extra_cost))
        _metric_card('Custo Total', money(result.total_cost))
        _profit_card(result.profit, result.margin)
        _render_observations(result)

        if to_decimal(sale_price) <= 0:
            st.warning('Informe o preço de venda para calcular lucro e margem.')
        elif result.profit < 0:
            st.warning('Atenção: o lucro líquido ficou negativo. Revise custo, preço, frete, imposto ou taxas.')
        else:
            st.success('Simulação concluída. O preço global ficou disponível para o restante do fluxo.')


__all__ = [
    'GLOBAL_PRICE_CONFIG_KEY',
    'GLOBAL_PRICE_MODE_KEY',
    'GLOBAL_PRICE_READY_KEY',
    'GLOBAL_PRICE_RESULT_KEY',
    'GLOBAL_PRICE_WARNING_ACK_KEY',
    'GLOBAL_PRICE_WARNING_TEXT',
    'render_quick_price_calculator',
]
