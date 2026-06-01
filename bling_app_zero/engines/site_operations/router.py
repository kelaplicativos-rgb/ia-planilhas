from __future__ import annotations

from collections.abc import Callable, Iterable

import pandas as pd

from bling_app_zero.engines.fast_site_scraper.constants import SAFE_CAPTURE_MAX_PAGES, SAFE_CAPTURE_MAX_PRODUCTS, normalize_capture_limits
from bling_app_zero.engines.site_operations.cadastro_engine import run_cadastro_site_engine
from bling_app_zero.engines.site_operations.estoque_engine import run_estoque_site_engine
from bling_app_zero.engines.site_operations.universal_engine import run_universal_site_engine
from bling_app_zero.universal.model_contract_detector import normalize_contract_operation

VALID_OPERATIONS = {'cadastro', 'estoque', 'universal', 'atualizacao_preco'}
UNIVERSAL_ALIASES = {'universal', 'modelo', 'modelo_destino', 'planilha', 'wizard_cadastro_estoque'}


def normalize_operation(operation: str | None) -> str:
    normalized = normalize_contract_operation(operation)
    if normalized in VALID_OPERATIONS:
        return normalized
    value = str(operation or 'universal').strip().lower()
    if value in {'estoque', 'stock', 'atualizacao_estoque', 'atualização de estoque', 'estoque_site'}:
        return 'estoque'
    if value in {'cadastro', 'cadastro_site', 'produtos', 'produto'}:
        return 'cadastro'
    if value in UNIVERSAL_ALIASES:
        return 'universal'
    return 'universal'


def _limit_mode(selected: str, stop_early: bool) -> str:
    if selected == 'estoque' and not stop_early:
        return 'stock_balance_flow'
    return 'safe' if stop_early else 'deep'


def run_site_operation_engine(
    *,
    operation: str,
    raw_urls: str,
    requested_columns: Iterable[str] | None = None,
    max_pages: int = SAFE_CAPTURE_MAX_PAGES,
    max_products: int = SAFE_CAPTURE_MAX_PRODUCTS,
    stop_early: bool = True,
    progress_callback: Callable[[dict], None] | None = None,
) -> pd.DataFrame:
    """Roteador central dos motores por site com limite controlado.

    Para estoque em modo completo, usa fluxo contínuo e não a quantidade segura.
    """
    selected = normalize_operation(operation)
    safe_stop_early = bool(stop_early)
    limits = normalize_capture_limits(
        max_pages=max_pages,
        max_products=max_products,
        mode=_limit_mode(selected, safe_stop_early),
    )
    safe_max_pages = int(limits['max_pages'])
    safe_max_products = int(limits['max_products'])

    if selected == 'estoque':
        return run_estoque_site_engine(
            raw_urls=raw_urls,
            requested_columns=requested_columns,
            max_pages=safe_max_pages,
            max_products=safe_max_products,
            stop_early=safe_stop_early,
            progress_callback=progress_callback,
        )

    if selected in {'cadastro', 'atualizacao_preco'}:
        return run_cadastro_site_engine(
            raw_urls=raw_urls,
            requested_columns=requested_columns,
            max_pages=safe_max_pages,
            max_products=safe_max_products,
            stop_early=safe_stop_early,
            progress_callback=progress_callback,
        )

    return run_universal_site_engine(
        raw_urls=raw_urls,
        requested_columns=requested_columns,
        max_pages=safe_max_pages,
        max_products=safe_max_products,
        stop_early=safe_stop_early,
        progress_callback=progress_callback,
    )


__all__ = ['normalize_operation', 'run_site_operation_engine']
