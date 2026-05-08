from __future__ import annotations

import pandas as pd

from bling_app_zero.core.column_contract import build_contract
from bling_app_zero.core.text import normalize_key
from bling_app_zero.engines.flash_amplo_engine import run_flash_amplo_page_mode, scrape_urls, split_urls
from bling_app_zero.engines.instant_scraper_engine import run_instant_scraper
from bling_app_zero.engines.power_scraper_engine import run_power_scraper


DEFAULT_ESTOQUE_SITE_COLUMNS = [
    'Código',
    'Descrição',
    'Depósito (OBRIGATÓRIO)',
    'Balanço (OBRIGATÓRIO)',
]

APOIO_NAME_COLUMNS = [
    'Nome do produto',
    'Produto',
    'Descrição',
]


def _effective_columns(requested_columns: list[str] | None) -> list[str]:
    columns = [str(column).strip() for column in (requested_columns or []) if str(column).strip()]
    return columns or list(DEFAULT_ESTOQUE_SITE_COLUMNS)


def _has_description_contract(requested_columns: list[str]) -> bool:
    for field in build_contract(requested_columns):
        if field.kind in {'descricao', 'nome_apoio'}:
            return True
    return False


def _inject_optional_name_support(requested_columns: list[str]) -> list[str]:
    columns = list(requested_columns)
    if _has_description_contract(columns):
        return columns
    for candidate in APOIO_NAME_COLUMNS:
        if candidate not in columns:
            columns.append(candidate)
            break
    return columns


def _blank_missing_requested_columns(df: pd.DataFrame, requested_columns: list[str]) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    for column in requested_columns:
        if column not in out.columns:
            out[column] = ''
    return out.loc[:, requested_columns].fillna('')


def _remove_unrequested_product_noise(df: pd.DataFrame, requested_columns: list[str]) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    requested_keys = {normalize_key(column) for column in requested_columns}
    keep_columns: list[str] = []
    for column in out.columns:
        if normalize_key(column) in requested_keys or column in requested_columns:
            keep_columns.append(column)
    if not keep_columns:
        return pd.DataFrame(columns=requested_columns)
    out = out.loc[:, keep_columns]
    return _blank_missing_requested_columns(out, requested_columns)


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
    extraction_columns: list[str],
    all_products: bool,
    max_pages: int,
    max_products: int,
) -> pd.DataFrame:
    if all_products:
        return run_flash_amplo_page_mode(
            raw_urls=raw_urls,
            requested_columns=extraction_columns,
            max_pages=max_pages,
            max_products=max_products,
            keep_only_requested_columns=True,
        )
    return scrape_urls(urls, requested_columns=extraction_columns)


def run_site_estoque_engine(
    raw_urls: str,
    requested_columns: list[str] | None = None,
    all_products: bool = False,
    max_pages: int = 250,
    max_products: int = 1000,
) -> pd.DataFrame:
    model_columns = _effective_columns(requested_columns)
    extraction_columns = _inject_optional_name_support(model_columns)
    urls = split_urls(raw_urls)
    if not urls:
        return pd.DataFrame(columns=extraction_columns)

    df_power = run_power_scraper(
        raw_urls=raw_urls,
        requested_columns=extraction_columns,
        operation='estoque',
        all_products=all_products,
        max_pages=max_pages,
        max_products=max_products,
        keep_only_requested_columns=True,
    ).fillna('')
    if _has_real_rows(df_power):
        return _remove_unrequested_product_noise(df_power, extraction_columns)

    df_instant = run_instant_scraper(
        raw_urls=raw_urls,
        requested_columns=extraction_columns,
        operation='estoque',
        all_products=all_products,
        max_pages=max_pages,
        max_products=max_products,
        keep_only_requested_columns=True,
    ).fillna('')
    if _has_real_rows(df_instant):
        return _remove_unrequested_product_noise(df_instant, extraction_columns)

    df_old = _fallback_old_engine(
        raw_urls=raw_urls,
        urls=urls,
        extraction_columns=extraction_columns,
        all_products=all_products,
        max_pages=max_pages,
        max_products=max_products,
    ).fillna('')
    return _remove_unrequested_product_noise(df_old, extraction_columns)
