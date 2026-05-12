from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


def D(value: Any) -> Decimal:
    text = str(value or '0').strip().replace('R$', '').replace('%', '').replace(' ', '')
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.') if text.rfind(',') > text.rfind('.') else text.replace(',', '')
    elif ',' in text:
        text = text.replace(',', '.')
    cleaned = ''.join(ch for ch in text if ch.isdigit() or ch in '.-')
    try:
        return Decimal(cleaned or '0')
    except Exception:
        return Decimal('0')


def pct(value: Any) -> Decimal:
    value = D(value)
    return value if value <= Decimal('1') else value / Decimal('100')


def money(value: Decimal) -> str:
    return f'{value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)}'.replace('.', ',')


def percent(value: Decimal) -> str:
    return f'{(value * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)}%'.replace('.', ',')


@dataclass(frozen=True)
class CalculatorInputs:
    tax_percent: Decimal = Decimal('0')
    product_cost: Decimal = Decimal('0')
    freight_cost: Decimal = Decimal('0')
    desired_sale_price: Decimal = Decimal('0')
    desired_nominal_profit: Decimal = Decimal('0')
    desired_contribution_margin_percent: Decimal = Decimal('0')
    supplier_term_days: Decimal = Decimal('0')
    stock_turnover_days: Decimal = Decimal('0')
    other_sale_fees_percent: Decimal = Decimal('0')


@dataclass(frozen=True)
class MarketplaceFeeRule:
    marketplace: str
    variation: str
    fee_percent: Decimal
    rule_type: str = 'standard'
    capital_days: Decimal = Decimal('15')
    threshold: Decimal = Decimal('0')
    fixed_fee: Decimal = Decimal('0')
    note: str = ''


@dataclass(frozen=True)
class MarketplacePriceResult:
    marketplace: str
    variation: str
    fee_percent: Decimal
    sale_price: Decimal
    nominal_profit: Decimal
    contribution_margin: Decimal
    working_capital: Decimal
    note: str = ''


MARKETPLACE_RULES: tuple[MarketplaceFeeRule, ...] = (
    MarketplaceFeeRule('mercado_livre', 'Anúncio Clássico', Decimal('10'), 'meli_79', Decimal('10'), Decimal('79'), Decimal('5')),
    MarketplaceFeeRule('mercado_livre', 'Anúncio Premium', Decimal('15'), 'meli_79', Decimal('10'), Decimal('79'), Decimal('5')),
    MarketplaceFeeRule('b2w', 'B2W Entrega ou Fulfillment · Até 29kg', Decimal('16'), 'b2w_40', Decimal('15'), Decimal('40'), Decimal('5')),
    MarketplaceFeeRule('b2w', 'B2W Entrega ou Fulfillment · Acima de 29kg', Decimal('16'), 'b2w_80', Decimal('15'), Decimal('80'), Decimal('5')),
    MarketplaceFeeRule('b2w', 'Transportadora Própria', Decimal('16'), 'fixed_fee_only', Decimal('15'), Decimal('0'), Decimal('5')),
    MarketplaceFeeRule('via_varejo', 'Casas Bahia, Extra, Loja HP, Ponto Frio', Decimal('14'), 'standard', Decimal('27')),
    MarketplaceFeeRule('via_varejo', 'Grupo Via · maior taxa', Decimal('18'), 'standard', Decimal('27')),
    MarketplaceFeeRule('magazine_luiza', 'Magazine Luiza, Netshoes e Zattini · menor taxa', Decimal('10'), 'standard', Decimal('0')),
    MarketplaceFeeRule('magazine_luiza', 'Magazine Luiza, Netshoes e Zattini · maior taxa', Decimal('20'), 'standard', Decimal('0')),
    MarketplaceFeeRule('olist', 'Olist', Decimal('20'), 'meli_100', Decimal('35'), Decimal('100'), Decimal('5')),
    MarketplaceFeeRule('madeira_madeira', 'Madeira Madeira', Decimal('20'), 'commission_on_freight', Decimal('15')),
    MarketplaceFeeRule('carrefour', 'Carrefour · menor taxa', Decimal('10'), 'standard', Decimal('27')),
    MarketplaceFeeRule('carrefour', 'Carrefour · maior taxa', Decimal('14'), 'standard', Decimal('27')),
    MarketplaceFeeRule('amazon', 'Amazon · menor taxa', Decimal('8'), 'standard', Decimal('15')),
    MarketplaceFeeRule('amazon', 'Amazon · maior taxa', Decimal('20'), 'standard', Decimal('15')),
    MarketplaceFeeRule('elo7', 'Elo7 · Anúncio Clássico', Decimal('12'), 'standard', Decimal('2')),
    MarketplaceFeeRule('elo7', 'Elo7 · Anúncio Plus', Decimal('18'), 'standard', Decimal('2')),
    MarketplaceFeeRule('gfg', 'GFG · Dafiti, Kanui e Tricae · menor taxa', Decimal('25'), 'standard', Decimal('35')),
    MarketplaceFeeRule('gfg', 'GFG · Dafiti, Kanui e Tricae · maior taxa', Decimal('30'), 'standard', Decimal('35')),
    MarketplaceFeeRule('cissa_magazine', 'Cissa Magazine · menor taxa', Decimal('8'), 'standard', Decimal('18')),
    MarketplaceFeeRule('cissa_magazine', 'Cissa Magazine · maior taxa', Decimal('14'), 'standard', Decimal('18')),
    MarketplaceFeeRule('shopee', 'Shopee · taxa digitada', Decimal('12'), 'standard', Decimal('15')),
)


