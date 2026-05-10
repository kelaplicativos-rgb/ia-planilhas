from __future__ import annotations

from collections.abc import Callable, Iterable

import pandas as pd

from bling_app_zero.engines.fast_site_scraper import run_fast_site_scraper
from bling_app_zero.engines.site_operations.contracts import estoque_columns
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
    max_pages: int = 1_000_000,
    max_products: int = 1_000_000,
    stop_early: bool = False,
    progress_callback: Callable[[dict], None] | None = None,
) -> pd.DataFrame:
    """Motor independente para SITE -> origem de ESTOQUE.

    Estoque deve obedecer ao contrato do modelo: buscar somente as colunas
    solicitadas. Se a coluna não for encontrada no site, fica vazia.
    Sem contrato/modelo, não tenta adivinhar e não reaproveita colunas de cadastro.
    """
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
    })
    return run_fast_site_scraper(
        raw_urls=raw_urls,
        requested_columns=columns,
        operation='estoque',
        max_pages=max_pages,
        max_products=max_products,
        stop_early=stop_early,
        progress_callback=progress_callback,
    )
