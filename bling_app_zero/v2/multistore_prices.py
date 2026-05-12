from __future__ import annotations

from decimal import Decimal

import pandas as pd

from bling_app_zero.v2.contracts import ModuleResult, ModuleSpec, TablePayload
from bling_app_zero.v2.marketplace_calculator import (
    CalculatorInputs,
    MarketplaceFeeRule,
    calculate_promo_price,
    money,
    price_by_contribution_margin,
    price_by_nominal_profit,
    simulate_by_fixed_sale_price,
)
from bling_app_zero.v2.price_math import D

INTERNAL_COST_COLUMN = '_v2_custo_base'
PRICE_COLUMN_CANDIDATES = (INTERNAL_COST_COLUMN, 'Custo', 'Preco de custo', 'Preço de custo', 'Preco Custo', 'Preço Custo')
REQUIRED_ID_COLUMNS = ('IdProduto', 'ID na Loja')
PRICE_OUTPUT_COLUMNS = ('Preco', 'Preço')
PROMO_OUTPUT_COLUMNS = ('Preco Promocional', 'Preço Promocional')


def _find_column(df: pd.DataFrame, candidates: tuple[str, ...]) -> str:
    normalized = {str(column).strip().lower(): str(column) for column in df.columns}
    for candidate in candidates:
        key = candidate.strip().lower()
        if key in normalized:
            return normalized[key]
    return ''


def _decimal_rule(rules: dict, key: str, default: str = '0') -> Decimal:
    return D(rules.get(key, default))


def _inputs_for_cost(cost_value: object, rules: dict) -> CalculatorInputs:
    return CalculatorInputs(
        tax_percent=_decimal_rule(rules, 'tax_percent'),
        product_cost=D(cost_value),
        freight_cost=_decimal_rule(rules, 'freight_cost'),
        desired_sale_price=_decimal_rule(rules, 'desired_sale_price'),
        desired_nominal_profit=_decimal_rule(rules, 'desired_nominal_profit', rules.get('profit_value', '0')),
        desired_contribution_margin_percent=_decimal_rule(rules, 'desired_contribution_margin_percent', rules.get('profit_percent', '0')),
        supplier_term_days=_decimal_rule(rules, 'supplier_term_days'),
        stock_turnover_days=_decimal_rule(rules, 'stock_turnover_days'),
        other_sale_fees_percent=_decimal_rule(rules, 'other_sale_fees_percent'),
    )


def _fee_rule(profile_channel: str, rules: dict) -> MarketplaceFeeRule:
    fee_percent = _decimal_rule(rules, 'marketplace_fee_percent', rules.get('commission_percent', '0'))
    variation = str(rules.get('marketplace_variation') or rules.get('variation') or profile_channel or 'Marketplace')
    return MarketplaceFeeRule(str(profile_channel or 'marketplace'), variation, fee_percent)


def _calculate_price_for_cost(cost_value: object, profile_channel: str, rules: dict) -> tuple[str, str]:
    inputs = _inputs_for_cost(cost_value, rules)
    rule = _fee_rule(profile_channel, rules)
    mode = str(rules.get('calculator_mode') or 'nominal_profit').strip().lower()

    if mode == 'contribution_margin':
        result = price_by_contribution_margin(inputs, rule)
    elif mode == 'fixed_sale_price':
        result = simulate_by_fixed_sale_price(inputs, rule)
    else:
        result = price_by_nominal_profit(inputs, rule)

    promo_discount = _decimal_rule(rules, 'promo_discount_percent')
    promo_value = calculate_promo_price(result.sale_price, {'promo_discount_percent': promo_discount})
    return money(result.sale_price), money(promo_value) if promo_value else ''


def validate_multistore_payload(payload: TablePayload) -> tuple[bool, tuple[str, ...]]:
    df = payload.df
    if not isinstance(df, pd.DataFrame) or df.empty:
        return False, ('Planilha multiloja vazia.',)
    errors: list[str] = []
    for required in REQUIRED_ID_COLUMNS:
        if not _find_column(df, (required,)):
            errors.append(f'Coluna obrigatoria ausente: {required}')
    cost_col = _find_column(df, PRICE_COLUMN_CANDIDATES)
    if not cost_col:
        errors.append('Coluna de custo/preco base ausente.')
    elif not any(str(value or '').strip() for value in df[cost_col].tolist()):
        errors.append('Coluna de custo/preco base esta vazia.')
    if not (_find_column(df, PRICE_OUTPUT_COLUMNS) or _find_column(df, PROMO_OUTPUT_COLUMNS)):
        errors.append('Modelo precisa ter coluna Preco ou Preco Promocional.')
    return not errors, tuple(errors)


def run_multistore_price_calculator(payload: TablePayload) -> ModuleResult:
    ok, errors = validate_multistore_payload(payload)
    if not ok:
        return ModuleResult(False, payload, 'Planilha multiloja invalida.', errors=errors)

    df = payload.df.copy().fillna('')
    profile = payload.store_profile
    rules = {**profile.pricing_rules, **dict(payload.config.get('pricing_rules', {}))}
    cost_col = _find_column(df, PRICE_COLUMN_CANDIDATES)
    price_col = _find_column(df, PRICE_OUTPUT_COLUMNS)
    promo_col = _find_column(df, PROMO_OUTPUT_COLUMNS)

    calculated_prices: list[str] = []
    promo_prices: list[str] = []
    for value in df[cost_col].tolist():
        price, promo = _calculate_price_for_cost(value, profile.channel, rules)
        calculated_prices.append(price)
        promo_prices.append(promo)

    if price_col:
        df[price_col] = calculated_prices
    if promo_col:
        df[promo_col] = promo_prices

    for column, value in profile.field_defaults.items():
        if column in df.columns:
            df[column] = str(value)

    return ModuleResult(
        True,
        payload.with_df(df, stage='calculate'),
        'Precos multiloja calculados com calculadora profissional.',
        metrics={
            'rows': len(df),
            'marketplace': profile.channel,
            'store_id': profile.store_id,
            'calculator_mode': str(rules.get('calculator_mode') or 'nominal_profit'),
            'marketplace_fee_percent': str(rules.get('marketplace_fee_percent') or rules.get('commission_percent') or '0'),
        },
    )


MULTISTORE_PRICE_SPEC = ModuleSpec(
    key='v2_multistore_price_calculator',
    title='Calculadora V2 de Precos Multiloja',
    description='Calcula Preco e Preco Promocional para vinculo produtos multilojas com lucro nominal, margem ou preco fixo.',
    operation='preco',
    stage='calculate',
    version='2.1.0',
    depends_on=('store_profile', 'modelo_multiloja', 'custo_base'),
    provides=('preco_multiloja_calculado',),
    runner=run_multistore_price_calculator,
)

__all__ = ['INTERNAL_COST_COLUMN', 'MULTISTORE_PRICE_SPEC', 'run_multistore_price_calculator', 'validate_multistore_payload']
