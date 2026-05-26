from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

import streamlit as st

QUICK_MODES = ['Lucro nominal', 'Margem de contribuição', 'Preço fixo']


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


def _denominator(rate: Decimal) -> Decimal:
    denominator = Decimal('1') - rate
    return denominator if denominator > Decimal('0.01') else Decimal('0.01')


def _calc(
    *,
    cost: Decimal,
    freight: Decimal,
    fixed_cost: Decimal,
    marketplace_fee: Decimal,
    tax: Decimal,
    other_fee: Decimal,
    mode: str,
    nominal_profit: Decimal,
    desired_margin: Decimal,
    fixed_price: Decimal,
    promo: Decimal,
) -> dict[str, Decimal]:
    base_cost = cost + freight + fixed_cost
    variable_rate = _rate(marketplace_fee) + _rate(tax) + _rate(other_fee)

    if mode == 'Margem de contribuição':
        sale_price = base_cost / _denominator(variable_rate + _rate(desired_margin))
    elif mode == 'Preço fixo':
        sale_price = fixed_price
    else:
        sale_price = (base_cost + nominal_profit) / _denominator(variable_rate)

    sale_price = max(sale_price, Decimal('0'))
    fees_value = sale_price * variable_rate
    profit = sale_price - fees_value - base_cost
    margin = (profit / sale_price * Decimal('100')) if sale_price > 0 else Decimal('0')
    break_even = base_cost / _denominator(variable_rate) if base_cost > 0 else Decimal('0')
    promo_price = sale_price * (Decimal('1') - _rate(promo)) if promo > 0 else sale_price

    return {
        'sale_price': sale_price,
        'profit': profit,
        'margin': margin,
        'break_even': break_even,
        'promo_price': promo_price,
        'fees_percent': variable_rate * Decimal('100'),
        'fees_value': fees_value,
        'base_cost': base_cost,
    }


def _card(label: str, value: str, help_text: str = '') -> None:
    st.markdown(
        f'''
<div style="background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:1rem;box-shadow:0 8px 20px rgba(15,23,42,.06);">
  <div style="font-size:.8rem;color:#64748b;font-weight:800;">{label}</div>
  <div style="font-size:1.25rem;color:#0f172a;font-weight:900;line-height:1.2;margin-top:.2rem;">{value}</div>
  <div style="font-size:.76rem;color:#64748b;margin-top:.25rem;">{help_text}</div>
</div>
''',
        unsafe_allow_html=True,
    )


def render_quick_price_calculator() -> None:
    st.markdown('### Calculadora rápida de preço')
    st.caption('Digite os valores e veja o resultado na hora, sem anexar planilha e sem iniciar fluxo.')

    with st.container(border=True):
        mode = st.radio('Como deseja calcular?', QUICK_MODES, horizontal=True, key='quick_price_mode')

        c1, c2, c3 = st.columns(3)
        cost = _to_decimal(c1.number_input('Custo do produto R$', min_value=0.0, value=0.0, step=1.0, key='quick_price_cost'))
        freight = _to_decimal(c2.number_input('Frete / embalagem R$', min_value=0.0, value=0.0, step=1.0, key='quick_price_freight'))
        fixed_cost = _to_decimal(c3.number_input('Custo fixo extra R$', min_value=0.0, value=0.0, step=1.0, key='quick_price_fixed_cost'))

        c4, c5, c6 = st.columns(3)
        marketplace_fee = _to_decimal(c4.number_input('Taxa marketplace %', min_value=0.0, value=20.0, step=0.5, key='quick_price_marketplace_fee'))
        tax = _to_decimal(c5.number_input('Imposto %', min_value=0.0, value=0.0, step=0.5, key='quick_price_tax'))
        other_fee = _to_decimal(c6.number_input('Outras taxas %', min_value=0.0, value=0.0, step=0.5, key='quick_price_other_fee'))

        c7, c8, c9 = st.columns(3)
        nominal_profit = Decimal('0')
        desired_margin = Decimal('0')
        fixed_price = Decimal('0')

        if mode == 'Lucro nominal':
            nominal_profit = _to_decimal(c7.number_input('Quero ganhar R$', min_value=0.0, value=0.0, step=1.0, key='quick_price_nominal_profit'))
        elif mode == 'Margem de contribuição':
            desired_margin = _to_decimal(c7.number_input('Quero margem de %', min_value=0.0, value=15.0, step=0.5, key='quick_price_desired_margin'))
        else:
            fixed_price = _to_decimal(c7.number_input('Quero vender por R$', min_value=0.0, value=0.0, step=1.0, key='quick_price_fixed_price'))

        promo = _to_decimal(c8.number_input('Desconto promo %', min_value=0.0, value=0.0, step=0.5, key='quick_price_promo'))
        round_90 = c9.checkbox('Arredondar para final ,90', value=False, key='quick_price_round_90')

        result = _calc(
            cost=cost,
            freight=freight,
            fixed_cost=fixed_cost,
            marketplace_fee=marketplace_fee,
            tax=tax,
            other_fee=other_fee,
            mode=mode,
            nominal_profit=nominal_profit,
            desired_margin=desired_margin,
            fixed_price=fixed_price,
            promo=promo,
        )

        if round_90 and result['sale_price'] > 0:
            rounded = result['sale_price'].quantize(Decimal('1'), rounding=ROUND_HALF_UP) - Decimal('0.10')
            result = _calc(
                cost=cost,
                freight=freight,
                fixed_cost=fixed_cost,
                marketplace_fee=marketplace_fee,
                tax=tax,
                other_fee=other_fee,
                mode='Preço fixo',
                nominal_profit=Decimal('0'),
                desired_margin=Decimal('0'),
                fixed_price=max(rounded, Decimal('0.90')),
                promo=promo,
            )

        st.markdown('#### Resultado')
        r1, r2, r3 = st.columns(3)
        with r1:
            _card('Preço de venda', _money(result['sale_price']), 'Valor sugerido para anunciar')
        with r2:
            _card('Lucro estimado', _money(result['profit']), 'Depois de custos, taxas e imposto')
        with r3:
            _card('Margem real', _percent(result['margin']), 'Margem final estimada')

        r4, r5, r6 = st.columns(3)
        with r4:
            _card('Preço promocional', _money(result['promo_price']), 'Com desconto aplicado')
        with r5:
            _card('Ponto de equilíbrio', _money(result['break_even']), 'Preço mínimo sem lucro')
        with r6:
            _card('Taxas variáveis', _percent(result['fees_percent']), f"Total: {_money(result['fees_value'])}")

        if cost <= 0:
            st.info('Digite o custo do produto para fazer uma conta real.')
        elif result['profit'] < 0:
            st.warning('Atenção: o lucro ficou negativo. Ajuste preço, custo, taxas ou margem.')
        else:
            st.success('Cálculo rápido concluído. Nada foi aplicado em planilhas do fluxo.')


__all__ = ['render_quick_price_calculator']
