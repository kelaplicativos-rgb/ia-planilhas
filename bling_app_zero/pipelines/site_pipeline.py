from __future__ import annotations

import pandas as pd

from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.engines.fast_site_scraper import run_fast_site_scraper


VALID_OPERATIONS = {'cadastro', 'estoque'}
ALL_PAGES_LIMIT = 1_000_000
ALL_PRODUCTS_LIMIT = 1_000_000


def _normalize_operation(operation: str | None) -> str:
    value = str(operation or 'cadastro').strip().lower()
    return value if value in VALID_OPERATIONS else 'cadastro'


def run_pipeline(
    raw_urls: str,
    requested_columns: list[str] | None = None,
    all_products: bool = True,
    max_pages: int = ALL_PAGES_LIMIT,
    max_products: int = ALL_PRODUCTS_LIMIT,
    operation: str = 'cadastro',
) -> pd.DataFrame:
    _ = all_products
    selected_operation = _normalize_operation(operation)
    df_result = run_fast_site_scraper(
        raw_urls=raw_urls,
        requested_columns=requested_columns,
        operation=selected_operation,
        max_pages=max(max_pages or 0, ALL_PAGES_LIMIT),
        max_products=max(max_products or 0, ALL_PRODUCTS_LIMIT),
    )
    return sanitize_for_bling(df_result)
