from __future__ import annotations

import pandas as pd

from bling_app_zero.engines.flash_amplo_engine import run_flash_amplo_page_mode, scrape_urls, split_urls
from bling_app_zero.engines.turbo_scraper_engine import run_turbo_scraper


DEFAULT_CADASTRO_SITE_COLUMNS = [
    'URL',
    'Código',
    'SKU',
    'GTIN',
    'Descrição',
    'Nome',
    'Preço',
    'Preço unitário (OBRIGATÓRIO)',
    'URL Imagens',
    'Imagens',
    'Marca',
    'Categoria',
]


def _effective_columns(requested_columns: list[str] | None) -> list[str] | None:
    if requested_columns:
        return [str(column) for column in requested_columns if str(column).strip()]
    return None


def _has_real_rows(df: pd.DataFrame | None) -> bool:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return False
    for _, row in df.iterrows():
        values = [str(value or '').strip() for value in row.to_dict().values()]
        if any(values):
            return True
    return False


def _fallback_old_engine(
    raw_urls: str,
    urls: list[str],
    columns: list[str] | None,
    all_products: bool,
    max_pages: int,
    max_products: int,
) -> pd.DataFrame:
    if all_products:
        return run_flash_amplo_page_mode(
            raw_urls=raw_urls,
            requested_columns=columns,
            max_pages=max_pages,
            max_products=max_products,
            keep_only_requested_columns=False,
        ).fillna('')
    return scrape_urls(urls, requested_columns=columns).fillna('')


def run_site_cadastro_engine(
    raw_urls: str,
    requested_columns: list[str] | None = None,
    all_products: bool = False,
    max_pages: int = 250,
    max_products: int = 1000,
) -> pd.DataFrame:
    urls = split_urls(raw_urls)
    columns = _effective_columns(requested_columns)
    if not urls:
        return pd.DataFrame(columns=columns or DEFAULT_CADASTRO_SITE_COLUMNS)

    df_turbo = run_turbo_scraper(
        raw_urls=raw_urls,
        requested_columns=columns,
        operation='cadastro',
        all_products=all_products,
        max_pages=max_pages,
        max_products=max_products,
        keep_only_requested_columns=bool(columns),
    ).fillna('')
    if _has_real_rows(df_turbo):
        return df_turbo

    return _fallback_old_engine(
        raw_urls=raw_urls,
        urls=urls,
        columns=columns,
        all_products=all_products,
        max_pages=max_pages,
        max_products=max_products,
    ).fillna('')
