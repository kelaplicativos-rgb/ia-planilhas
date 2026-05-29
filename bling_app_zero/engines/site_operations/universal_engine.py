from __future__ import annotations

from collections.abc import Callable, Iterable

import pandas as pd

from bling_app_zero.engines.fast_site_scraper import run_fast_site_scraper
from bling_app_zero.engines.fast_site_scraper.constants import SAFE_CAPTURE_MAX_PAGES, SAFE_CAPTURE_MAX_PRODUCTS, normalize_capture_limits
from bling_app_zero.engines.site_operations.contracts import cadastro_columns
from bling_app_zero.engines.site_operations.stoqui_api_engine import can_handle_stoqui_url, run_stoqui_site_engine
from bling_app_zero.engines.site_operations.submotors import SiteSubmotorPlan, build_submotor_plan

CADASTRO_RICH_SUBMOTORS = {'descricao_rica', 'preco', 'imagens', 'marca', 'categoria'}
ESTOQUE_COMPATIBLE_SUBMOTORS = {'links', 'identificacao', 'gtin', 'estoque', 'descricao'}


def _emit(progress_callback: Callable[[dict], None] | None, payload: dict) -> None:
    if not progress_callback:
        return
    try:
        progress_callback(payload)
    except Exception:
        pass


def _operation_from_universal_contract(plan: SiteSubmotorPlan) -> str:
    active = set(plan.active)
    if active and active <= ESTOQUE_COMPATIBLE_SUBMOTORS and 'estoque' in active:
        return 'estoque'
    if active & CADASTRO_RICH_SUBMOTORS:
        return 'cadastro'
    return 'cadastro'


def run_universal_site_engine(
    *,
    raw_urls: str,
    requested_columns: Iterable[str] | None = None,
    max_pages: int = SAFE_CAPTURE_MAX_PAGES,
    max_products: int = SAFE_CAPTURE_MAX_PRODUCTS,
    stop_early: bool = True,
    progress_callback: Callable[[dict], None] | None = None,
) -> pd.DataFrame:
    """Motor universal para SITE -> origem única baseada no modelo anexado."""
    limits = normalize_capture_limits(max_pages=max_pages, max_products=max_products, mode='safe' if stop_early else 'deep')
    max_pages = limits['max_pages']
    max_products = limits['max_products']
    stop_early = True

    columns = cadastro_columns(requested_columns)
    plan = build_submotor_plan('universal', columns)
    internal_operation = _operation_from_universal_contract(plan)
    _emit(progress_callback, {
        'stage': 'Motor universal',
        'message': f'Origem única por modelo. Submotores ativos: {plan.summary}. Modo interno: {internal_operation}.',
        'progress': 0.04,
        'submotors': plan.active,
        'operation': plan.operation,
        'internal_operation': internal_operation,
        'max_pages': max_pages,
        'max_products': max_products,
        'safe_limited': True,
    })

    if can_handle_stoqui_url(raw_urls):
        df_stoqui = run_stoqui_site_engine(
            raw_urls=raw_urls,
            requested_columns=columns,
            operation=internal_operation,
            max_products=max_products,
            progress_callback=progress_callback,
        )
        if isinstance(df_stoqui, pd.DataFrame) and not df_stoqui.empty:
            return df_stoqui

    return run_fast_site_scraper(
        raw_urls=raw_urls,
        requested_columns=columns,
        operation=internal_operation,
        max_pages=max_pages,
        max_products=max_products,
        stop_early=stop_early,
        progress_callback=progress_callback,
    )


__all__ = ['run_universal_site_engine']