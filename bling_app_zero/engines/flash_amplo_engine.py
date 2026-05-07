from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from time import monotonic
from typing import Iterable

import pandas as pd

from bling_app_zero.engines.site_engine import discover_product_urls, scrape_product, split_urls


DEFAULT_FLASH_WORKERS = 12
MAX_FLASH_WORKERS = 16


@dataclass(frozen=True)
class FlashAmploReport:
    start_urls: int
    discovered_products: int
    extracted_products: int
    failed_products: int
    elapsed_seconds: float


def _normalize_columns(requested_columns: Iterable[str] | None) -> list[str] | None:
    columns = [str(column).strip() for column in (requested_columns or []) if str(column).strip()]
    return columns or None


def _safe_scrape_one(url: str, requested_columns: list[str] | None) -> tuple[str, dict[str, str] | None]:
    try:
        row = scrape_product(url, requested_columns=requested_columns)
        if not isinstance(row, dict):
            return url, None
        if not row:
            return url, None
        return url, row
    except Exception:
        return url, None


def _ensure_requested_columns(df: pd.DataFrame, requested_columns: list[str] | None) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if not requested_columns:
        return out.fillna('')

    for column in requested_columns:
        if column not in out.columns:
            out[column] = ''
    return out.loc[:, requested_columns].fillna('')


def crawl_flash_amplo_page_by_page_dataframe(
    raw_urls: str,
    requested_columns: list[str] | None = None,
    max_pages: int = 250,
    max_products: int = 1000,
    workers: int = DEFAULT_FLASH_WORKERS,
    keep_only_requested_columns: bool = False,
) -> tuple[pd.DataFrame, FlashAmploReport]:
    started = monotonic()
    start_urls = split_urls(raw_urls)
    columns = _normalize_columns(requested_columns)

    if not start_urls:
        empty = pd.DataFrame(columns=columns or [])
        report = FlashAmploReport(
            start_urls=0,
            discovered_products=0,
            extracted_products=0,
            failed_products=0,
            elapsed_seconds=0.0,
        )
        return empty, report

    product_urls = discover_product_urls(
        start_urls=start_urls,
        max_pages=max_pages,
        max_products=max_products,
    )

    if not product_urls:
        empty = pd.DataFrame(columns=columns or [])
        report = FlashAmploReport(
            start_urls=len(start_urls),
            discovered_products=0,
            extracted_products=0,
            failed_products=0,
            elapsed_seconds=round(monotonic() - started, 3),
        )
        return empty, report

    safe_workers = max(1, min(int(workers or DEFAULT_FLASH_WORKERS), MAX_FLASH_WORKERS, len(product_urls)))
    rows: list[dict[str, str]] = []
    failed = 0

    with ThreadPoolExecutor(max_workers=safe_workers) as executor:
        futures = [executor.submit(_safe_scrape_one, url, columns) for url in product_urls]
        for future in as_completed(futures):
            _url, row = future.result()
            if row is None:
                failed += 1
                continue
            rows.append(row)

    df = pd.DataFrame(rows).fillna('')
    if keep_only_requested_columns:
        df = _ensure_requested_columns(df, columns)

    report = FlashAmploReport(
        start_urls=len(start_urls),
        discovered_products=len(product_urls),
        extracted_products=len(rows),
        failed_products=failed,
        elapsed_seconds=round(monotonic() - started, 3),
    )
    return df, report


def run_flash_amplo_page_mode(
    raw_urls: str,
    requested_columns: list[str] | None = None,
    max_pages: int = 250,
    max_products: int = 1000,
    workers: int = DEFAULT_FLASH_WORKERS,
    keep_only_requested_columns: bool = False,
) -> pd.DataFrame:
    df, _report = crawl_flash_amplo_page_by_page_dataframe(
        raw_urls=raw_urls,
        requested_columns=requested_columns,
        max_pages=max_pages,
        max_products=max_products,
        workers=workers,
        keep_only_requested_columns=keep_only_requested_columns,
    )
    return df
