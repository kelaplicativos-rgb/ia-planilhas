from __future__ import annotations

from collections.abc import Callable, Iterable

import pandas as pd

from bling_app_zero.engines.fast_site_scraper import run_fast_site_scraper
from bling_app_zero.engines.fast_site_scraper.constants import SAFE_CAPTURE_MAX_PAGES, SAFE_CAPTURE_MAX_PRODUCTS, normalize_capture_limits
from bling_app_zero.engines.site_operations.contracts import estoque_columns
from bling_app_zero.engines.site_operations.stoqui_api_engine import can_handle_stoqui_url, run_stoqui_site_engine
from bling_app_zero.engines.site_operations.submotors import build_submotor_plan


def _emit(progress_callback: Callable[[dict], None] | None, payload: dict) -> None:
    if not progress_callback:
        return
    try:
        progress_callback(payload)
    except Exception:
        pass


def run_estoque_site_engine(
    *,
    raw_urls: str,
    requested_columns: Iterable[str] | None = None,
    max_pages: int = SAFE_CAPTURE_MAX_PAGES,
    max_products: int = SAFE_CAPTURE_MAX_PRODUCTS,
    stop_early: bool = True,
    progress_callback: Callable[[dict], None] | None = None,
) -> pd.DataFrame:
    """Motor independente para SITE -> origem de ESTOQUE com limite seguro."""
    limits = normalize_capture_limits(max_pages=max_pages, max_products=max_products, mode='safe' if stop_early else 'deep')
    max_pages = limits['max_pages']
    max_products = limits['max_products']
    stop_early = True

    columns = estoque_columns(requested_columns)
    if not columns:
        _emit(progress_callback, {
            'stage': 'Modelo obrigatório',
            'message': 'Estoque por site exige modelo/contrato de colunas. Nenhuma captura foi executada.',
            'progress': 1.0,
        })
        return pd.DataFrame()

    plan = build_submotor_plan('estoque', columns)
    _emit(progress_callback, {
        'stage': 'Motor de estoque',
        'message': f'Submotores ativos: {plan.summary}.',
        'progress': 0.04,
        'submotors': plan.active,
        'max_pages': max_pages,
        'max_products': max_products,
        'safe_limited': True,
    })

    if can_handle_stoqui_url(raw_urls):
        df_stoqui = run_stoqui_site_engine(
            raw_urls=raw_urls,
            requested_columns=columns,
            operation='estoque',
            max_products=max_products,
            progress_callback=progress_callback,
        )
        if isinstance(df_stoqui, pd.DataFrame) and not df_stoqui.empty:
            return df_stoqui

    return run_fast_site_scraper(
        raw_urls=raw_urls,
        requested_columns=columns,
        operation='estoque',
        max_pages=max_pages,
        max_products=max_products,
        stop_early=stop_early,
        progress_callback=progress_callback,
    )