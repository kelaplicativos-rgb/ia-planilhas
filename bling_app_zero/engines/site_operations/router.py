from __future__ import annotations

from collections.abc import Callable, Iterable

import pandas as pd

from bling_app_zero.engines.site_operations.cadastro_engine import run_cadastro_site_engine
from bling_app_zero.engines.site_operations.estoque_engine import run_estoque_site_engine

VALID_OPERATIONS = {'cadastro', 'estoque'}


def normalize_operation(operation: str | None) -> str:
    value = str(operation or 'cadastro').strip().lower()
    if value in {'estoque', 'stock', 'atualizacao_estoque', 'atualização de estoque', 'estoque_site'}:
        return 'estoque'
    return 'cadastro'


def run_site_operation_engine(
    *,
    operation: str,
    raw_urls: str,
    requested_columns: Iterable[str] | None = None,
    max_pages: int = 1_000_000,
    max_products: int = 1_000_000,
    stop_early: bool = False,
    progress_callback: Callable[[dict], None] | None = None,
) -> pd.DataFrame:
    """Roteador central de motores por operação.

    Mantém cadastro e estoque desacoplados. A UI chama uma única entrada,
    mas cada operação evolui no seu próprio motor sem contaminar a outra.
    """
    selected = normalize_operation(operation)
    if selected == 'estoque':
        return run_estoque_site_engine(
            raw_urls=raw_urls,
            requested_columns=requested_columns,
            max_pages=max_pages,
            max_products=max_products,
            stop_early=stop_early,
            progress_callback=progress_callback,
        )

    return run_cadastro_site_engine(
        raw_urls=raw_urls,
        requested_columns=requested_columns,
        max_pages=max_pages,
        max_products=max_products,
        stop_early=stop_early,
        progress_callback=progress_callback,
    )
