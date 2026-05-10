from __future__ import annotations

from collections.abc import Callable, Iterable

import pandas as pd

from bling_app_zero.engines.fast_site_scraper import run_fast_site_scraper

CADASTRO_DEFAULT_COLUMNS = [
    'URL',
    'Código',
    'SKU',
    'GTIN',
    'Descrição',
    'Descrição complementar',
    'Características',
    'Ficha técnica',
    'Nome',
    'Preço',
    'Preço unitário (OBRIGATÓRIO)',
    'URL Imagens',
    'Imagens',
    'Marca',
    'Categoria',
]


def _clean_columns(columns: Iterable[str] | None) -> list[str]:
    cleaned = [str(column).strip() for column in (columns or []) if str(column).strip()]
    return cleaned or CADASTRO_DEFAULT_COLUMNS.copy()


def run_cadastro_site_engine(
    *,
    raw_urls: str,
    requested_columns: Iterable[str] | None = None,
    max_pages: int = 1_000_000,
    max_products: int = 1_000_000,
    stop_early: bool = False,
    progress_callback: Callable[[dict], None] | None = None,
) -> pd.DataFrame:
    """Motor independente para SITE -> origem de CADASTRO.

    Cadastro pode enriquecer produto com campos completos: descrição, preço,
    imagens, GTIN, marca, categoria e dados ricos quando o modelo pedir.
    Este motor nunca deve aplicar regra específica de estoque.
    """
    columns = _clean_columns(requested_columns)
    return run_fast_site_scraper(
        raw_urls=raw_urls,
        requested_columns=columns,
        operation='cadastro',
        max_pages=max_pages,
        max_products=max_products,
        stop_early=stop_early,
        progress_callback=progress_callback,
    )