def parse_inputs(data: dict[str, Any]) -> CalculatorInputs:
    return CalculatorInputs(
        tax_percent=D(data.get('tax_percent', 0)),
        product_cost=D(data.get('product_cost', 0)),
        freight_cost=D(data.get('freight_cost', 0)),
        desired_sale_price=D(data.get('desired_sale_price', 0)),
        desired_nominal_profit=D(data.get('desired_nominal_profit', 0)),
        desired_contribution_margin_percent=D(data.get('desired_contribution_margin_percent', 0)),
        supplier_term_days=D(data.get('supplier_term_days', 0)),
        stock_turnover_days=D(data.get('stock_turnover_days', 0)),
        other_sale_fees_percent=D(data.get('other_sale_fees_percent', 0)),
    )


def _rate(inputs: CalculatorInputs, rule: MarketplaceFeeRule, target_margin: Decimal = Decimal('0')) -> Decimal:
    return pct(inputs.tax_percent) + pct(inputs.other_sale_fees_percent) + pct(rule.fee_percent) + target_margin


def _base_cost(inputs: CalculatorInputs) -> Decimal:
    return inputs.product_cost


def _denominator(rate: Decimal) -> Decimal:
    denominator = Decimal('1') - rate
    return denominator if denominator > Decimal('0.01') else Decimal('0.01')


def _standard_price(inputs: CalculatorInputs, rule: MarketplaceFeeRule, mode: str) -> Decimal:
    if mode == 'contribution_margin':
        margin = pct(inputs.desired_contribution_margin_percent)
        numerator = inputs.product_cost
        if rule.rule_type == 'commission_on_freight':
            numerator = inputs.product_cost + (inputs.freight_cost * pct(rule.fee_percent))
        return numerator / _denominator(_rate(inputs, rule, margin))
    if mode == 'fixed_sale_price':
        return inputs.desired_sale_price
    numerator = inputs.product_cost + inputs.desired_nominal_profit
    if rule.rule_type == 'commission_on_freight':
        numerator = inputs.product_cost + inputs.desired_nominal_profit + (inputs.freight_cost * pct(rule.fee_percent))
    return numerator / _denominator(_rate(inputs, rule))


def _price_with_threshold(inputs: CalculatorInputs, rule: MarketplaceFeeRule, mode: str) -> Decimal:
    if mode == 'contribution_margin':
        margin = pct(inputs.desired_contribution_margin_percent)
        low = (inputs.product_cost + rule.fixed_fee) / _denominator(_rate(inputs, rule, margin))
        high = (inputs.product_cost + inputs.freight_cost) / _denominator(_rate(inputs, rule, margin))
    elif mode == 'fixed_sale_price':
        return inputs.desired_sale_price
    else:
        low = (inputs.product_cost + inputs.desired_nominal_profit + rule.fixed_fee) / _denominator(_rate(inputs, rule))
        high = (inputs.product_cost + inputs.desired_nominal_profit + inputs.freight_cost) / _denominator(_rate(inputs, rule))
    return high if low >= rule.threshold else low


