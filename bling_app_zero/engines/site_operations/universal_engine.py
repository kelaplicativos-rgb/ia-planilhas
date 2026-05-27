from __future__ import annotations

from collections.abc import Callable, Iterable

import pandas as pd

from bling_app_zero.engines.fast_site_scraper import run_fast_site_scraper
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
    """Escolhe o modo interno sem desrespeitar o contrato universal.

    O fluxo universal recebe qualquer modelo. Quando o contrato pede apenas campos
    típicos de estoque/identificação, usar o motor interno de estoque evita trazer
    campos ricos de cadastro sem necessidade. Quando aparecem preço, imagens,
    marca, categoria ou descrição rica, cadastro continua sendo o modo mais
    completo e seguro.
    """
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
    plan = build_submotor_plan('universal', columns)
    internal_operation = _operation_from_universal_contract(plan)
    _emit(progress_callback, {
        'stage': 'Motor universal',
        'message': f'Origem única por modelo. Submotores ativos: {plan.summary}. Modo interno: {internal_operation}.',
        'progress': 0.04,
        'submotors': plan.active,
        'operation': plan.operation,
        'internal_operation': internal_operation,
    })

    # Em sites Stoqui/React, a API interna deve operar primeiro porque o HTML
    # público costuma vir vazio. A API respeita o mesmo contrato de colunas e
    # agora recebe o modo interno calculado pelo contrato universal.
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

    # Fallback genérico: usa o mesmo modo interno calculado pelo contrato.
    # Cadastro continua completo; estoque fica enxuto quando o modelo pedir apenas
    # identificação/descrição/saldo.
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
