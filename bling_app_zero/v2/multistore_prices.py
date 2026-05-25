from __future__ import annotations

from decimal import Decimal

import pandas as pd

from bling_app_zero.core.price_calculator_plugin import PRICE_OUTPUT_COLUMN, apply_price_calculator_plugin
from bling_app_zero.v2.contracts import ModuleResult, ModuleSpec, TablePayload
from bling_app_zero.v2.marketplace_calculator import D, money

INTERNAL_COST_COLUMN = '_v2_custo_base'
PRICE_COLUMN_CANDIDATES = (INTERNAL_COST_COLUMN, 'Custo', 'Preco de custo', 'Preço de custo', 'Preco Custo', 'Preço Custo')
REQUIRED_ID_COLUMNS = ('IdProduto', 'ID na Loja')
PRICE_OUTPUT_COLUMNS = ('Preco', 'Preço')
PROMO_OUTPUT_COLUMNS = ('Preco Promocional', 'Preço Promocional')

# Regras genéricas por canal lógico. Mantém compatibilidade com chaves antigas,
# mas não força nomes comerciais na experiência white-label.
GENERIC_RULE_BY_CHANNEL = {
    'canal_1': {'rule_type': 'standard', 'threshold': '0', 'fixed_fee': '0', 'capital_days': '15'},
    'canal_2': {'rule_type': 'standard', 'threshold': '0', 'fixed_fee': '0', 'capital_days': '15'},
    'canal_3': {'rule_type': 'standard', 'threshold': '0', 'fixed_fee': '0', 'capital_days': '15'},
    'outro': {'rule_type': 'standard', 'threshold': '0', 'fixed_fee': '0', 'capital_days': '15'},
    # Compatibilidade silenciosa com perfis antigos salvos em sessão.
    'mercado_livre': {'rule_type': 'standard', 'threshold': '0', 'fixed_fee': '0', 'capital_days': '15'},
    'olist': {'rule_type': 'standard', 'threshold': '0', 'fixed_fee': '0', 'capital_days': '15'},
    'madeira_madeira': {'rule_type': 'standard', 'threshold': '0', 'fixed_fee': '0', 'capital_days': '15'},
    'b2w': {'rule_type': 'standard', 'threshold': '0', 'fixed_fee': '0', 'capital_days': '15'},
    'via_varejo': {'rule_type': 'standard', 'threshold': '0', 'fixed_fee': '0', 'capital_days': '15'},
    'carrefour': {'rule_type': 'standard', 'threshold': '0', 'fixed_fee': '0', 'capital_days': '15'},
    'amazon': {'rule_type': 'standard', 'threshold': '0', 'fixed_fee': '0', 'capital_days': '15'},
    'shopee': {'rule_type': 'standard', 'threshold': '0', 'fixed_fee': '0', 'capital_days': '15'},
}
SPECIAL_RULE_BY_CHANNEL = GENERIC_RULE_BY_CHANNEL


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


def _channel_rule_defaults(profile_channel: str, rules: dict) -> dict:
    channel = str(profile_channel or 'outro').strip().lower() or 'outro'
    special = GENERIC_RULE_BY_CHANNEL.get(channel, GENERIC_RULE_BY_CHANNEL['outro'])
    return {
        'marketplace_rule_type': str(rules.get('marketplace_rule_type') or special['rule_type']),
        'marketplace_capital_days': str(rules.get('marketplace_capital_days') or special['capital_days']),
        'marketplace_threshold': str(rules.get('marketplace_threshold') or special['threshold']),
        'marketplace_fixed_fee': str(rules.get('marketplace_fixed_fee') or special['fixed_fee']),
    }


def _promo_price(sale_price: Decimal, rules: dict) -> Decimal:
    discount = _decimal_rule(rules, 'promo_discount_percent') / Decimal('100')
    if discount <= 0:
        return Decimal('0')
    return sale_price * (Decimal('1') - discount)


def validate_multistore_payload(payload: TablePayload) -> tuple[bool, tuple[str, ...]]:
    df = payload.df
    if not isinstance(df, pd.DataFrame) or df.empty:
        return False, ('Planilha de preços vazia.',)
    errors: list[str] = []
    for required in REQUIRED_ID_COLUMNS:
        if not _find_column(df, (required,)):
            errors.append(f'Coluna obrigatória ausente: {required}')
    if not (_find_column(df, PRICE_OUTPUT_COLUMNS) or _find_column(df, PROMO_OUTPUT_COLUMNS)):
        errors.append('Modelo precisa ter coluna de preço ou preço promocional.')
    return not errors, tuple(errors)


def _pricing_rules_for_plugin(profile_channel: str, rules: dict) -> dict:
    output = dict(rules or {})
    output.update(_channel_rule_defaults(profile_channel, output))
    output['enabled'] = True
    return output


