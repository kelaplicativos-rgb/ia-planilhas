from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pandas as pd

from bling_app_zero.v2.price_math import parse_money
from bling_app_zero.v2.price_multistore.matcher import find_column


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    message: str
    column: str = ''
    row: int | None = None


ID_PRODUCT = ('IdProduto', 'ID Produto')
ID_STORE = ('ID na Loja', 'Id na Loja', 'ID Anuncio', 'ID Anúncio')
PRICE_COLUMNS = ('Preço', 'Preco')
PROMO_COLUMNS = ('Preço Promocional', 'Preco Promocional')


def validate_before_calculation(df: pd.DataFrame) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not isinstance(df, pd.DataFrame) or df.empty:
        return [ValidationIssue('erro', 'Planilha multiloja vazia.')]

    id_product = find_column(df, ID_PRODUCT)
    id_store = find_column(df, ID_STORE)
    price_col = find_column(df, PRICE_COLUMNS)
    promo_col = find_column(df, PROMO_COLUMNS)

    if not id_product:
        issues.append(ValidationIssue('erro', 'Coluna obrigatoria IdProduto ausente.'))
    if not id_store:
        issues.append(ValidationIssue('erro', 'Coluna obrigatoria ID na Loja ausente.'))
    if not price_col and not promo_col:
        issues.append(ValidationIssue('erro', 'A planilha precisa ter Preço ou Preço Promocional.'))

    for column in [id_product, id_store]:
        if column and column in df.columns:
            empty_rows = [int(i) + 2 for i, value in enumerate(df[column].tolist()) if not str(value or '').strip()]
            for row in empty_rows[:10]:
                issues.append(ValidationIssue('erro', f'{column} vazio na linha {row}.', column, row))
            if len(empty_rows) > 10:
                issues.append(ValidationIssue('erro', f'{column} tem mais {len(empty_rows) - 10} linha(s) vazia(s).', column))

    return issues


def validate_after_calculation(df: pd.DataFrame) -> list[ValidationIssue]:
    issues = validate_before_calculation(df)
    if not isinstance(df, pd.DataFrame) or df.empty:
        return issues
    price_col = find_column(df, PRICE_COLUMNS)
    promo_col = find_column(df, PROMO_COLUMNS)
    if price_col:
        for index, value in enumerate(df[price_col].tolist()):
            price = parse_money(value)
            if price <= Decimal('0'):
                issues.append(ValidationIssue('erro', f'Preço inválido na linha {index + 2}.', price_col, index + 2))
    if price_col and promo_col:
        for index, row in df[[price_col, promo_col]].fillna('').iterrows():
            promo_text = str(row[promo_col] or '').strip()
            if not promo_text:
                continue
            if parse_money(promo_text) > parse_money(row[price_col]):
                issues.append(ValidationIssue('erro', f'Preço Promocional maior que Preço na linha {int(index) + 2}.', promo_col, int(index) + 2))
    return issues


def has_blocking_errors(issues: list[ValidationIssue]) -> bool:
    return any(issue.severity == 'erro' for issue in issues)


__all__ = ['ValidationIssue', 'has_blocking_errors', 'validate_after_calculation', 'validate_before_calculation']
