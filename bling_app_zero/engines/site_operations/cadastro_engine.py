from __future__ import annotations

from collections.abc import Callable, Iterable

import pandas as pd

from bling_app_zero.engines.fast_site_scraper import run_fast_site_scraper
from bling_app_zero.engines.site_operations.contracts import cadastro_columns
from bling_app_zero.engines.site_operations.submotors import build_submotor_plan


def _emit(progress_callback: Callable[[dict], None] | None, payload: dict) -> None:
    if not progress_callback:
        return
    try:
        progress_callback(payload)
    except Exception:
        pass


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
    columns = cadastro_columns(requested_columns)
    plan = build_submotor_plan('cadastro', columns)
    _emit(progress_callback, {
        'stage': 'Motor de cadastro',
        'message': f'Submotores ativos: {plan.summary}.',
        'progress': 0.04,
        'submotors': plan.active,
    })
    return run_fast_site_scraper(
        raw_urls=raw_urls,
        requested_columns=columns,
        operation='cadastro',
        max_pages=max_pages,
        max_products=max_products,
        stop_early=stop_early,
        progress_callback=progress_callback,
    )