def _sale_price(inputs: CalculatorInputs, rule: MarketplaceFeeRule, mode: str) -> Decimal:
    if rule.rule_type in {'meli_79', 'meli_100', 'b2w_40', 'b2w_80'}:
        return _price_with_threshold(inputs, rule, mode)
    if rule.rule_type == 'fixed_fee_only':
        if mode == 'contribution_margin':
            return (inputs.product_cost + rule.fixed_fee) / _denominator(_rate(inputs, rule, pct(inputs.desired_contribution_margin_percent)))
        if mode == 'fixed_sale_price':
            return inputs.desired_sale_price
        return (inputs.product_cost + inputs.desired_nominal_profit + rule.fixed_fee) / _denominator(_rate(inputs, rule))
    return _standard_price(inputs, rule, mode)


def _nominal_profit(inputs: CalculatorInputs, rule: MarketplaceFeeRule, sale_price: Decimal, mode: str) -> Decimal:
    if mode == 'contribution_margin':
        return sale_price * pct(inputs.desired_contribution_margin_percent)
    variable = sale_price * _rate(inputs, rule)
    freight_component = Decimal('0')
    if rule.rule_type in {'meli_79', 'meli_100', 'b2w_40', 'b2w_80'}:
        low_reference = sale_price
        low_with_fee = (inputs.product_cost + inputs.desired_nominal_profit + rule.fixed_fee) / _denominator(_rate(inputs, rule)) if mode != 'contribution_margin' else Decimal('0')
        freight_component = inputs.freight_cost if rule.threshold and low_reference >= rule.threshold and low_with_fee >= rule.threshold else rule.fixed_fee
    elif rule.rule_type == 'fixed_fee_only':
        freight_component = rule.fixed_fee
    elif rule.rule_type == 'commission_on_freight':
        freight_component = inputs.freight_cost * pct(rule.fee_percent)
    return sale_price - variable - inputs.product_cost - freight_component


def _working_capital(inputs: CalculatorInputs, sale_price: Decimal, rule: MarketplaceFeeRule) -> Decimal:
    return (inputs.product_cost / Decimal('30') * inputs.supplier_term_days) - (inputs.product_cost / Decimal('30') * inputs.stock_turnover_days) - (sale_price / Decimal('30') * rule.capital_days)


def result_from_sale_price(inputs: CalculatorInputs, rule: MarketplaceFeeRule, sale_price: Decimal, mode: str = 'nominal_profit') -> MarketplacePriceResult:
    nominal_profit = _nominal_profit(inputs, rule, sale_price, mode)
    contribution_margin = nominal_profit / sale_price if sale_price > 0 else Decimal('0')
    return MarketplacePriceResult(
        marketplace=rule.marketplace,
        variation=rule.variation,
        fee_percent=rule.fee_percent,
        sale_price=sale_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        nominal_profit=nominal_profit.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        contribution_margin=contribution_margin.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP),
        working_capital=_working_capital(inputs, sale_price, rule).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        note=rule.note,
    )


def price_by_nominal_profit(inputs: CalculatorInputs, rule: MarketplaceFeeRule) -> MarketplacePriceResult:
    return result_from_sale_price(inputs, rule, _sale_price(inputs, rule, 'nominal_profit'), 'nominal_profit')


def price_by_contribution_margin(inputs: CalculatorInputs, rule: MarketplaceFeeRule) -> MarketplacePriceResult:
    return result_from_sale_price(inputs, rule, _sale_price(inputs, rule, 'contribution_margin'), 'contribution_margin')


def simulate_by_fixed_sale_price(inputs: CalculatorInputs, rule: MarketplaceFeeRule) -> MarketplacePriceResult:
    return result_from_sale_price(inputs, rule, inputs.desired_sale_price, 'fixed_sale_price')


def calculate_all(inputs: CalculatorInputs, mode: str = 'nominal_profit') -> list[MarketplacePriceResult]:
    results: list[MarketplacePriceResult] = []
    for rule in MARKETPLACE_RULES:
        if mode == 'contribution_margin':
            results.append(price_by_contribution_margin(inputs, rule))
        elif mode == 'fixed_sale_price':
            results.append(simulate_by_fixed_sale_price(inputs, rule))
        else:
            results.append(price_by_nominal_profit(inputs, rule))
    return results


__all__ = [
    'CalculatorInputs',
    'D',
    'MARKETPLACE_RULES',
    'MarketplaceFeeRule',
    'MarketplacePriceResult',
    'calculate_all',
    'money',
    'parse_inputs',
    'pct',
    'percent',
    'price_by_contribution_margin',
    'price_by_nominal_profit',
    'simulate_by_fixed_sale_price',
]