def _has_valid_costs(df: pd.DataFrame, cost_col: str) -> bool:
    return bool(cost_col and cost_col in df.columns and int(_valid_cost_mask(df, cost_col).sum()) > 0)


def run_multistore_price_calculator(payload: TablePayload) -> ModuleResult:
    ok, errors = validate_multistore_payload(payload)
    if not ok:
        return ModuleResult(False, payload, 'Planilha de preços inválida.', errors=errors)

    df = payload.df.copy().fillna('')
    profile = payload.store_profile
    rules = {**profile.pricing_rules, **dict(payload.config.get('pricing_rules', {}))}
    cost_col = _find_column(df, PRICE_COLUMN_CANDIDATES)
    price_col = _find_column(df, PRICE_OUTPUT_COLUMNS)
    promo_col = _find_column(df, PROMO_OUTPUT_COLUMNS)

    if not _has_valid_costs(df, cost_col):
        message = 'Nenhum custo/preço base válido foi encontrado. A calculadora foi pulada e a planilha seguirá com os preços existentes no modelo.'
        return ModuleResult(
            True,
            payload.with_df(df, stage='calculate'),
            message,
            metrics={
                'rows': len(df),
                'skipped_rows_without_valid_cost': len(df),
                'channel': profile.channel,
                'store_id': profile.store_id,
                'calculator_mode': str(rules.get('calculator_mode') or 'nominal_profit'),
                'calculator_skipped': 'missing_valid_cost',
                'plugin': 'price_calculator_plugin',
            },
        )

    valid_mask = _valid_cost_mask(df, cost_col)
    skipped_rows = int((~valid_mask).sum())
    df = df.loc[valid_mask].copy().fillna('')

    plugin_result = apply_price_calculator_plugin(
        df,
        enabled=True,
        config=_pricing_rules_for_plugin(profile.channel, rules),
        cost_column=cost_col,
        output_column=PRICE_OUTPUT_COLUMN,
        channel=str(profile.channel or 'canal'),
        aliases=(PRICE_OUTPUT_COLUMN,),
    )
    if not plugin_result.applied:
        return ModuleResult(False, payload.with_df(df, stage='calculate'), plugin_result.message or 'Não foi possível aplicar a calculadora.', errors=(plugin_result.message,))

    df = plugin_result.df.copy().fillna('')
    if price_col:
        df[price_col] = df[PRICE_OUTPUT_COLUMN]
    if promo_col:
        df[promo_col] = [money(_promo_price(D(value), rules)) if _promo_price(D(value), rules) else '' for value in df[PRICE_OUTPUT_COLUMN].tolist()]
    if PRICE_OUTPUT_COLUMN in df.columns and PRICE_OUTPUT_COLUMN not in set(PRICE_OUTPUT_COLUMNS):
        df = df.drop(columns=[PRICE_OUTPUT_COLUMN])

    for column, value in profile.field_defaults.items():
        if column in df.columns:
            df[column] = str(value)

    message = 'Preços calculados com a calculadora plugável.'
    if skipped_rows:
        message += f' {skipped_rows} linha(s) sem custo válido foram ignoradas para evitar preço zerado.'

    normalized_rules = _pricing_rules_for_plugin(profile.channel, rules)
    return ModuleResult(
        True,
        payload.with_df(df, stage='calculate'),
        message,
        metrics={
            'rows': len(df),
            'skipped_rows_without_valid_cost': skipped_rows,
            'channel': profile.channel,
            'store_id': profile.store_id,
            'calculator_mode': str(rules.get('calculator_mode') or 'nominal_profit'),
            'marketplace_fee_percent': str(rules.get('marketplace_fee_percent') or rules.get('commission_percent') or '0'),
            'marketplace_rule_type': str(normalized_rules.get('marketplace_rule_type') or 'standard'),
            'marketplace_threshold': str(normalized_rules.get('marketplace_threshold') or '0'),
            'marketplace_fixed_fee': str(normalized_rules.get('marketplace_fixed_fee') or '0'),
            'plugin': 'price_calculator_plugin',
        },
    )


MULTISTORE_PRICE_SPEC = ModuleSpec(
    key='v2_multistore_price_calculator',
    title='Calculadora plugável de preços',
    description='Calcula preço e preço promocional para atualização por loja/canal com lucro nominal, margem ou preço fixo.',
    operation='preco',
    stage='calculate',
    version='2.2.0',
    depends_on=('store_profile', 'modelo_precos', 'custo_base'),
    provides=('preco_calculado',),
    runner=run_multistore_price_calculator,
)

__all__ = ['INTERNAL_COST_COLUMN', 'MULTISTORE_PRICE_SPEC', 'SPECIAL_RULE_BY_CHANNEL', 'GENERIC_RULE_BY_CHANNEL', 'run_multistore_price_calculator', 'validate_multistore_payload']
