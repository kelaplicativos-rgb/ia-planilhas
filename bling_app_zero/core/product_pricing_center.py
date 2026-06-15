from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable

import pandas as pd

from bling_app_zero.core.easy_reprice import calc_easy_promo_price, calc_easy_sale_price, money_or_empty
from bling_app_zero.core.text import normalize_key
from bling_app_zero.v2.marketplace_calculator import (
    CalculatorInputs,
    D,
    MarketplaceFeeRule,
    money,
    price_by_contribution_margin,
    price_by_nominal_profit,
    simulate_by_fixed_sale_price,
)

RESPONSIBLE_FILE = 'bling_app_zero/core/product_pricing_center.py'
DEFAULT_CHANNEL = 'cadastro_estoque_compartilhado'
PRICE_OUTPUT_COLUMN = 'Preço de venda'
PROMO_PRICE_OUTPUT_COLUMN = 'Preço promocional'

PRICE_TARGET_ALIASES = [
    PRICE_OUTPUT_COLUMN,
    'Preço unitário (OBRIGATÓRIO)',
    'Preço unitário',
    'Preço',
    'Preco',
    'Valor',
]
PROMO_PRICE_TARGET_ALIASES = [
    PROMO_PRICE_OUTPUT_COLUMN,
    'Preco Promocional',
    'Preço Promocional',
    'Preço promocional',
    'preco_promocional',
    'preço_promocional',
    'Valor promocional',
    'Preço de oferta',
    'Preço oferta',
    'Valor de oferta',
    'Preço especial',
    'Preço com desconto',
]
PROMO_COLUMN_TERMS = ('promocional', 'promocao', 'oferta', 'especial', 'com desconto', 'sale price', 'promo price')
PRICE_COLUMN_TERMS = ('preco', 'valor', 'price')
COST_STRONG_TERMS = ['preço custo', 'preco custo', 'valor custo', 'custo', 'cost', 'preco compra', 'preço compra', 'valor compra']
COST_WEAK_TERMS = ['valor produto', 'valor', 'preço', 'preco', 'price']
BAD_COST_TERMS = ['venda', 'unitario', 'unitário', 'marketplace', 'comissao', 'comissão', 'taxa', 'lucro', 'promocional']


def promotional_price_columns(columns: Iterable[object]) -> list[str]:
    detected: list[str] = []
    for column in columns:
        name = str(column)
        key = normalize_key(name)
        has_price = any(term in key for term in PRICE_COLUMN_TERMS)
        has_promo = any(term in key for term in PROMO_COLUMN_TERMS)
        if has_price and has_promo and name not in detected:
            detected.append(name)
    return detected


def to_number(value: Any) -> float:
    text = str(value or '').strip()
    if not text:
        return 0.0
    text = text.replace('R$', '').replace('%', '').replace(' ', '')
    text = re.sub(r'[^0-9,.-]+', '', text)
    if not text or text in {'-', ',', '.', '-,', '-.'}:
        return 0.0
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.')
    elif ',' in text:
        text = text.replace(',', '.')
    elif text.count('.') == 1:
        before, after = text.split('.', 1)
        if len(after) == 3 and len(before) <= 3:
            text = before + after
    elif text.count('.') > 1:
        text = text.replace('.', '')
    try:
        return float(text)
    except Exception:
        return 0.0


def normalize_percent(value: Any) -> float:
    number = to_number(value)
    if 0 < number <= 1:
        return number * 100.0
    return number


def calculate_price(cost: float, margin: float = 0.0, tax: float = 0.0, fee: float = 0.0, fixed: float = 0.0, discount: float = 0.0) -> float:
    base = float(cost or 0.0) + float(fixed or 0.0)
    total_percent = float(margin or 0.0) + float(tax or 0.0) + float(fee or 0.0) + float(discount or 0.0)
    if total_percent <= 0:
        return round(base, 2)
    if total_percent >= 95:
        total_percent = 95.0
    divisor = 1 - (total_percent / 100.0)
    return round(base / divisor, 2)


def calculate_product_price(cost: Any, config: dict[str, Any] | None = None) -> float:
    cfg = dict(config or {})
    return calculate_price(
        to_number(cost),
        margin=normalize_percent(cfg.get('margin', cfg.get('margem', 0))),
        tax=normalize_percent(cfg.get('tax', cfg.get('impostos', cfg.get('tax_percent', 0)))),
        fee=normalize_percent(cfg.get('fee', cfg.get('taxa', cfg.get('fee_percent', 0)))),
        fixed=to_number(cfg.get('fixed', cfg.get('custo_fixo', 0))),
        discount=normalize_percent(cfg.get('discount', cfg.get('desconto', 0))),
    )


