from __future__ import annotations

import pandas as pd

from bling_app_zero.engines.site_engine import scrape_all_products, scrape_urls, split_urls


def run_pipeline(
    raw_urls: str,
    requested_columns: list[str] | None = None,
    all_products: bool = False,
    max_pages: int = 250,
    max_products: int = 1000,
) -> pd.DataFrame:
    urls = split_urls(raw_urls)
    if not urls:
        return pd.DataFrame()

    if all_products:
        df, _product_urls = scrape_all_products(
            start_urls=urls,
            requested_columns=requested_columns,
            max_pages=max_pages,
            max_products=max_products,
        )
        return df

    return scrape_urls(urls, requested_columns=requested_columns)
