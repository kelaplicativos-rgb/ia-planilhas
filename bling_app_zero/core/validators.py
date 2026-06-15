from __future__ import annotations

from decimal import Decimal, InvalidOperation

import pandas as pd

from bling_app_zero.core.text import clean_cell, normalize_key

EMPTY_NORMALIZED_VALUES = {'', 'nan', 'none', 'null', 'na', 'n/a'}
CADASTRO_NAME_TERMS = ['descricao', 'descrição', 'nome', 'produto']
CADASTRO_PRICE_TERMS = ['preco', 'preço', 'valor', 'unitario', 'unitário', 'venda']
ESTOQUE_CODE_TERMS = ['codigo', 'código', 'sku', 'referencia', 'referência', 'id_produto']
ESTOQUE_QTY_TERMS = ['estoque', 'balanco', 'balanço', 'quantidade', 'qtd', 'saldo']
PRICE_UPDATE_TERMS = ['preco', 'preço', 'preco_promocional', 'promocional', 'idproduto', 'id_produto', 'id_na_loja', 'loja', 'multiloja']
PRICE_COLUMN_TERMS = ('preco', 'valor', 'unitario', 'venda', 'price')
PRICE_COLUMN_EXCLUSIONS = ('destino', 'canal', 'loja id', 'fornecedor', 'custo', 'compra', 'margem', 'desconto', 'comissao')
PRIMARY_PRICE_COLUMNS = {'preco', 'preco unitario', 'preco venda', 'valor', 'valor venda', 'price'}
PRICE_OPERATION_VALUES = {'atualizacao preco', 'atualizacao precos', 'preco', 'precos', 'price', 'prices'}


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


def _price_columns(df: pd.DataFrame) -> list[str]:
    candidates: list[tuple[int, int, str]] = []
    for index, column in enumerate(df.columns):
        key = normalize_key(column)
        if not key or not any(term in key for term in PRICE_COLUMN_TERMS):
            continue
        if any(term in key for term in PRICE_COLUMN_EXCLUSIONS):
            continue
        priority = 0 if key in PRIMARY_PRICE_COLUMNS else 1
        candidates.append((priority, index, str(column)))
    if not candidates:
        return []
    best_priority = min(priority for priority, _index, _column in candidates)
    return [column for priority, _index, column in sorted(candidates) if priority == best_priority]


def _positive_price(value: object) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    text = clean_cell(value).replace('R$', '').replace('\u00a0', '').replace(' ', '')
    if normalize_key(text) in EMPTY_NORMALIZED_VALUES:
        return False
    if ',' in text and '.' in text:
        if text.rfind(',') > text.rfind('.'):
            text = text.replace('.', '').replace(',', '.')
        else:
            text = text.replace(',', '')
    elif ',' in text:
        text = text.replace('.', '').replace(',', '.')
    try:
        return Decimal(text) > 0
    except (InvalidOperation, ValueError):
        return False


def price_validation_details(df: pd.DataFrame) -> dict[str, object]:
    columns = _price_columns(df) if isinstance(df, pd.DataFrame) else []
    invalid_rows: list[int] = []
    if isinstance(df, pd.DataFrame) and not df.empty and columns:
        for position, (_index, row) in enumerate(df.iterrows(), start=1):
            if not any(_positive_price(row.get(column)) for column in columns):
                invalid_rows.append(position)
    return {
        'price_columns': columns,
        'invalid_rows': invalid_rows,
        'invalid_count': len(invalid_rows),
        'rows': int(len(df)) if isinstance(df, pd.DataFrame) else 0,
    }


def validate_price_update_values(df: pd.DataFrame, *, label: str = 'Atualização de preços') -> list[str]:
    details = price_validation_details(df)
    columns = list(details['price_columns'])
    invalid_rows = list(details['invalid_rows'])
    if not columns:
        return [f'{label}: nenhuma coluna de preço de venda foi encontrada no resultado mapeado.']
    if not invalid_rows:
        return []
    sample = ', '.join(map(str, invalid_rows[:12]))
    suffix = '...' if len(invalid_rows) > 12 else ''
    return [
        f'{label}: {len(invalid_rows)} produto(s) estão com preço vazio, inválido ou igual a zero. '
        f'Linhas: {sample}{suffix}. Corrija o mapeamento ou a origem antes de baixar/enviar.'
    ]


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
    elif _price_columns(df):
        errors.extend(validate_price_update_values(df, label=f'{label} bloqueado'))
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
    """Valida os campos presentes sem classificar ou alterar o modelo anexado."""
    errors: list[str] = []
    has_name = _has_column(keys, CADASTRO_NAME_TERMS)
    has_price = _has_column(keys, CADASTRO_PRICE_TERMS)
    has_code = _has_column(keys, ESTOQUE_CODE_TERMS)
    has_qty = _has_column(keys, ESTOQUE_QTY_TERMS)

    if has_name and not _column_has_values(df, CADASTRO_NAME_TERMS):
        errors.append('Modelo final: o campo de nome ou descrição está vazio.')
    if has_price and not _column_has_values(df, CADASTRO_PRICE_TERMS):
        errors.append('Modelo final: o campo de preço ou valor está vazio.')
    if _price_columns(df):
        errors.extend(validate_price_update_values(df, label='Modelo final bloqueado'))
    if has_qty:
        errors.extend(_validate_estoque(df, keys, label='Modelo final'))
    if not has_name and not has_price and not has_qty and not has_code:
        return errors
    return errors


def validate_final_df(df: pd.DataFrame, operation: str) -> list[str]:
    errors: list[str] = []
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return ['O arquivo final ainda está vazio. Confira a origem dos dados antes de baixar.']
    if len(df.columns) == 0:
        return ['O arquivo final não tem colunas. Confira o modelo antes de baixar.']
    if not _has_any_cell_value(df):
        errors.append('O arquivo final tem colunas, mas parece estar sem dados preenchidos.')
    columns = [str(c) for c in df.columns]
    keys = [normalize_key(c) for c in columns]
    op = normalize_key(operation)
    if op == 'cadastro':
        errors.extend(_validate_cadastro(df, keys))
    elif op == 'estoque':
        errors.extend(_validate_estoque(df, keys))
    elif op in PRICE_OPERATION_VALUES:
        errors.extend(validate_price_update_values(df))
    elif op in {'universal', 'modelo', 'modelo destino', 'planilha', 'wizard cadastro estoque'}:
        errors.extend(_validate_universal(df, keys))
    return errors


__all__ = ['price_validation_details', 'validate_final_df', 'validate_price_update_values']
