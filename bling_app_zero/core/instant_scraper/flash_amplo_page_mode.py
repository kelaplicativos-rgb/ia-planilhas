from __future__ import annotations

"""Adaptador do modo Flash Amplo para captura página por página.

Este arquivo é a ponte entre o fluxo Instant/Flash e o motor rápido paralelo em
`bling_app_zero.core.flash_page_crawler`.

Regra obrigatória:
- categoria/listagem só descobre links;
- dados do produto vêm entrando em cada página `/produto/...`;
- estoque não é obrigatório;
- cada linha mantém `Link Externo`/`URL do Produto` da página real.
"""

from typing import Callable, Iterable, Optional

import pandas as pd

from bling_app_zero.core.flash_page_crawler import (
    crawl_flash_amplo_page_by_page,
    crawl_flash_amplo_page_by_page_dataframe,
)


ProgressCallback = Optional[Callable[[int, int, str], None]]


def run_flash_amplo_page_mode(
    urls: Iterable[str],
    *,
    max_products: int = 500,
    max_workers: int = 12,
    progress_callback: ProgressCallback = None,
) -> pd.DataFrame:
    """Executa o Flash Amplo correto: rápido e página por página."""
    return crawl_flash_amplo_page_by_page_dataframe(
        urls,
        max_products=max_products,
        max_workers=max_workers,
        progress_callback=progress_callback,
    )


def run_flash_amplo(
    urls: Iterable[str],
    *,
    max_products: int = 500,
    max_workers: int = 12,
    progress_callback: ProgressCallback = None,
) -> pd.DataFrame:
    """Alias compatível para telas/fluxos que chamarem `run_flash_amplo`."""
    return run_flash_amplo_page_mode(
        urls,
        max_products=max_products,
        max_workers=max_workers,
        progress_callback=progress_callback,
    )


def flash_amplo_dataframe(
    urls: Iterable[str],
    *,
    max_products: int = 500,
    max_workers: int = 12,
    progress_callback: ProgressCallback = None,
) -> pd.DataFrame:
    """Alias objetivo para retorno em DataFrame."""
    return run_flash_amplo_page_mode(
        urls,
        max_products=max_products,
        max_workers=max_workers,
        progress_callback=progress_callback,
    )


def flash_amplo_rows(
    urls: Iterable[str],
    *,
    max_products: int = 500,
    max_workers: int = 12,
    progress_callback: ProgressCallback = None,
) -> list[dict[str, str]]:
    """Retorna linhas em lista de dicts para fluxos antigos."""
    return crawl_flash_amplo_page_by_page(
        urls,
        max_products=max_products,
        max_workers=max_workers,
        progress_callback=progress_callback,
    )
