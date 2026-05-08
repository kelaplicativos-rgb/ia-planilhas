from __future__ import annotations

import pandas as pd

from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.engines.source_sheet_scraper_engine import run_source_sheet_scraper


VALID_OPERATIONS = {'cadastro', 'estoque'}


def _normalize_operation(operation: str | None) -> str:
    value = str(operation or 'cadastro').strip().lower()
    return value if value in VALID_OPERATIONS else 'cadastro'


def run_pipeline(
    raw_urls: str,
    requested_columns: list[str] | None = None,
    all_products: bool = False,
    max_pages: int = 120,
    max_products: int = 300,
    operation: str = 'cadastro',
) -> pd.DataFrame:
    selected_operation = _normalize_operation(operation)
    df_result = run_source_sheet_scraper(
        raw_urls=raw_urls,
        requested_columns=requested_columns,
        operation=selected_operation,
        all_products=all_products,
        max_pages=max_pages,
        max_products=max_products,
        keep_only_requested_columns=True,
    )
    return sanitize_for_bling(df_result)
