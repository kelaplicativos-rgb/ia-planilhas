from __future__ import annotations

from decimal import Decimal
from typing import Any

from bling_app_zero.v2.marketplace_calculator import D, money


def calc_easy_sale_price(base_value: Any, config: dict[str, Any] | None) -> Decimal:
    config = dict(config or {})
    base = D(base_value)
    if base <= Decimal('0'):
        return Decimal('0')

    mode = str(config.get('quick_reprice_mode') or 'markup')
    add_percent = D(config.get('quick_markup_percent', 0))
    tax_percent = D(config.get('tax_percent', 0))
    fee_percent = D(config.get('marketplace_fee_percent', 0))
    other_percent = D(config.get('other_sale_fees_percent', 0))
    promo_percent = D(config.get('promo_discount_percent', 0))
    fixed_value = D(config.get('quick_fixed_addition', 0)) + D(config.get('freight_cost', 0)) + D(config.get('marketplace_fixed_fee', 0))

    if mode == 'net_margin':
        total_percent = add_percent + tax_percent + fee_percent + other_percent + promo_percent
        divider = Decimal('1') - (total_percent / Decimal('100'))
        if divider <= Decimal('0'):
            return Decimal('0')
        return (base + fixed_value) / divider

    total_percent = add_percent + fee_percent + other_percent
    return (base * (Decimal('1') + (total_percent / Decimal('100')))) + fixed_value


def calc_easy_promo_price(sale_price: Any, promo_percent: Any) -> Decimal:
    sale = D(sale_price)
    discount = D(promo_percent)
    if sale <= Decimal('0') or discount <= Decimal('0'):
        return Decimal('0')
    return sale * (Decimal('1') - (discount / Decimal('100')))


def money_or_empty(value: Decimal) -> str:
    return money(value) if value > Decimal('0') else ''


__all__ = ['calc_easy_promo_price', 'calc_easy_sale_price', 'money_or_empty']
