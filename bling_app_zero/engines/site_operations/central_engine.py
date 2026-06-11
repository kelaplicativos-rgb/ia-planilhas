from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

import pandas as pd

from bling_app_zero.engines.fast_site_scraper import run_fast_site_scraper
from bling_app_zero.engines.fast_site_scraper.constants import (
    SAFE_CAPTURE_MAX_PAGES,
    SAFE_CAPTURE_MAX_PRODUCTS,
    normalize_capture_limits,
)
from bling_app_zero.engines.site_operations.contracts import cadastro_columns, estoque_columns
from bling_app_zero.engines.site_operations.stoqui_api_engine import can_handle_stoqui_url, run_stoqui_site_engine
from bling_app_zero.engines.site_operations.submotors import SiteSubmotorPlan, build_submotor_plan
from bling_app_zero.universal.model_contract_detector import normalize_contract_operation

RESPONSIBLE_FILE = 'bling_app_zero/engines/site_operations/central_engine.py'
VALID_OPERATIONS = {'cadastro', 'estoque', 'universal', 'atualizacao_preco'}
UNIVERSAL_ALIASES = {'universal', 'modelo', 'modelo_destino', 'planilha', 'wizard_cadastro_estoque'}
CADASTRO_RICH_SUBMOTORS = {'descricao_rica', 'preco', 'imagens', 'marca', 'categoria'}
ESTOQUE_COMPATIBLE_SUBMOTORS = {'links', 'identificacao', 'gtin', 'estoque', 'descricao'}
CADASTRO_OPERATION_ALIASES = {'cadastro', 'atualizacao_preco'}


@dataclass(frozen=True)
class ProductSiteSearchPlan:
    """Plano único para qualquer busca de produtos por site."""

    requested_operation: str
    selected_operation: str
    internal_operation: str
    columns: list[str]
    submotor_plan: SiteSubmotorPlan
    max_pages: int
    max_products: int
    stop_early: bool
    safe_limited: bool
    flow_mode: bool

    @property
    def summary(self) -> str:
        return self.submotor_plan.summary


def emit_site_progress(progress_callback: Callable[[dict], None] | None, payload: dict) -> None:
    """Emite progresso sem deixar erro de UI quebrar o motor."""
    if not progress_callback:
        return
    try:
        progress_callback(payload)
    except Exception:
        pass


def normalize_site_operation(operation: str | None) -> str:
    """Normaliza cadastro, estoque, universal e aliases vindos da UI/modelo."""
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


def _limit_mode(selected_operation: str, stop_early: bool) -> str:
    if selected_operation == 'estoque' and not stop_early:
        return 'stock_balance_flow'
    return 'safe' if stop_early else 'deep'


def _operation_from_universal_contract(plan: SiteSubmotorPlan) -> str:
    active = set(plan.active)
    if active and active <= ESTOQUE_COMPATIBLE_SUBMOTORS and 'estoque' in active:
        return 'estoque'
    if active & CADASTRO_RICH_SUBMOTORS:
        return 'cadastro'
    return 'cadastro'


def _columns_for_operation(selected_operation: str, requested_columns: Iterable[str] | None) -> list[str]:
    if selected_operation == 'estoque':
        return estoque_columns(requested_columns)
    return cadastro_columns(requested_columns)


def _submotor_operation(selected_operation: str) -> str:
    if selected_operation == 'estoque':
        return 'estoque'
    if selected_operation in CADASTRO_OPERATION_ALIASES:
        return 'cadastro'
    return 'universal'


def build_product_site_search_plan(
    *,
    operation: str | None,
    requested_columns: Iterable[str] | None = None,
    max_pages: int = SAFE_CAPTURE_MAX_PAGES,
    max_products: int = SAFE_CAPTURE_MAX_PRODUCTS,
    stop_early: bool = True,
) -> ProductSiteSearchPlan:
    """Monta o plano central de captura por site para cadastro, estoque ou universal."""
    selected_operation = normalize_site_operation(operation)
    capture_stop_early = bool(stop_early)
    limits = normalize_capture_limits(
        max_pages=max_pages,
        max_products=max_products,
        mode=_limit_mode(selected_operation, capture_stop_early),
    )
    safe_max_pages = int(limits['max_pages'])
    safe_max_products = int(limits['max_products'])
    columns = _columns_for_operation(selected_operation, requested_columns)
    submotor_operation = _submotor_operation(selected_operation)
    submotor_plan = build_submotor_plan(submotor_operation, columns)

    if selected_operation == 'universal':
        internal_operation = _operation_from_universal_contract(submotor_plan)
    elif selected_operation == 'estoque':
        internal_operation = 'estoque'
    else:
        internal_operation = 'cadastro'

    return ProductSiteSearchPlan(
        requested_operation=str(operation or 'universal'),
        selected_operation=selected_operation,
        internal_operation=internal_operation,
        columns=columns,
        submotor_plan=submotor_plan,
        max_pages=safe_max_pages,
        max_products=safe_max_products,
        stop_early=capture_stop_early,
        safe_limited=bool(limits.get('safe_limited')),
        flow_mode=bool(limits.get('flow_mode')),
    )


