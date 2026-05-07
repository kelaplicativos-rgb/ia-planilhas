from __future__ import annotations

import pandas as pd

from bling_app_zero.engines.flash_amplo_engine import run_flash_amplo_page_mode, scrape_urls, split_urls


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


def run_site_cadastro_engine(
    raw_urls: str,
    requested_columns: list[str] | None = None,
    all_products: bool = False,
    max_pages: int = 250,
    max_products: int = 1000,
) -> pd.DataFrame:
    urls = split_urls(raw_urls)
    if not urls:
        return pd.DataFrame(columns=_effective_columns(requested_columns) or DEFAULT_CADASTRO_SITE_COLUMNS)

    columns = _effective_columns(requested_columns)

    if all_products:
        return run_flash_amplo_page_mode(
            raw_urls=raw_urls,
            requested_columns=columns,
            max_pages=max_pages,
            max_products=max_products,
            keep_only_requested_columns=False,
        ).fillna('')

    return scrape_urls(urls, requested_columns=columns).fillna('')
