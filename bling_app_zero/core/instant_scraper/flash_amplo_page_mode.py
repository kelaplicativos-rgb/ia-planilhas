from __future__ import annotations

from typing import Callable, Iterable, Optional

import pandas as pd

from bling_app_zero.core.flash_page_crawler import (
    DEFAULT_MAX_PRODUCTS,
    DEFAULT_MAX_WORKERS,
    crawl_flash_amplo_page_by_page,
    crawl_flash_amplo_page_by_page_dataframe,
)

ProgressCallback = Optional[Callable[[int, int, str], None]]


def run_flash_amplo_page_mode(
    urls: Iterable[str],
    *,
    max_products: int = DEFAULT_MAX_PRODUCTS,
    max_workers: int = DEFAULT_MAX_WORKERS,
    progress_callback: ProgressCallback = None,
    requested_fields: Iterable[str] | None = None,
) -> pd.DataFrame:
    return crawl_flash_amplo_page_by_page_dataframe(
        urls,
        max_products=max_products,
        max_workers=max_workers,
        progress_callback=progress_callback,
        requested_fields=requested_fields,
    )


def run_flash_amplo(
    urls: Iterable[str],
    *,
    max_products: int = DEFAULT_MAX_PRODUCTS,
    max_workers: int = DEFAULT_MAX_WORKERS,
    progress_callback: ProgressCallback = None,
    requested_fields: Iterable[str] | None = None,
) -> pd.DataFrame:
    return run_flash_amplo_page_mode(
        urls,
        max_products=max_products,
        max_workers=max_workers,
        progress_callback=progress_callback,
        requested_fields=requested_fields,
    )


def flash_amplo_dataframe(
    urls: Iterable[str],
    *,
    max_products: int = DEFAULT_MAX_PRODUCTS,
    max_workers: int = DEFAULT_MAX_WORKERS,
    progress_callback: ProgressCallback = None,
    requested_fields: Iterable[str] | None = None,
) -> pd.DataFrame:
    return run_flash_amplo_page_mode(
        urls,
        max_products=max_products,
        max_workers=max_workers,
        progress_callback=progress_callback,
        requested_fields=requested_fields,
    )


def flash_amplo_rows(
    urls: Iterable[str],
    *,
    max_products: int = DEFAULT_MAX_PRODUCTS,
    max_workers: int = DEFAULT_MAX_WORKERS,
    progress_callback: ProgressCallback = None,
    requested_fields: Iterable[str] | None = None,
) -> list[dict[str, str]]:
    return crawl_flash_amplo_page_by_page(
        urls,
        max_products=max_products,
        max_workers=max_workers,
        progress_callback=progress_callback,
        requested_fields=requested_fields,
    )
