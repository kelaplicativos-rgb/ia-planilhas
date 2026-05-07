from __future__ import annotations

import pandas as pd

from bling_app_zero.engines.site_engine import scrape_urls, split_urls


def run_pipeline(raw_urls: str, requested_columns: list[str] | None = None) -> pd.DataFrame:
    urls = split_urls(raw_urls)
    if not urls:
        return pd.DataFrame()
    return scrape_urls(urls, requested_columns=requested_columns)
