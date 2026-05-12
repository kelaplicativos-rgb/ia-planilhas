from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any


def parse_money(value: Any) -> Decimal:
    text = str(value or '').strip()
    if not text:
        return Decimal('0')
    text = text.replace('R$', '').replace(' ', '')
    if ',' in text and '.' in text:
        if text.rfind(',') > text.rfind('.'):
            text = text.replace('.', '').replace(',', '.')
        else:
            text = text.replace(',', '')
    elif ',' in text:
        text = text.replace(',', '.')
    keep = ''.join(ch for ch in text if ch.isdigit() or ch in {'.', '-'})
    try:
        return Decimal(keep or '0')
    except Exception:
        return Decimal('0')


def money_ptbr(value: Decimal) -> str:
    return str(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)).replace('.', ',')


def calculate_marketplace_price(cost: Any, rules: dict[str, Any]) -> Decimal:
    base = parse_money(cost)
    commission = Decimal(str(rules.get('commission_percent', 0) or 0)) / Decimal('100')
    tax = Decimal(str(rules.get('tax_percent', 0) or 0)) / Decimal('100')
    profit = Decimal(str(rules.get('profit_percent', 0) or 0)) / Decimal('100')
    fixed_fee = parse_money(rules.get('fixed_fee', 0))
    denominator = Decimal('1') - commission - tax - profit
    if denominator <= Decimal('0.01'):
        denominator = Decimal('0.01')
    return (base + fixed_fee) / denominator


def calculate_promo_price(price: Decimal, rules: dict[str, Any]) -> Decimal:
    discount = Decimal(str(rules.get('promo_discount_percent', 0) or 0)) / Decimal('100')
    if discount <= 0:
        return Decimal('0')
    return price * (Decimal('1') - discount)


__all__ = ['calculate_marketplace_price', 'calculate_promo_price', 'money_ptbr', 'parse_money']
