from __future__ import annotations

import pandas as pd

from bling_app_zero.core.text import clean_cell, normalize_key

EMPTY_NORMALIZED_VALUES = {'', 'nan', 'none', 'null', 'na', 'n/a'}
CADASTRO_NAME_TERMS = ['descricao', 'descrição', 'nome', 'produto']
CADASTRO_PRICE_TERMS = ['preco', 'preço', 'valor', 'unitario', 'unitário', 'venda']
ESTOQUE_CODE_TERMS = ['codigo', 'código', 'sku', 'referencia', 'referência', 'id_produto']
ESTOQUE_QTY_TERMS = ['estoque', 'balanco', 'balanço', 'quantidade', 'qtd', 'saldo']


def _has_column(keys: list[str], terms: list[str]) -> bool:
    normalized_terms = [normalize_key(term) for term in terms]
    return any(any(term in key for term in normalized_terms) for key in keys)


def _column_has_values(df: pd.DataFrame, column_terms: list[str]) -> bool:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return False
    normalized_terms = [normalize_key(term) for term in column_terms]
    for column in df.columns:
        key = normalize_key(column)
        if not any(term in key for term in normalized_terms):
            continue
        series = df[column].astype(str).map(clean_cell)
        if series.map(lambda value: normalize_key(value) not in EMPTY_NORMALIZED_VALUES).any():
            return True
    return False


def _has_any_cell_value(df: pd.DataFrame) -> bool:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return False
    for column in df.columns:
        series = df[column].astype(str).map(clean_cell)
        if series.map(lambda value: normalize_key(value) not in EMPTY_NORMALIZED_VALUES).any():
            return True
    return False


def _validate_cadastro(df: pd.DataFrame, keys: list[str], *, label: str = 'Cadastro') -> list[str]:
    errors: list[str] = []

    if not _has_column(keys, CADASTRO_NAME_TERMS):
        errors.append(f'{label}: falta um campo de nome ou descrição do produto.')
    elif not _column_has_values(df, CADASTRO_NAME_TERMS):
        errors.append(f'{label}: o campo de nome ou descrição está vazio.')

    if not _has_column(keys, CADASTRO_PRICE_TERMS):
        errors.append(f'{label}: falta um campo de preço ou valor.')
    elif not _column_has_values(df, CADASTRO_PRICE_TERMS):
        errors.append(f'{label}: o campo de preço ou valor está vazio.')

    return errors


def _validate_estoque(df: pd.DataFrame, keys: list[str], *, label: str = 'Estoque') -> list[str]:
    errors: list[str] = []

    if not _has_column(keys, ESTOQUE_CODE_TERMS):
        errors.append(f'{label}: falta um campo de código, SKU ou referência do produto.')
    elif not _column_has_values(df, ESTOQUE_CODE_TERMS):
        errors.append(f'{label}: o campo de código, SKU ou referência está vazio.')

    if not _has_column(keys, ESTOQUE_QTY_TERMS):
        errors.append(f'{label}: falta um campo de saldo, quantidade, balanço ou estoque.')
    elif not _column_has_values(df, ESTOQUE_QTY_TERMS):
        errors.append(f'{label}: o campo de saldo, quantidade, balanço ou estoque está vazio.')

    return errors


def _validate_universal(df: pd.DataFrame, keys: list[str]) -> list[str]:
    """Valida o modelo universal pelo contrato real de colunas anexado pelo usuário.

    O fluxo universal não deve cair no "vale tudo". Ele precisa reconhecer se o
    modelo anexado parece cadastro, estoque ou híbrido e aplicar as proteções
    compatíveis sem forçar uma operação visual antiga.
    """
    errors: list[str] = []
    looks_like_cadastro = _has_column(keys, CADASTRO_NAME_TERMS) or _has_column(keys, CADASTRO_PRICE_TERMS)
    looks_like_estoque = _has_column(keys, ESTOQUE_CODE_TERMS) or _has_column(keys, ESTOQUE_QTY_TERMS)

    if looks_like_cadastro:
        errors.extend(_validate_cadastro(df, keys, label='Modelo final'))

    if looks_like_estoque:
        errors.extend(_validate_estoque(df, keys, label='Modelo final'))

    if not looks_like_cadastro and not looks_like_estoque:
        errors.append(
            'Modelo final: não consegui identificar campos principais de cadastro ou estoque no modelo anexado. '
            'Confira se as colunas do modelo estão corretas antes de baixar.'
        )

    return errors


def validate_final_df(df: pd.DataFrame, operation: str) -> list[str]:
    errors: list[str] = []
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return ['O arquivo final ainda está vazio. Confira a origem dos dados antes de baixar.']

    if len(df.columns) == 0:
        return ['O arquivo final não tem colunas. Confira o modelo do Bling antes de baixar.']

    if not _has_any_cell_value(df):
        errors.append('O arquivo final tem colunas, mas parece estar sem dados preenchidos.')

    columns = [str(c) for c in df.columns]
    keys = [normalize_key(c) for c in columns]
    op = normalize_key(operation)

    if op == 'cadastro':
        errors.extend(_validate_cadastro(df, keys))
    elif op == 'estoque':
        errors.extend(_validate_estoque(df, keys))
    elif op in {'universal', 'modelo', 'modelo_destino', 'planilha', 'wizard_cadastro_estoque'}:
        errors.extend(_validate_universal(df, keys))

    return errors
