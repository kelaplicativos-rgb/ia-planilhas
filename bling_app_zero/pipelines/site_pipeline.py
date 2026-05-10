from __future__ import annotations

from typing import Callable

import pandas as pd

from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.engines.fast_site_scraper import run_fast_site_scraper


VALID_OPERATIONS = {'cadastro', 'estoque'}
DEFAULT_MAX_PAGES = 120
DEFAULT_MAX_PRODUCTS = 300
HARD_MAX_PAGES = 250
HARD_MAX_PRODUCTS = 600


def _normalize_operation(operation: str | None) -> str:
    value = str(operation or 'cadastro').strip().lower()
    return value if value in VALID_OPERATIONS else 'cadastro'


def _safe_limit(value: int | None, default: int, hard_max: int) -> int:
    try:
        number = int(value or default)
    except Exception:
        number = default
    if number <= 0:
        number = default
    return max(1, min(number, hard_max))


def run_pipeline(
    raw_urls: str,
    requested_columns: list[str] | None = None,
    all_products: bool = True,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_products: int = DEFAULT_MAX_PRODUCTS,
    operation: str = 'cadastro',
    progress_callback: Callable[[dict], None] | None = None,
) -> pd.DataFrame:
    _ = all_products
    selected_operation = _normalize_operation(operation)
    safe_max_pages = _safe_limit(max_pages, DEFAULT_MAX_PAGES, HARD_MAX_PAGES)
    safe_max_products = _safe_limit(max_products, DEFAULT_MAX_PRODUCTS, HARD_MAX_PRODUCTS)

    if progress_callback:
        progress_callback({
            'stage': 'Preparando',
            'message': f'Preparando busca segura: até {safe_max_pages} página(s) e {safe_max_products} produto(s).',
            'progress': 0.02,
        })

    df_result = run_fast_site_scraper(
        raw_urls=raw_urls,
        requested_columns=requested_columns,
        operation=selected_operation,
        max_pages=safe_max_pages,
        max_products=safe_max_products,
        progress_callback=progress_callback,
    )

    if progress_callback:
        progress_callback({'stage': 'Organizando', 'message': 'Organizando os dados no padrão do Bling...', 'progress': 0.96})
    safe = sanitize_for_bling(df_result)
    if progress_callback:
        progress_callback({'stage': 'Pronto', 'message': f'{len(safe)} produto(s) preparados na origem.', 'progress': 1.0})
    return safe
