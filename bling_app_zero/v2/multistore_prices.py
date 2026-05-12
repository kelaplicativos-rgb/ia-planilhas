from __future__ import annotations

from decimal import Decimal

import pandas as pd

from bling_app_zero.v2.contracts import ModuleResult, ModuleSpec, TablePayload
from bling_app_zero.v2.marketplace_calculator import (
    CalculatorInputs,
    D,
    MarketplaceFeeRule,
    money,
    price_by_contribution_margin,
    price_by_nominal_profit,
    simulate_by_fixed_sale_price,
)

INTERNAL_COST_COLUMN = '_v2_custo_base'
PRICE_COLUMN_CANDIDATES = (INTERNAL_COST_COLUMN, 'Custo', 'Preco de custo', 'Preço de custo', 'Preco Custo', 'Preço Custo')
REQUIRED_ID_COLUMNS = ('IdProduto', 'ID na Loja')
PRICE_OUTPUT_COLUMNS = ('Preco', 'Preço')
PROMO_OUTPUT_COLUMNS = ('Preco Promocional', 'Preço Promocional')

SPECIAL_RULE_BY_CHANNEL = {
    'mercado_livre': {'rule_type': 'meli_79', 'threshold': '79', 'fixed_fee': '5', 'capital_days': '10'},
    'olist': {'rule_type': 'meli_100', 'threshold': '100', 'fixed_fee': '5', 'capital_days': '35'},
    'madeira_madeira': {'rule_type': 'commission_on_freight', 'threshold': '0', 'fixed_fee': '0', 'capital_days': '15'},
    'b2w': {'rule_type': 'b2w_40', 'threshold': '40', 'fixed_fee': '5', 'capital_days': '15'},
    'via_varejo': {'rule_type': 'standard', 'threshold': '0', 'fixed_fee': '0', 'capital_days': '27'},
    'carrefour': {'rule_type': 'standard', 'threshold': '0', 'fixed_fee': '0', 'capital_days': '27'},
    'amazon': {'rule_type': 'standard', 'threshold': '0', 'fixed_fee': '0', 'capital_days': '15'},
    'shopee': {'rule_type': 'standard', 'threshold': '0', 'fixed_fee': '0', 'capital_days': '15'},
    'outro': {'rule_type': 'standard', 'threshold': '0', 'fixed_fee': '0', 'capital_days': '15'},
}


def _find_column(df: pd.DataFrame, candidates: tuple[str, ...]) -> str:
    normalized = {str(column).strip().lower(): str(column) for column in df.columns}
    for candidate in candidates:
        key = candidate.strip().lower()
        if key in normalized:
            return normalized[key]
    return ''


def _decimal_rule(rules: dict, key: str, default: object = '0') -> Decimal:
    return D(rules.get(key, default))


def _is_positive_money(value: object) -> bool:
    return D(value) > Decimal('0')


def _valid_cost_mask(df: pd.DataFrame, cost_col: str) -> pd.Series:
    if cost_col not in df.columns:
        return pd.Series([False] * len(df), index=df.index)
    return df[cost_col].apply(_is_positive_money)


def _sample_invalid_cost_rows(df: pd.DataFrame, cost_col: str, limit: int = 10) -> tuple[str, ...]:
    if cost_col not in df.columns:
        return ()
    mask = ~_valid_cost_mask(df, cost_col)
    rows = [int(index) + 2 for index in df.index[mask].tolist()]
    messages = [f'Custo vazio ou inválido na linha {row}.' for row in rows[:limit]]
    if len(rows) > limit:
        messages.append(f'Custo vazio ou inválido em mais {len(rows) - limit} linha(s).')
    return tuple(messages)


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
    channel = str(profile_channel or 'outro').strip().lower() or 'outro'
    special = SPECIAL_RULE_BY_CHANNEL.get(channel, SPECIAL_RULE_BY_CHANNEL['outro'])
    fee_percent = _decimal_rule(rules, 'marketplace_fee_percent', rules.get('commission_percent', '0'))
    variation = str(rules.get('marketplace_variation') or rules.get('variation') or channel.replace('_', ' ').title())
    return MarketplaceFeeRule(
        marketplace=channel,
        variation=variation,
        fee_percent=fee_percent,
        rule_type=str(rules.get('marketplace_rule_type') or special['rule_type']),
        capital_days=_decimal_rule(rules, 'marketplace_capital_days', special['capital_days']),
        threshold=_decimal_rule(rules, 'marketplace_threshold', special['threshold']),
        fixed_fee=_decimal_rule(rules, 'marketplace_fixed_fee', special['fixed_fee']),
    )


def _promo_price(sale_price: Decimal, rules: dict) -> Decimal:
    discount = _decimal_rule(rules, 'promo_discount_percent') / Decimal('100')
    if discount <= 0:
        return Decimal('0')
    return sale_price * (Decimal('1') - discount)


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

    promo_value = _promo_price(result.sale_price, rules)
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
    else:
        valid_costs = int(_valid_cost_mask(df, cost_col).sum())
        if valid_costs <= 0:
            errors.append('Nenhum custo/preco base valido foi encontrado para calcular.')
            errors.extend(_sample_invalid_cost_rows(df, cost_col, limit=5))
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

    valid_mask = _valid_cost_mask(df, cost_col)
    skipped_rows = int((~valid_mask).sum())
    df = df.loc[valid_mask].copy().fillna('')

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

    fee_rule = _fee_rule(profile.channel, rules)
    message = 'Precos multiloja calculados com calculadora profissional.'
    if skipped_rows:
        message += f' {skipped_rows} linha(s) sem custo valido foram ignoradas para evitar preco zerado.'

    return ModuleResult(
        True,
        payload.with_df(df, stage='calculate'),
        message,
        metrics={
            'rows': len(df),
            'skipped_rows_without_valid_cost': skipped_rows,
            'marketplace': profile.channel,
            'store_id': profile.store_id,
            'calculator_mode': str(rules.get('calculator_mode') or 'nominal_profit'),
            'marketplace_fee_percent': str(fee_rule.fee_percent),
            'marketplace_rule_type': fee_rule.rule_type,
            'marketplace_threshold': str(fee_rule.threshold),
            'marketplace_fixed_fee': str(fee_rule.fixed_fee),
        },
    )


MULTISTORE_PRICE_SPEC = ModuleSpec(
    key='v2_multistore_price_calculator',
    title='Calculadora V2 de Precos Multiloja',
    description='Calcula Preco e Preco Promocional para vinculo produtos multilojas com lucro nominal, margem ou preco fixo.',
    operation='preco',
    stage='calculate',
    version='2.1.3',
    depends_on=('store_profile', 'modelo_multiloja', 'custo_base'),
    provides=('preco_multiloja_calculado',),
    runner=run_multistore_price_calculator,
)

__all__ = ['INTERNAL_COST_COLUMN', 'MULTISTORE_PRICE_SPEC', 'SPECIAL_RULE_BY_CHANNEL', 'run_multistore_price_calculator', 'validate_multistore_payload']
