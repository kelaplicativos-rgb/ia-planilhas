from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

import streamlit as st

AD_TYPES = ('Clássico', 'Premium')


def _to_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value or '0').replace(',', '.'))
    except Exception:
        return Decimal('0')


def _money(value: Decimal) -> str:
    return f'R$ {value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)}'.replace('.', ',')


def _percent(value: Decimal) -> str:
    return f'{value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)}%'.replace('.', ',')


def _rate(value: Decimal) -> Decimal:
    return value / Decimal('100')


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
  <div style="font-size:1.85rem;font-weight:950;margin:.35rem 0;">{_money(profit)}</div>
  <div style="font-size:1rem;font-weight:650;">Margem de Lucro: {_percent(margin)}</div>
</div>
''',
        unsafe_allow_html=True,
    )


def _calc_result(
    *,
    marketplace_fee_percent: Decimal,
    cost: Decimal,
    sale_price: Decimal,
    tax_percent: Decimal,
    freight: Decimal,
    fixed_fee: Decimal,
    extra_cost: Decimal,
) -> dict[str, Decimal]:
    marketplace_fee = sale_price * _rate(marketplace_fee_percent)
    tax = sale_price * _rate(tax_percent)
    total_cost = cost + extra_cost + marketplace_fee + fixed_fee + freight + tax
    profit = sale_price - total_cost
    margin = (profit / sale_price * Decimal('100')) if sale_price > 0 else Decimal('0')

    return {
        'marketplace_fee': marketplace_fee,
        'fixed_fee': fixed_fee,
        'freight': freight,
        'tax': tax,
        'extra_cost': extra_cost,
        'total_cost': total_cost,
        'profit': profit,
        'margin': margin,
    }


def _render_observations(ad_type: str, fee_percent: Decimal) -> None:
    st.markdown(
        f'''
<div style="background:#dbeafe;border:1px solid #bfdbfe;border-radius:16px;padding:1rem 1.2rem;color:#1e3a5f;margin-top:.8rem;">
  <div style="font-weight:900;margin-bottom:.55rem;">Observações:</div>
  <ul style="margin:.2rem 0 0 1.15rem;padding:0;line-height:1.65;">
    <li>Tipo selecionado: <b>{ad_type}</b>.</li>
    <li>Taxa informada para este cálculo: <b>{_percent(fee_percent)}</b>.</li>
    <li>Preencha as taxas conforme o marketplace, categoria ou contrato do vendedor.</li>
    <li>Esta simulação não altera nenhuma planilha do fluxo.</li>
  </ul>
</div>
''',
        unsafe_allow_html=True,
    )


def render_quick_price_calculator() -> None:
    st.markdown('### Calculadora rápida de preço')
    st.caption('Simule preço, taxas e lucro sem anexar planilha e sem iniciar o fluxo completo.')

    with st.container(border=True):
        st.markdown('## Configurações')
        st.caption('Defina os parâmetros para o cálculo')

        st.markdown('#### Taxas do marketplace')
        st.caption('Informe manualmente as porcentagens cobradas pelo canal, marketplace ou loja.')
        c_fee_1, c_fee_2 = st.columns(2)
        classic_fee = _to_decimal(c_fee_1.number_input('Taxa Clássico (%)', min_value=0.0, value=11.5, step=0.5, key='quick_market_classic_fee'))
        premium_fee = _to_decimal(c_fee_2.number_input('Taxa Premium (%)', min_value=0.0, value=16.5, step=0.5, key='quick_market_premium_fee'))

        ad_type = st.selectbox('Tipo de taxa / anúncio', AD_TYPES, index=0, key='quick_market_ad_type')
        marketplace_fee_percent = premium_fee if ad_type == 'Premium' else classic_fee

        cost = _to_decimal(st.number_input('Custo do Produto', min_value=0.0, value=65.0, step=1.0, key='quick_market_cost'))
        sale_price = _to_decimal(st.number_input('Preço de Venda (R$)', min_value=0.0, value=130.0, step=1.0, key='quick_market_sale_price'))
        tax_percent = _to_decimal(st.number_input('Imposto (%)', min_value=0.0, value=6.0, step=0.5, key='quick_market_tax'))
        freight = _to_decimal(st.number_input('Custo do Frete (R$)', min_value=0.0, value=0.0, step=1.0, key='quick_market_freight'))
        fixed_fee = _to_decimal(st.number_input('Taxa Fixa (R$)', min_value=0.0, value=0.0, step=0.5, key='quick_market_fixed_fee'))
        extra_cost = _to_decimal(st.number_input('Outros Custos (R$)', min_value=0.0, value=0.0, step=0.5, key='quick_market_extra_cost'))

        clicked = st.button('🧮 Calcular', use_container_width=True, key='quick_market_calculate')
        if clicked:
            st.session_state['quick_market_has_calculated'] = True

        if not st.session_state.get('quick_market_has_calculated'):
            st.info('Preencha os valores e toque em Calcular para ver a simulação.')
            return

        result = _calc_result(
            marketplace_fee_percent=marketplace_fee_percent,
            cost=cost,
            sale_price=sale_price,
            tax_percent=tax_percent,
            freight=freight,
            fixed_fee=fixed_fee,
            extra_cost=extra_cost,
        )

        st.markdown('## Resultado da Precificação')
        st.caption('Simulação dos cálculos')
        _metric_card('Taxa Marketplace', _money(result['marketplace_fee']), f'({_percent(marketplace_fee_percent)})')
        _metric_card('Taxa Fixa', _money(result['fixed_fee']))
        _metric_card('Frete', _money(result['freight']))
        _metric_card('Imposto', _money(result['tax']))
        _metric_card('Outros Custos', _money(result['extra_cost']))
        _metric_card('Custo Total', _money(result['total_cost']))
        _profit_card(result['profit'], result['margin'])
        _render_observations(ad_type, marketplace_fee_percent)

        if sale_price <= 0:
            st.warning('Informe o preço de venda para calcular lucro e margem.')
        elif result['profit'] < 0:
            st.warning('Atenção: o lucro líquido ficou negativo. Revise custo, preço, frete, imposto ou taxas.')
        else:
            st.success('Simulação concluída. Estes valores não alteram nenhuma planilha do fluxo.')


__all__ = ['render_quick_price_calculator']
