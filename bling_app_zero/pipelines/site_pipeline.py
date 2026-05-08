from __future__ import annotations

import pandas as pd

from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.engines.site_cadastro_engine import run_site_cadastro_engine
from bling_app_zero.engines.site_estoque_engine import run_site_estoque_engine


VALID_OPERATIONS = {'cadastro', 'estoque'}


def _normalize_operation(operation: str | None) -> str:
    value = str(operation or 'cadastro').strip().lower()
    return value if value in VALID_OPERATIONS else 'cadastro'


def run_pipeline(
    raw_urls: str,
    requested_columns: list[str] | None = None,
    all_products: bool = False,
    max_pages: int = 250,
    max_products: int = 1000,
    operation: str = 'cadastro',
) -> pd.DataFrame:
    selected_operation = _normalize_operation(operation)

    if selected_operation == 'estoque':
        df_result = run_site_estoque_engine(
            raw_urls=raw_urls,
            requested_columns=requested_columns,
            all_products=all_products,
            max_pages=max_pages,
            max_products=max_products,
        )
        return sanitize_for_bling(df_result)

    df_result = run_site_cadastro_engine(
        raw_urls=raw_urls,
        requested_columns=requested_columns,
        all_products=all_products,
        max_pages=max_pages,
        max_products=max_products,
    )
    return sanitize_for_bling(df_result)
