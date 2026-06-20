from __future__ import annotations

from typing import Callable

import pandas as pd

from bling_app_zero.pipelines.site_pipeline import run_pipeline

RESPONSIBLE_FILE = 'bling_app_zero/engines/site_cadastro_engine.py'


def run_site_cadastro_engine(
    raw_urls: str,
    requested_columns: list[str] | None = None,
    all_products: bool = True,
    max_pages: int | None = None,
    max_products: int | None = None,
    progress_callback: Callable[[dict], None] | None = None,
    **kwargs,
) -> pd.DataFrame:
    _ = kwargs
    options: dict[str, object] = {
        'raw_urls': raw_urls,
        'requested_columns': requested_columns,
        'all_products': all_products,
        'operation': 'cadastro',
        'progress_callback': progress_callback,
    }
    if max_pages is not None:
        options['max_pages'] = max_pages
    if max_products is not None:
        options['max_products'] = max_products
    return run_pipeline(**options)


def run_engine(*args, **kwargs) -> pd.DataFrame:
    return run_site_cadastro_engine(*args, **kwargs)


__all__ = ['RESPONSIBLE_FILE', 'run_engine', 'run_site_cadastro_engine']
