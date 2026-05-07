from __future__ import annotations

from io import BytesIO

import pandas as pd

from bling_app_zero.core.gtin import clean_gtin, looks_like_gtin_column
from bling_app_zero.core.text import clean_cell


def sanitize_for_bling(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()

    out = df.copy().fillna('')

    for col in out.columns:
        if looks_like_gtin_column(col):
            out[col] = out[col].apply(clean_gtin)
        else:
            out[col] = out[col].apply(clean_cell)

    return out.fillna('')


def to_bling_csv_bytes(df: pd.DataFrame) -> bytes:
    safe = sanitize_for_bling(df)
    buffer = BytesIO()
    safe.to_csv(buffer, sep=';', index=False, encoding='utf-8-sig')
    return buffer.getvalue()


def filename_for_operation(operation: str) -> str:
    op = str(operation or 'bling').lower().strip()
    if op == 'estoque':
        return 'bling_atualizacao_estoque.csv'
    if op == 'cadastro':
        return 'bling_cadastro_produtos.csv'
    return 'bling_exportacao.csv'