def _emit_plan(progress_callback: Callable[[dict], None] | None, plan: ProductSiteSearchPlan) -> None:
    stage_by_operation = {
        'cadastro': 'Motor central de cadastro por site',
        'estoque': 'Motor central de estoque por site',
        'universal': 'Motor central universal por site',
        'atualizacao_preco': 'Motor central de preço por site',
    }
    stage = stage_by_operation.get(plan.selected_operation, 'Motor central de busca por site')
    message = f'Submotores ativos: {plan.summary}. Modo interno: {plan.internal_operation}.'
    if plan.selected_operation == 'universal':
        message = f'Origem única por modelo. {message}'

    emit_site_progress(progress_callback, {
        'stage': stage,
        'message': message,
        'progress': 0.04,
        'submotors': plan.submotor_plan.active,
        'operation': plan.selected_operation,
        'requested_operation': plan.requested_operation,
        'internal_operation': plan.internal_operation,
        'max_pages': plan.max_pages,
        'max_products': plan.max_products,
        'stop_early': plan.stop_early,
        'safe_limited': plan.safe_limited,
        'flow_mode': plan.flow_mode,
        'responsible_file': RESPONSIBLE_FILE,
    })


def run_product_site_search(
    *,
    raw_urls: str,
    operation: str | None = 'universal',
    requested_columns: Iterable[str] | None = None,
    max_pages: int = SAFE_CAPTURE_MAX_PAGES,
    max_products: int = SAFE_CAPTURE_MAX_PRODUCTS,
    stop_early: bool = True,
    progress_callback: Callable[[dict], None] | None = None,
) -> pd.DataFrame:
    """Entrada única para busca de produtos por site.

    Este módulo centraliza os recursos antes espalhados entre router,
    cadastro_engine, estoque_engine e universal_engine:
    - normalização da operação;
    - escolha de contrato/colunas;
    - plano de submotores;
    - limites de captura;
    - decisão Stoqui API ou scraper universal;
    - chamada final do fast_site_scraper.
    """
    plan = build_product_site_search_plan(
        operation=operation,
        requested_columns=requested_columns,
        max_pages=max_pages,
        max_products=max_products,
        stop_early=stop_early,
    )

    if plan.selected_operation == 'estoque' and not plan.columns:
        emit_site_progress(progress_callback, {
            'stage': 'Modelo obrigatório',
            'message': 'Estoque por site exige modelo/contrato de colunas. Nenhuma captura foi executada.',
            'progress': 1.0,
            'operation': plan.selected_operation,
            'responsible_file': RESPONSIBLE_FILE,
        })
        return pd.DataFrame()

    _emit_plan(progress_callback, plan)

    if can_handle_stoqui_url(raw_urls):
        df_stoqui = run_stoqui_site_engine(
            raw_urls=raw_urls,
            requested_columns=plan.columns,
            operation=plan.internal_operation,
            max_products=plan.max_products,
            progress_callback=progress_callback,
        )
        if isinstance(df_stoqui, pd.DataFrame) and not df_stoqui.empty:
            return df_stoqui

    return run_fast_site_scraper(
        raw_urls=raw_urls,
        requested_columns=plan.columns,
        operation=plan.internal_operation,
        max_pages=plan.max_pages,
        max_products=plan.max_products,
        stop_early=plan.stop_early,
        progress_callback=progress_callback,
    )


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
    return run_product_site_search(
        raw_urls=raw_urls,
        operation=operation,
        requested_columns=requested_columns,
        max_pages=max_pages,
        max_products=max_products,
        stop_early=stop_early,
        progress_callback=progress_callback,
    )


def run_cadastro_site_engine(
    *,
    raw_urls: str,
    requested_columns: Iterable[str] | None = None,
    max_pages: int = SAFE_CAPTURE_MAX_PAGES,
    max_products: int = SAFE_CAPTURE_MAX_PRODUCTS,
    stop_early: bool = True,
    progress_callback: Callable[[dict], None] | None = None,
) -> pd.DataFrame:
    return run_product_site_search(
        raw_urls=raw_urls,
        operation='cadastro',
        requested_columns=requested_columns,
        max_pages=max_pages,
        max_products=max_products,
        stop_early=stop_early,
        progress_callback=progress_callback,
    )


def run_estoque_site_engine(
    *,
    raw_urls: str,
    requested_columns: Iterable[str] | None = None,
    max_pages: int = SAFE_CAPTURE_MAX_PAGES,
    max_products: int = SAFE_CAPTURE_MAX_PRODUCTS,
    stop_early: bool = True,
    progress_callback: Callable[[dict], None] | None = None,
) -> pd.DataFrame:
    return run_product_site_search(
        raw_urls=raw_urls,
        operation='estoque',
        requested_columns=requested_columns,
        max_pages=max_pages,
        max_products=max_products,
        stop_early=stop_early,
        progress_callback=progress_callback,
    )


def run_universal_site_engine(
    *,
    raw_urls: str,
    requested_columns: Iterable[str] | None = None,
    max_pages: int = SAFE_CAPTURE_MAX_PAGES,
    max_products: int = SAFE_CAPTURE_MAX_PRODUCTS,
    stop_early: bool = True,
    progress_callback: Callable[[dict], None] | None = None,
) -> pd.DataFrame:
    return run_product_site_search(
        raw_urls=raw_urls,
        operation='universal',
        requested_columns=requested_columns,
        max_pages=max_pages,
        max_products=max_products,
        stop_early=stop_early,
        progress_callback=progress_callback,
    )


# Compatibilidade com o nome antigo do roteador.
normalize_operation = normalize_site_operation

__all__ = [
    'ProductSiteSearchPlan',
    'build_product_site_search_plan',
    'emit_site_progress',
    'normalize_operation',
    'normalize_site_operation',
    'run_cadastro_site_engine',
    'run_estoque_site_engine',
    'run_product_site_search',
    'run_site_operation_engine',
    'run_universal_site_engine',
]
