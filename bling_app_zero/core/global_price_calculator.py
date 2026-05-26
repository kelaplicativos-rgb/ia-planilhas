from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


AD_TYPES = ('Clássico', 'Premium')


def to_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or '0').replace('R$', '').replace('%', '').replace(' ', '').replace(',', '.'))
    except Exception:
        return Decimal('0')


def money(value: Decimal) -> str:
    return f'R$ {value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)}'.replace('.', ',')


def percent(value: Decimal) -> str:
    return f'{value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)}%'.replace('.', ',')


def rate(value: Decimal) -> Decimal:
    return value / Decimal('100')


@dataclass(frozen=True)
class GlobalPriceInput:
    ad_type: str = 'Clássico'
    classic_fee_percent: Decimal = Decimal('11.5')
    premium_fee_percent: Decimal = Decimal('16.5')
    cost: Decimal = Decimal('0')
    sale_price: Decimal = Decimal('0')
    tax_percent: Decimal = Decimal('0')
    freight: Decimal = Decimal('0')
    fixed_fee: Decimal = Decimal('0')
    extra_cost: Decimal = Decimal('0')


@dataclass(frozen=True)
class GlobalPriceResult:
    ad_type: str
    marketplace_fee_percent: Decimal
    marketplace_fee: Decimal
    fixed_fee: Decimal
    freight: Decimal
    tax: Decimal
    extra_cost: Decimal
    total_cost: Decimal
    profit: Decimal
    margin: Decimal
    sale_price: Decimal
    cost: Decimal


def selected_fee_percent(data: GlobalPriceInput) -> Decimal:
    return data.premium_fee_percent if data.ad_type == 'Premium' else data.classic_fee_percent


def calculate_global_price(data: GlobalPriceInput) -> GlobalPriceResult:
    marketplace_fee_percent = selected_fee_percent(data)
    marketplace_fee = data.sale_price * rate(marketplace_fee_percent)
    tax = data.sale_price * rate(data.tax_percent)
    total_cost = data.cost + data.extra_cost + marketplace_fee + data.fixed_fee + data.freight + tax
    profit = data.sale_price - total_cost
    margin = (profit / data.sale_price * Decimal('100')) if data.sale_price > 0 else Decimal('0')
    return GlobalPriceResult(
        ad_type=data.ad_type,
        marketplace_fee_percent=marketplace_fee_percent,
        marketplace_fee=marketplace_fee,
        fixed_fee=data.fixed_fee,
        freight=data.freight,
        tax=tax,
        extra_cost=data.extra_cost,
        total_cost=total_cost,
        profit=profit,
        margin=margin,
        sale_price=data.sale_price,
        cost=data.cost,
    )


def build_input_from_values(
    *,
    ad_type: str = 'Clássico',
    classic_fee_percent: Any = '11.5',
    premium_fee_percent: Any = '16.5',
    cost: Any = '0',
    sale_price: Any = '0',
    tax_percent: Any = '0',
    freight: Any = '0',
    fixed_fee: Any = '0',
    extra_cost: Any = '0',
) -> GlobalPriceInput:
    clean_ad_type = str(ad_type or 'Clássico')
    if clean_ad_type not in AD_TYPES:
        clean_ad_type = 'Clássico'
    return GlobalPriceInput(
        ad_type=clean_ad_type,
        classic_fee_percent=to_decimal(classic_fee_percent),
        premium_fee_percent=to_decimal(premium_fee_percent),
        cost=to_decimal(cost),
        sale_price=to_decimal(sale_price),
        tax_percent=to_decimal(tax_percent),
        freight=to_decimal(freight),
        fixed_fee=to_decimal(fixed_fee),
        extra_cost=to_decimal(extra_cost),
    )


__all__ = [
    'AD_TYPES',
    'GlobalPriceInput',
    'GlobalPriceResult',
    'build_input_from_values',
    'calculate_global_price',
    'money',
    'percent',
    'rate',
    'selected_fee_percent',
    'to_decimal',
]
