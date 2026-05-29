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
    """Roteador central dos motores por site com limite duro.

    BLINGFIX: este roteador não deve aceitar 1_000_000 páginas/produtos em
    chamadas diretas. Mesmo fora da UI, os limites passam pelo normalizador.
    """
    selected = normalize_operation(operation)
    limits = normalize_capture_limits(
        max_pages=max_pages,
        max_products=max_products,
        mode='safe' if stop_early else 'deep',
    )
    safe_max_pages = limits['max_pages']
    safe_max_products = limits['max_products']
    safe_stop_early = True

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