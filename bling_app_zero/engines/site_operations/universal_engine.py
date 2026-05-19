from __future__ import annotations

from collections.abc import Callable, Iterable

import pandas as pd

from bling_app_zero.engines.fast_site_scraper import run_fast_site_scraper
from bling_app_zero.engines.site_operations.contracts import cadastro_columns
from bling_app_zero.engines.site_operations.stoqui_api_engine import can_handle_stoqui_url, run_stoqui_site_engine
from bling_app_zero.engines.site_operations.submotors import build_submotor_plan


def _emit(progress_callback: Callable[[dict], None] | None, payload: dict) -> None:
    if not progress_callback:
        return
    try:
        progress_callback(payload)
    except Exception:
        pass


def run_universal_site_engine(
    *,
    raw_urls: str,
    requested_columns: Iterable[str] | None = None,
    max_pages: int = 1_000_000,
    max_products: int = 1_000_000,
    stop_early: bool = False,
    progress_callback: Callable[[dict], None] | None = None,
) -> pd.DataFrame:
    """Motor universal para SITE -> origem única baseada no modelo anexado.

    O usuário não precisa mais escolher Cadastro ou Estoque. Este orquestrador
    recebe as colunas reais do modelo de destino e aciona os submotores conforme
    o contrato: descrição, preço, imagens, GTIN, categoria, estoque, depósito,
    código etc. Os motores continuam especializados por baixo, mas a saída é um
    único DataFrame com exatamente as colunas solicitadas.
    """
    columns = cadastro_columns(requested_columns)
    plan = build_submotor_plan('cadastro', columns)
    _emit(progress_callback, {
        'stage': 'Motor universal',
        'message': f'Origem única por modelo. Submotores ativos: {plan.summary}.',
        'progress': 0.04,
        'submotors': plan.active,
        'operation': 'universal',
    })

    # Em sites Stoqui/React, a API interna deve operar primeiro porque o HTML
    # público costuma vir vazio. A API respeita o mesmo contrato de colunas.
    if can_handle_stoqui_url(raw_urls):
        df_stoqui = run_stoqui_site_engine(
            raw_urls=raw_urls,
            requested_columns=columns,
            operation='cadastro',
            max_products=max_products,
            progress_callback=progress_callback,
        )
        if isinstance(df_stoqui, pd.DataFrame) and not df_stoqui.empty:
            return df_stoqui

    # Fallback genérico: usa modo cadastro internamente porque é o modo mais
    # completo e também extrai estoque quando o contrato pedir saldo/quantidade.
    return run_fast_site_scraper(
        raw_urls=raw_urls,
        requested_columns=columns,
        operation='cadastro',
        max_pages=max_pages,
        max_products=max_products,
        stop_early=stop_early,
        progress_callback=progress_callback,
    )


__all__ = ['run_universal_site_engine']
