from __future__ import annotations

import pandas as pd

from bling_app_zero.engines.site_engine import scrape_all_products, scrape_urls, split_urls


DEFAULT_ESTOQUE_SITE_COLUMNS = [
    'Código',
    'Descrição',
    'Depósito (OBRIGATÓRIO)',
    'Balanço (OBRIGATÓRIO)',
]


def _effective_columns(requested_columns: list[str] | None) -> list[str]:
    columns = [str(column).strip() for column in (requested_columns or []) if str(column).strip()]
    return columns or list(DEFAULT_ESTOQUE_SITE_COLUMNS)


def _blank_missing_requested_columns(df: pd.DataFrame, requested_columns: list[str]) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()

    for column in requested_columns:
        if column not in out.columns:
            out[column] = ''

    return out.loc[:, requested_columns].fillna('')


def run_site_estoque_engine(
    raw_urls: str,
    requested_columns: list[str] | None = None,
    all_products: bool = False,
    max_pages: int = 250,
    max_products: int = 1000,
) -> pd.DataFrame:
    columns = _effective_columns(requested_columns)
    urls = split_urls(raw_urls)
    if not urls:
        return pd.DataFrame(columns=columns)

    if all_products:
        df, _product_urls = scrape_all_products(
            start_urls=urls,
            requested_columns=columns,
            max_pages=max_pages,
            max_products=max_products,
        )
    else:
        df = scrape_urls(urls, requested_columns=columns)

    return _blank_missing_requested_columns(df, columns)
