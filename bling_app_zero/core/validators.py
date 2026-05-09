from __future__ import annotations

import pandas as pd

from bling_app_zero.core.text import clean_cell, normalize_key


def _has_column(keys: list[str], terms: list[str]) -> bool:
    return any(any(term in key for term in terms) for key in keys)


def _column_has_values(df: pd.DataFrame, column_terms: list[str]) -> bool:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return False
    for column in df.columns:
        key = normalize_key(column)
        if not any(term in key for term in column_terms):
            continue
        series = df[column].astype(str).map(clean_cell)
        if series.map(lambda value: bool(value and normalize_key(value) not in {'nan', 'none', 'null', 'na', 'n/a'})).any():
            return True
    return False


def validate_final_df(df: pd.DataFrame, operation: str) -> list[str]:
    errors: list[str] = []
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return ['O arquivo final ainda está vazio. Confira a origem dos dados antes de baixar.']

    if len(df.columns) == 0:
        return ['O arquivo final não tem colunas. Confira o modelo do Bling antes de baixar.']

    if not _column_has_values(df, [normalize_key(column) for column in df.columns]):
        errors.append('O arquivo final tem colunas, mas parece estar sem dados preenchidos.')

    columns = [str(c) for c in df.columns]
    keys = [normalize_key(c) for c in columns]
    op = normalize_key(operation)

    if op == 'cadastro':
        if not _has_column(keys, ['descricao', 'nome', 'produto']):
            errors.append('Cadastro: falta um campo de nome ou descrição do produto.')
        elif not _column_has_values(df, ['descricao', 'nome', 'produto']):
            errors.append('Cadastro: o campo de nome ou descrição está vazio.')

        if not _has_column(keys, ['preco', 'valor']):
            errors.append('Cadastro: falta um campo de preço ou valor.')
        elif not _column_has_values(df, ['preco', 'valor']):
            errors.append('Cadastro: o campo de preço ou valor está vazio.')

    if op == 'estoque':
        if not _has_column(keys, ['codigo', 'sku', 'referencia']):
            errors.append('Estoque: falta um campo de código, SKU ou referência do produto.')
        elif not _column_has_values(df, ['codigo', 'sku', 'referencia']):
            errors.append('Estoque: o campo de código, SKU ou referência está vazio.')

        if not _has_column(keys, ['estoque', 'balanco', 'quantidade', 'saldo']):
            errors.append('Estoque: falta um campo de saldo, quantidade, balanço ou estoque.')
        elif not _column_has_values(df, ['estoque', 'balanco', 'quantidade', 'saldo']):
            errors.append('Estoque: o campo de saldo, quantidade, balanço ou estoque está vazio.')

    return errors
