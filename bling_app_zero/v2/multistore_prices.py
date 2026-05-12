from __future__ import annotations

import pandas as pd

from bling_app_zero.v2.contracts import ModuleResult, ModuleSpec, TablePayload
from bling_app_zero.v2.price_math import calculate_marketplace_price, calculate_promo_price, money_ptbr

PRICE_COLUMN_CANDIDATES = ('Custo', 'Preco de custo', 'Preço de custo', 'Preco Custo', 'Preço Custo', 'Preco', 'Preço')
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


def validate_multistore_payload(payload: TablePayload) -> tuple[bool, tuple[str, ...]]:
    df = payload.df
    if not isinstance(df, pd.DataFrame) or df.empty:
        return False, ('Planilha multiloja vazia.',)
    errors: list[str] = []
    for required in REQUIRED_ID_COLUMNS:
        if not _find_column(df, (required,)):
            errors.append(f'Coluna obrigatoria ausente: {required}')
    if not _find_column(df, PRICE_COLUMN_CANDIDATES):
        errors.append('Coluna de custo/preco base ausente.')
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
        price = calculate_marketplace_price(value, rules)
        promo = calculate_promo_price(price, rules)
        calculated_prices.append(money_ptbr(price))
        promo_prices.append(money_ptbr(promo) if promo else '')

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
        'Precos multiloja calculados.',
        metrics={'rows': len(df), 'marketplace': profile.channel, 'store_id': profile.store_id},
    )


MULTISTORE_PRICE_SPEC = ModuleSpec(
    key='v2_multistore_price_calculator',
    title='Calculadora V2 de Precos Multiloja',
    description='Calcula Preco e Preco Promocional para vinculo produtos multilojas.',
    operation='preco',
    stage='calculate',
    version='2.0.0',
    depends_on=('store_profile', 'modelo_multiloja'),
    provides=('preco_multiloja_calculado',),
    runner=run_multistore_price_calculator,
)

__all__ = ['MULTISTORE_PRICE_SPEC', 'run_multistore_price_calculator', 'validate_multistore_payload']
