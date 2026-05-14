from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pandas as pd

from bling_app_zero.v2.marketplace_calculator import (
    CalculatorInputs,
    D,
    MarketplaceFeeRule,
    money,
    price_by_contribution_margin,
    price_by_nominal_profit,
    simulate_by_fixed_sale_price,
)

RESPONSIBLE_FILE = 'bling_app_zero/core/shared_price_calculator.py'
DEFAULT_CHANNEL = 'cadastro_estoque_compartilhado'


@dataclass(frozen=True)
class SharedPriceConfig:
    enabled: bool = False
    calculator_mode: str = 'nominal_profit'
    marketplace_fee_percent: float = 0.0
    tax_percent: float = 0.0
    freight_cost: float = 0.0
    other_sale_fees_percent: float = 0.0
    desired_nominal_profit: float = 0.0
    desired_contribution_margin_percent: float = 0.0
    desired_sale_price: float = 0.0
    supplier_term_days: float = 0.0
    stock_turnover_days: float = 0.0
    promo_discount_percent: float = 0.0
    marketplace_rule_type: str = 'standard'
    marketplace_threshold: float = 0.0
    marketplace_fixed_fee: float = 0.0
    marketplace_capital_days: float = 15.0


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(D(value))
    except Exception:
        return float(default)


def normalize_shared_price_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Normaliza a configuração única de preço para cadastro, estoque e multiloja.

    Também aceita as chaves antigas da calculadora de cadastro para não quebrar
    sessões existentes.
    """
    raw = dict(raw or {})
    mode = str(raw.get('calculator_mode') or 'nominal_profit').strip().lower()
    if mode not in {'nominal_profit', 'contribution_margin', 'fixed_sale_price'}:
        mode = 'nominal_profit'

    nominal_profit = raw.get('desired_nominal_profit', raw.get('fixed_value', 0.0))
    contribution_margin = raw.get('desired_contribution_margin_percent', raw.get('profit_percent', 0.0))
    marketplace_fee = raw.get('marketplace_fee_percent', raw.get('commission_percent', raw.get('discount_percent', 0.0)))
    other_fees = raw.get('other_sale_fees_percent', raw.get('fee_percent', 0.0))

    config = SharedPriceConfig(
        enabled=bool(raw.get('enabled', False)),
        calculator_mode=mode,
        marketplace_fee_percent=_float(marketplace_fee),
        tax_percent=_float(raw.get('tax_percent', 0.0)),
        freight_cost=_float(raw.get('freight_cost', 0.0)),
        other_sale_fees_percent=_float(other_fees),
        desired_nominal_profit=_float(nominal_profit),
        desired_contribution_margin_percent=_float(contribution_margin),
        desired_sale_price=_float(raw.get('desired_sale_price', 0.0)),
        supplier_term_days=_float(raw.get('supplier_term_days', 0.0)),
        stock_turnover_days=_float(raw.get('stock_turnover_days', 0.0)),
        promo_discount_percent=_float(raw.get('promo_discount_percent', 0.0)),
        marketplace_rule_type=str(raw.get('marketplace_rule_type') or 'standard'),
        marketplace_threshold=_float(raw.get('marketplace_threshold', 0.0)),
        marketplace_fixed_fee=_float(raw.get('marketplace_fixed_fee', 0.0)),
        marketplace_capital_days=_float(raw.get('marketplace_capital_days', 15.0), 15.0),
    )
    return {
        'enabled': config.enabled,
        'calculator_mode': config.calculator_mode,
        'marketplace_fee_percent': config.marketplace_fee_percent,
        'tax_percent': config.tax_percent,
        'freight_cost': config.freight_cost,
        'other_sale_fees_percent': config.other_sale_fees_percent,
        'desired_nominal_profit': config.desired_nominal_profit,
        'desired_contribution_margin_percent': config.desired_contribution_margin_percent,
        'desired_sale_price': config.desired_sale_price,
        'supplier_term_days': config.supplier_term_days,
        'stock_turnover_days': config.stock_turnover_days,
        'promo_discount_percent': config.promo_discount_percent,
        'marketplace_rule_type': config.marketplace_rule_type,
        'marketplace_threshold': config.marketplace_threshold,
        'marketplace_fixed_fee': config.marketplace_fixed_fee,
        'marketplace_capital_days': config.marketplace_capital_days,
        # Chaves antigas mantidas para compatibilidade visual/estado.
        'profit_percent': config.desired_contribution_margin_percent,
        'fee_percent': config.other_sale_fees_percent,
        'discount_percent': config.marketplace_fee_percent,
        'fixed_value': config.desired_nominal_profit,
    }


def _inputs(cost: Any, config: dict[str, Any]) -> CalculatorInputs:
    return CalculatorInputs(
        tax_percent=D(config.get('tax_percent', 0)),
        product_cost=D(cost),
        freight_cost=D(config.get('freight_cost', 0)),
        desired_sale_price=D(config.get('desired_sale_price', 0)),
        desired_nominal_profit=D(config.get('desired_nominal_profit', 0)),
        desired_contribution_margin_percent=D(config.get('desired_contribution_margin_percent', 0)),
        supplier_term_days=D(config.get('supplier_term_days', 0)),
        stock_turnover_days=D(config.get('stock_turnover_days', 0)),
        other_sale_fees_percent=D(config.get('other_sale_fees_percent', 0)),
    )


def _rule(config: dict[str, Any], channel: str = DEFAULT_CHANNEL) -> MarketplaceFeeRule:
    return MarketplaceFeeRule(
        marketplace=str(channel or DEFAULT_CHANNEL),
        variation='Calculadora compartilhada',
        fee_percent=D(config.get('marketplace_fee_percent', 0)),
        rule_type=str(config.get('marketplace_rule_type') or 'standard'),
        capital_days=D(config.get('marketplace_capital_days', 15)),
        threshold=D(config.get('marketplace_threshold', 0)),
        fixed_fee=D(config.get('marketplace_fixed_fee', 0)),
    )


def calculate_shared_price(cost: Any, config: dict[str, Any] | None, channel: str = DEFAULT_CHANNEL) -> str:
    normalized = normalize_shared_price_config(config)
    inputs = _inputs(cost, normalized)
    rule = _rule(normalized, channel)
    mode = str(normalized.get('calculator_mode') or 'nominal_profit')
    if inputs.product_cost <= Decimal('0') and mode != 'fixed_sale_price':
        return ''
    if mode == 'contribution_margin':
        result = price_by_contribution_margin(inputs, rule)
    elif mode == 'fixed_sale_price':
        result = simulate_by_fixed_sale_price(inputs, rule)
    else:
        result = price_by_nominal_profit(inputs, rule)
    return money(result.sale_price)


def apply_shared_pricing(
    df: pd.DataFrame,
    cost_column: str,
    output_column: str = 'Preço de venda',
    config: dict[str, Any] | None = None,
    channel: str = DEFAULT_CHANNEL,
) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    if df.empty or cost_column not in df.columns:
        return df.copy().fillna('')
    normalized = normalize_shared_price_config(config)
    out = df.copy().fillna('')
    out[output_column] = out[cost_column].apply(lambda value: calculate_shared_price(value, normalized, channel))
    return out


__all__ = [
    'DEFAULT_CHANNEL',
    'SharedPriceConfig',
    'apply_shared_pricing',
    'calculate_shared_price',
    'normalize_shared_price_config',
]
