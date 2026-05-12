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
    return D(value) / Decimal('100')


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
    MarketplaceFeeRule('mercado_livre', 'Anúncio Clássico', Decimal('10'), 'Tarifa padrão visível na calculadora.'),
    MarketplaceFeeRule('mercado_livre', 'Anúncio Premium', Decimal('15'), 'Tarifa padrão visível na calculadora.'),
    MarketplaceFeeRule('b2w', 'B2W Entrega ou B2W Fulfillment · Até 2kg', Decimal('16'), 'Frete grátis aplicado conforme regra do grupo.'),
    MarketplaceFeeRule('b2w', 'B2W Entrega ou B2W Fulfillment · Acima de 2kg', Decimal('16'), 'Frete grátis aplicado conforme regra do grupo.'),
    MarketplaceFeeRule('b2w', 'Transportadora Própria · Qualquer', Decimal('16'), ''),
    MarketplaceFeeRule('via_varejo', 'Casas Bahia, Extra, Loja HP, Ponto Frio', Decimal('14'), ''),
    MarketplaceFeeRule('via_varejo', 'Grupo Via · maior taxa', Decimal('18'), ''),
    MarketplaceFeeRule('magazine_luiza', 'Magazine Luiza, Netshoes e Zattini · Menor taxa', Decimal('10'), ''),
    MarketplaceFeeRule('magazine_luiza', 'Magazine Luiza, Netshoes e Zattini · Maior taxa', Decimal('20'), ''),
    MarketplaceFeeRule('olist', 'Olist', Decimal('20'), ''),
    MarketplaceFeeRule('madeira_madeira', 'Madeira Madeira', Decimal('20'), ''),
    MarketplaceFeeRule('carrefour', 'Carrefour · Menor taxa', Decimal('10'), ''),
    MarketplaceFeeRule('carrefour', 'Carrefour · Maior taxa', Decimal('14'), ''),
    MarketplaceFeeRule('amazon', 'Amazon · Menor taxa', Decimal('8'), ''),
    MarketplaceFeeRule('amazon', 'Amazon · Maior taxa', Decimal('20'), ''),
    MarketplaceFeeRule('elo7', 'Elo7 · Anúncio Clássico', Decimal('12'), ''),
    MarketplaceFeeRule('elo7', 'Elo7 · Anúncio Plus', Decimal('18'), ''),
    MarketplaceFeeRule('gfg', 'GFG · Dafiti, Kanui e Tricae · Menor taxa', Decimal('25'), ''),
    MarketplaceFeeRule('gfg', 'GFG · Dafiti, Kanui e Tricae · Maior taxa', Decimal('30'), ''),
    MarketplaceFeeRule('cissa_magazine', 'Cissa Magazine · Menor taxa', Decimal('8'), ''),
    MarketplaceFeeRule('cissa_magazine', 'Cissa Magazine · Maior taxa', Decimal('14'), ''),
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


def total_variable_rate(inputs: CalculatorInputs, rule: MarketplaceFeeRule) -> Decimal:
    return pct(inputs.tax_percent + inputs.other_sale_fees_percent + rule.fee_percent)


def base_cost(inputs: CalculatorInputs) -> Decimal:
    return inputs.product_cost + inputs.freight_cost


def working_capital(inputs: CalculatorInputs, sale_price: Decimal, nominal_profit: Decimal) -> Decimal:
    gap_days = inputs.stock_turnover_days - inputs.supplier_term_days
    if gap_days <= 0:
        return Decimal('0')
    daily_cost = base_cost(inputs) / Decimal('30') if base_cost(inputs) > 0 else Decimal('0')
    return (nominal_profit - (daily_cost * gap_days)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def result_from_sale_price(inputs: CalculatorInputs, rule: MarketplaceFeeRule, sale_price: Decimal) -> MarketplacePriceResult:
    rate = total_variable_rate(inputs, rule)
    variable_cost = sale_price * rate
    nominal_profit = sale_price - variable_cost - base_cost(inputs)
    contribution_margin = (nominal_profit / sale_price) if sale_price > 0 else Decimal('0')
    return MarketplacePriceResult(
        marketplace=rule.marketplace,
        variation=rule.variation,
        fee_percent=rule.fee_percent,
        sale_price=sale_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        nominal_profit=nominal_profit.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        contribution_margin=contribution_margin.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP),
        working_capital=working_capital(inputs, sale_price, nominal_profit),
        note=rule.note,
    )


def price_by_nominal_profit(inputs: CalculatorInputs, rule: MarketplaceFeeRule) -> MarketplacePriceResult:
    rate = total_variable_rate(inputs, rule)
    denominator = Decimal('1') - rate
    if denominator <= Decimal('0.01'):
        denominator = Decimal('0.01')
    sale_price = (base_cost(inputs) + inputs.desired_nominal_profit) / denominator
    return result_from_sale_price(inputs, rule, sale_price)


def price_by_contribution_margin(inputs: CalculatorInputs, rule: MarketplaceFeeRule) -> MarketplacePriceResult:
    rate = total_variable_rate(inputs, rule)
    target_margin = pct(inputs.desired_contribution_margin_percent)
    denominator = Decimal('1') - rate - target_margin
    if denominator <= Decimal('0.01'):
        denominator = Decimal('0.01')
    sale_price = base_cost(inputs) / denominator
    return result_from_sale_price(inputs, rule, sale_price)


def simulate_by_fixed_sale_price(inputs: CalculatorInputs, rule: MarketplaceFeeRule) -> MarketplacePriceResult:
    return result_from_sale_price(inputs, rule, inputs.desired_sale_price)


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
    'MARKETPLACE_RULES',
    'MarketplaceFeeRule',
    'MarketplacePriceResult',
    'calculate_all',
    'money',
    'parse_inputs',
    'percent',
    'price_by_contribution_margin',
    'price_by_nominal_profit',
    'simulate_by_fixed_sale_price',
]
