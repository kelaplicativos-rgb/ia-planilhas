from __future__ import annotations

from collections.abc import Callable, Iterable

import pandas as pd

from bling_app_zero.engines.fast_site_scraper import run_fast_site_scraper

ESTOQUE_FALLBACK_COLUMNS = ['Código', 'Descrição', 'Depósito (OBRIGATÓRIO)', 'Balanço (OBRIGATÓRIO)']


def _clean_columns(columns: Iterable[str] | None) -> list[str]:
    return [str(column).strip() for column in (columns or []) if str(column).strip()]


def run_estoque_site_engine(
    *,
    raw_urls: str,
    requested_columns: Iterable[str] | None = None,
    max_pages: int = 1_000_000,
    max_products: int = 1_000_000,
    stop_early: bool = False,
    progress_callback: Callable[[dict], None] | None = None,
) -> pd.DataFrame:
    """Motor independente para SITE -> origem de ESTOQUE.

    Estoque deve obedecer ao contrato do modelo: buscar somente as colunas
    solicitadas. Se a coluna não for encontrada no site, fica vazia.
    """
    columns = _clean_columns(requested_columns)
    if not columns:
        return pd.DataFrame(columns=ESTOQUE_FALLBACK_COLUMNS)

    return run_fast_site_scraper(
        raw_urls=raw_urls,
        requested_columns=columns,
        operation='estoque',
        max_pages=max_pages,
        max_products=max_products,
        stop_early=stop_early,
        progress_callback=progress_callback,
    )