def apply_pricing(df: pd.DataFrame, cost_column: str, output_column: str, margin: float = 0.0, tax: float = 0.0, fee: float = 0.0, fixed: float = 0.0, discount: float = 0.0) -> pd.DataFrame:
    if df is None or not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    if df.empty or cost_column not in df.columns:
        return df.copy()
    out = df.copy().fillna('')
    out[output_column] = out[cost_column].apply(lambda value: calculate_price(to_number(value), margin, tax, fee, fixed, discount))
    return out


def detect_discount_percent(df: pd.DataFrame | None) -> float:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return 0.0
    columns = {str(column).strip().lower(): column for column in df.columns}
    for key, original_column in columns.items():
        if 'comiss' in key and '%' in key:
            values = [normalize_percent(value) for value in df[original_column].dropna().tolist()]
            values = [value for value in values if value > 0]
            if values:
                return round(max(set(values), key=values.count), 2)
    for key, original_column in columns.items():
        if 'desconto' in key and '%' in key:
            values = [normalize_percent(value) for value in df[original_column].dropna().tolist()]
            values = [value for value in values if value > 0]
            if values:
                return round(max(set(values), key=values.count), 2)
    return 0.0


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
    quick_reprice_mode: str = ''
    quick_markup_percent: float = 0.0
    quick_fixed_addition: float = 0.0
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
    raw = dict(raw or {})
    mode = str(raw.get('calculator_mode') or 'nominal_profit').strip().lower()
    if mode not in {'nominal_profit', 'contribution_margin', 'fixed_sale_price'}:
        mode = 'nominal_profit'
    nominal_profit = raw.get('desired_nominal_profit', raw.get('fixed_value', 0.0))
    contribution_margin = raw.get('desired_contribution_margin_percent', raw.get('profit_percent', 0.0))
    marketplace_fee = raw.get('marketplace_fee_percent', raw.get('commission_percent', raw.get('discount_percent', 0.0)))
    other_fees = raw.get('other_sale_fees_percent', raw.get('fee_percent', 0.0))
    return {
        'enabled': bool(raw.get('enabled', False)),
        'calculator_mode': mode,
        'marketplace_fee_percent': _float(marketplace_fee),
        'tax_percent': _float(raw.get('tax_percent', 0.0)),
        'freight_cost': _float(raw.get('freight_cost', 0.0)),
        'other_sale_fees_percent': _float(other_fees),
        'desired_nominal_profit': _float(nominal_profit),
        'desired_contribution_margin_percent': _float(contribution_margin),
        'desired_sale_price': _float(raw.get('desired_sale_price', 0.0)),
        'supplier_term_days': _float(raw.get('supplier_term_days', 0.0)),
        'stock_turnover_days': _float(raw.get('stock_turnover_days', 0.0)),
        'promo_discount_percent': max(0.0, _float(raw.get('promo_discount_percent', 0.0))),
        'quick_reprice_mode': str(raw.get('quick_reprice_mode') or '').strip().lower(),
        'quick_markup_percent': _float(raw.get('quick_markup_percent', raw.get('tax_percent', 0.0))),
        'quick_fixed_addition': _float(raw.get('quick_fixed_addition', 0.0)),
        'marketplace_rule_type': str(raw.get('marketplace_rule_type') or 'standard'),
        'marketplace_threshold': _float(raw.get('marketplace_threshold', 0.0)),
        'marketplace_fixed_fee': _float(raw.get('marketplace_fixed_fee', 0.0)),
        'marketplace_capital_days': _float(raw.get('marketplace_capital_days', 15.0), 15.0),
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


def calculate_quick_reprice_decimal(cost: Any, config: dict[str, Any] | None) -> Decimal:
    normalized = normalize_shared_price_config(config)
    base = D(cost)
    if base <= Decimal('0'):
        return Decimal('0')
    percent_total = D(normalized.get('quick_markup_percent', 0)) + D(normalized.get('marketplace_fee_percent', 0)) + D(normalized.get('other_sale_fees_percent', 0))
    fixed_total = D(normalized.get('quick_fixed_addition', 0)) + D(normalized.get('freight_cost', 0)) + D(normalized.get('marketplace_fixed_fee', 0))
    return (base * (Decimal('1') + (percent_total / Decimal('100')))) + fixed_total


def calculate_shared_price_decimal(cost: Any, config: dict[str, Any] | None, channel: str = DEFAULT_CHANNEL) -> Decimal:
    normalized = normalize_shared_price_config(config)
    if str(normalized.get('quick_reprice_mode') or '') == 'markup':
        return calculate_quick_reprice_decimal(cost, normalized)
    inputs = _inputs(cost, normalized)
    rule = _rule(normalized, channel)
    mode = str(normalized.get('calculator_mode') or 'nominal_profit')
    if inputs.product_cost <= Decimal('0') and mode != 'fixed_sale_price':
        return Decimal('0')
    if mode == 'contribution_margin':
        result = price_by_contribution_margin(inputs, rule)
    elif mode == 'fixed_sale_price':
        result = simulate_by_fixed_sale_price(inputs, rule)
    else:
        result = price_by_nominal_profit(inputs, rule)
    return result.sale_price


def calculate_shared_price(cost: Any, config: dict[str, Any] | None, channel: str = DEFAULT_CHANNEL) -> str:
    value = calculate_shared_price_decimal(cost, config, channel)
    return money(value) if value > Decimal('0') else ''


def calculate_promotional_price_from_sale(sale_price: Any, config: dict[str, Any] | None) -> str:
    normalized = normalize_shared_price_config(config)
    discount = D(normalized.get('promo_discount_percent', 0))
    sale = D(sale_price)
    if sale <= Decimal('0') or discount <= Decimal('0'):
        return ''
    promo = sale * (Decimal('1') - (discount / Decimal('100')))
    return money(promo) if promo > Decimal('0') else ''


def apply_shared_pricing(df: pd.DataFrame, cost_column: str, output_column: str = PRICE_OUTPUT_COLUMN, config: dict[str, Any] | None = None, channel: str = DEFAULT_CHANNEL, promo_output_column: str = PROMO_PRICE_OUTPUT_COLUMN) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    if df.empty or cost_column not in df.columns:
        return df.copy().fillna('')
    normalized = normalize_shared_price_config(config)
    out = df.copy().fillna('')
    sale_values = out[cost_column].apply(lambda value: calculate_shared_price_decimal(value, normalized, channel))
    out[output_column] = sale_values.apply(lambda value: money(value) if value > Decimal('0') else '')
    promo_discount = D(normalized.get('promo_discount_percent', 0))
    out[promo_output_column] = sale_values.apply(lambda value: calculate_promotional_price_from_sale(value, normalized)) if promo_discount > Decimal('0') else ''
    return out


@dataclass(frozen=True)
class PricePluginResult:
    df: pd.DataFrame
    applied: bool
    source_column: str = ''
    output_column: str = PRICE_OUTPUT_COLUMN
    promo_output_column: str = PROMO_PRICE_OUTPUT_COLUMN
    message: str = ''


def _column_score_for_cost(column: str) -> int:
    text = str(column or '').lower()
    score = 0
    for term in COST_STRONG_TERMS:
        if term in text:
            score += 100
    for term in COST_WEAK_TERMS:
        if term in text:
            score += 35
    for term in BAD_COST_TERMS:
        if term in text:
            score -= 60
    return score


def best_cost_column(columns: Iterable[str]) -> str:
    normalized = [str(column) for column in columns]
    if not normalized:
        return ''
    best_column, best_score = max([(column, _column_score_for_cost(column)) for column in normalized], key=lambda item: item[1])
    return best_column if best_score > 0 else normalized[0]


def apply_price_aliases(df: pd.DataFrame, calculated_column: str = PRICE_OUTPUT_COLUMN, aliases: Iterable[str] | None = None) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty or calculated_column not in df.columns:
        return df
    out = df.copy().fillna('')
    calculated_values = out[calculated_column]
    for column in list(aliases or PRICE_TARGET_ALIASES):
        out[str(column)] = calculated_values
    return out


def _non_blank_mask(series: pd.Series) -> pd.Series:
    return series.fillna('').astype(str).str.strip().ne('')


def apply_promotional_price_aliases(df: pd.DataFrame, calculated_column: str = PROMO_PRICE_OUTPUT_COLUMN, aliases: Iterable[str] | None = None) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty or calculated_column not in df.columns:
        return df
    out = df.copy().fillna('')
    calculated_values = out[calculated_column]
    calculated_mask = _non_blank_mask(calculated_values)
    dynamic_aliases = promotional_price_columns(out.columns)
    all_aliases = list(dict.fromkeys([*(aliases or PROMO_PRICE_TARGET_ALIASES), *dynamic_aliases]))

    # Sem desconto promocional calculado, nunca apaga o valor que veio da origem/modelo.
    if not bool(calculated_mask.any()):
        return out

    for column in all_aliases:
        name = str(column)
        if name not in out.columns:
            out[name] = ''
        out.loc[calculated_mask, name] = calculated_values.loc[calculated_mask]
    return out


def _apply_easy_pricing(df: pd.DataFrame, cost_column: str, output_column: str, promo_output_column: str, config: dict[str, Any]) -> pd.DataFrame:
    out = df.copy().fillna('')
    existing_promo: dict[str, pd.Series] = {
        column: out[column].copy()
        for column in promotional_price_columns(out.columns)
        if column in out.columns
    }
    sale_values = out[cost_column].apply(lambda value: calc_easy_sale_price(value, config))
    promo_percent = config.get('promo_discount_percent', 0)
    out[output_column] = sale_values.apply(money_or_empty)
    if float(promo_percent or 0) > 0:
        out[promo_output_column] = sale_values.apply(lambda value: money_or_empty(calc_easy_promo_price(value, promo_percent)))
    elif promo_output_column not in out.columns:
        out[promo_output_column] = ''
    for column, values in existing_promo.items():
        out[column] = values
    return out


def apply_price_calculator_plugin(df: pd.DataFrame, *, enabled: bool, config: dict[str, Any] | None, cost_column: str | None = None, output_column: str = PRICE_OUTPUT_COLUMN, channel: str = 'shared_price_plugin', aliases: Iterable[str] | None = None, promo_output_column: str = PROMO_PRICE_OUTPUT_COLUMN, promo_aliases: Iterable[str] | None = None) -> PricePluginResult:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return PricePluginResult(df=df, applied=False, message='Origem vazia ou inválida.')
    out = df.copy().fillna('')
    normalized_config = normalize_shared_price_config(config)
    if not enabled or not bool(normalized_config.get('enabled', False)):
        return PricePluginResult(df=out, applied=False, message='Calculadora desativada.')
    columns = [str(column) for column in out.columns]
    selected_cost_column = str(cost_column or '').strip() or best_cost_column(columns)
    if not selected_cost_column or selected_cost_column not in out.columns:
        return PricePluginResult(df=out, applied=False, message='Coluna de custo não encontrada.')
    if str(normalized_config.get('quick_reprice_mode') or '') in {'markup', 'net_margin'}:
        priced = _apply_easy_pricing(out, selected_cost_column, output_column, promo_output_column, normalized_config)
    else:
        priced = apply_shared_pricing(out, selected_cost_column, output_column, normalized_config, channel, promo_output_column)
    priced = apply_price_aliases(priced, output_column, aliases)
    priced = apply_promotional_price_aliases(priced, promo_output_column, promo_aliases)
    return PricePluginResult(df=priced, applied=True, source_column=selected_cost_column, output_column=output_column, promo_output_column=promo_output_column, message=f'Calculadora aplicada usando a coluna "{selected_cost_column}".')


__all__ = [
    'BAD_COST_TERMS', 'COST_STRONG_TERMS', 'COST_WEAK_TERMS', 'DEFAULT_CHANNEL',
    'PRICE_OUTPUT_COLUMN', 'PRICE_TARGET_ALIASES', 'PROMO_PRICE_OUTPUT_COLUMN',
    'PROMO_PRICE_TARGET_ALIASES', 'PricePluginResult', 'SharedPriceConfig',
    'apply_price_aliases', 'apply_price_calculator_plugin', 'apply_pricing',
    'apply_promotional_price_aliases', 'apply_shared_pricing', 'best_cost_column',
    'calculate_price', 'calculate_product_price', 'calculate_promotional_price_from_sale',
    'calculate_quick_reprice_decimal', 'calculate_shared_price',
    'calculate_shared_price_decimal', 'detect_discount_percent', 'normalize_percent',
    'normalize_shared_price_config', 'promotional_price_columns', 'to_number',
]
