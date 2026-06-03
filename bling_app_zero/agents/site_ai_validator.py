from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

import pandas as pd

STORE_BRAND_TERMS = {
    'mega center',
    'mega center eletronicos',
    'mega center eletrônicos',
    'megacenter',
    'stoqui',
    'loja',
}


@dataclass(frozen=True)
class SmartScanQuality:
    rows: int
    columns: int
    score: int
    good_rows: int
    missing_price: int
    missing_description: int
    missing_stock: int
    invalid_brand: int
    warnings: list[str]


def _clean_text(value: object) -> str:
    text = str(value or '').strip()
    text = re.sub(r'\s+', ' ', text)
    return text


def _find_column(columns: Iterable[str], *needles: str) -> str | None:
    lowered = {str(col).lower(): str(col) for col in columns}
    for needle in needles:
        for low, original in lowered.items():
            if needle in low:
                return original
    return None


def _looks_empty(value: object) -> bool:
    return not _clean_text(value)


def _is_stock_operation(operation: str) -> bool:
    text = str(operation or '').strip().lower()
    return text in {'estoque', 'atualizacao_estoque', 'atualização_estoque', 'stock', 'stock_balance'}


def _find_identity_column(columns: Iterable[str]) -> str | None:
    return _find_column(
        columns,
        'produto.id',
        'id produto',
        'id_produto',
        'codigo',
        'código',
        'sku',
        'gtin',
        'ean',
        'referencia',
        'referência',
    )


def normalize_site_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame() if not isinstance(df, pd.DataFrame) else df.copy()

    out = df.copy()
    for col in out.columns:
        if out[col].dtype == object:
            out[col] = out[col].map(_clean_text)

    brand_col = _find_column(out.columns, 'marca')
    if brand_col:
        def fix_brand(value: object) -> str:
            text = _clean_text(value)
            normalized = text.lower().replace('é', 'e').replace('ê', 'e').replace('ô', 'o')
            if normalized in STORE_BRAND_TERMS or any(term in normalized for term in STORE_BRAND_TERMS):
                return ''
            return text
        out[brand_col] = out[brand_col].map(fix_brand)

    image_col = _find_column(out.columns, 'imagem', 'image')
    if image_col:
        out[image_col] = out[image_col].map(lambda value: '|'.join(dict.fromkeys([part.strip() for part in re.split(r'[;,|]', _clean_text(value)) if part.strip()])))

    gtin_col = _find_column(out.columns, 'gtin', 'ean')
    if gtin_col:
        def fix_gtin(value: object) -> str:
            digits = re.sub(r'\D+', '', _clean_text(value))
            return digits if len(digits) in {8, 12, 13, 14} else ''
        out[gtin_col] = out[gtin_col].map(fix_gtin)

    return out.fillna('')


def evaluate_site_dataframe(df: pd.DataFrame, operation: str = 'cadastro') -> SmartScanQuality:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return SmartScanQuality(0, 0, 0, 0, 0, 0, 0, 0, ['Nenhum produto válido foi capturado.'])

    is_stock = _is_stock_operation(operation)
    desc_col = _find_column(df.columns, 'descrição', 'descricao', 'nome', 'produto')
    price_col = _find_column(df.columns, 'preço', 'preco', 'valor')
    stock_col = _find_column(df.columns, 'estoque', 'quantidade', 'saldo', 'balanço', 'balanco')
    brand_col = _find_column(df.columns, 'marca')
    identity_col = _find_identity_column(df.columns)

    rows = len(df)
    # BLINGFIX: estoque não deve ser penalizado por falta de descrição/título.
    # Atualização de estoque precisa de identificador + saldo/quantidade + depósito.
    missing_description = 0 if is_stock else (int(df[desc_col].map(_looks_empty).sum()) if desc_col else rows)
    missing_price = int(df[price_col].map(_looks_empty).sum()) if price_col else (0 if is_stock else rows)
    missing_stock = int(df[stock_col].map(_looks_empty).sum()) if stock_col else (rows if is_stock else 0)
    missing_identity = int(df[identity_col].map(_looks_empty).sum()) if identity_col else (rows if is_stock else 0)
    invalid_brand = 0
    if brand_col and not is_stock:
        invalid_brand = int(df[brand_col].astype(str).str.lower().str.contains('mega center|stoqui|loja', regex=True, na=False).sum())

    good_rows = rows
    if not is_stock and desc_col:
        good_rows = min(good_rows, rows - missing_description)
    if not is_stock and price_col:
        good_rows = min(good_rows, rows - missing_price)
    if is_stock and stock_col:
        good_rows = min(good_rows, rows - missing_stock)
    if is_stock and identity_col:
        good_rows = min(good_rows, rows - missing_identity)

    penalties = 0
    penalties += int((missing_description / max(rows, 1)) * 35) if not is_stock else 0
    penalties += int((missing_price / max(rows, 1)) * 25) if not is_stock else 0
    penalties += int((missing_stock / max(rows, 1)) * 35) if is_stock else 0
    penalties += int((missing_identity / max(rows, 1)) * 35) if is_stock else 0
    penalties += int((invalid_brand / max(rows, 1)) * 10)
    score = max(0, min(100, 100 - penalties))

    warnings: list[str] = []
    if not is_stock and missing_description:
        warnings.append(f'{missing_description} produto(s) sem descrição/título.')
    if not is_stock and missing_price:
        warnings.append(f'{missing_price} produto(s) sem preço.')
    if is_stock and missing_identity:
        warnings.append(f'{missing_identity} produto(s) sem código/SKU/GTIN/ID para localizar no Bling.')
    if is_stock and missing_stock:
        warnings.append(f'{missing_stock} produto(s) sem estoque/saldo.')
    if invalid_brand:
        warnings.append(f'{invalid_brand} marca(s) pareciam nome da loja e foram sinalizadas.')
    if score >= 85:
        warnings.append('Qualidade boa para seguir.')
    elif score >= 60:
        warnings.append('Qualidade mediana: revisar campos faltantes antes de continuar.')
    else:
        warnings.append('Qualidade baixa: recomenda-se nova captura ou links mais específicos.')

    return SmartScanQuality(rows, len(df.columns), score, max(0, good_rows), missing_price, missing_description, missing_stock, invalid_brand, warnings)


__all__ = ['SmartScanQuality', 'evaluate_site_dataframe', 'normalize_site_dataframe']
