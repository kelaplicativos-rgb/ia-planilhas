from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable

import pandas as pd

from bling_app_zero.agents.site_ai_validator import SmartScanQuality, evaluate_site_dataframe, normalize_site_dataframe
from bling_app_zero.agents.site_platform_detector import SitePlatformSignal, detect_site_platform
from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/agents/site_capture_agent.py'


@dataclass(frozen=True)
class SmartScanReport:
    platform: SitePlatformSignal
    quality: SmartScanQuality
    strategy: str
    used_ai_validation: bool
    message: str


def _emit(progress_callback: Callable[[dict], None] | None, payload: dict) -> None:
    if not progress_callback:
        return
    try:
        progress_callback(payload)
    except Exception:
        pass


def _strategy_for(platform: SitePlatformSignal, operation: str) -> str:
    if platform.platform in {'stoqui', 'mega_center'}:
        return 'api_first_then_fast_scraper'
    if platform.platform in {'shopify', 'woocommerce', 'loja_integrada', 'nuvemshop', 'tray'}:
        return 'platform_hints_then_fast_scraper'
    if operation == 'estoque':
        return 'stock_safe_batch_with_ai_validation'
    return 'generic_safe_batch_with_ai_validation'


def run_bling_smartscan(
    *,
    raw_urls: str,
    operation: str,
    requested_columns: list[str] | None,
    engine_runner: Callable[..., pd.DataFrame],
    all_products: bool,
    max_pages: int,
    max_products: int,
    progress_callback: Callable[[dict], None] | None = None,
) -> tuple[pd.DataFrame, SmartScanReport]:
    """Executa captura inteligente com IA operacional.

    Esta primeira versão não depende de API externa de LLM. Ela usa heurísticas fortes,
    validação de qualidade e normalização inteligente para comandar o motor atual.
    A camada LLM pode ser plugada depois sem alterar a UI.
    """
    platform = detect_site_platform(raw_urls)
    strategy = _strategy_for(platform, operation)
    _emit(progress_callback, {
        'stage': 'BLINGSMARTSCAN',
        'message': f'Plataforma provável: {platform.platform} ({int(platform.confidence * 100)}%). Estratégia: {strategy}.',
        'progress': 0.04,
        'platform': platform.platform,
        'platform_confidence': platform.confidence,
        'strategy': strategy,
    })
    add_audit_event(
        'blingsmartscan_started',
        area='SITE',
        step='entrada',
        status='OK',
        details={
            'platform': asdict(platform),
            'strategy': strategy,
            'operation': operation,
            'requested_columns_count': len(requested_columns or []),
            'max_pages': int(max_pages),
            'max_products': int(max_products),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )

    df = engine_runner(
        operation=operation,
        raw_urls=raw_urls,
        requested_columns=requested_columns,
        all_products=all_products,
        max_pages=max_pages,
        max_products=max_products,
        progress_callback=progress_callback,
    )

    normalized_df = normalize_site_dataframe(df)
    quality = evaluate_site_dataframe(normalized_df, operation=operation)
    message = f'BLINGSMARTSCAN finalizado com nota {quality.score}/100 e {quality.rows} produto(s) capturado(s).'
    _emit(progress_callback, {
        'stage': 'Validação inteligente',
        'message': message,
        'progress': 0.94,
        'quality_score': quality.score,
        'rows': quality.rows,
        'good_rows': quality.good_rows,
        'missing_price': quality.missing_price,
        'missing_description': quality.missing_description,
        'missing_stock': quality.missing_stock,
        'invalid_brand': quality.invalid_brand,
        'warnings': quality.warnings,
    })

    report = SmartScanReport(
        platform=platform,
        quality=quality,
        strategy=strategy,
        used_ai_validation=True,
        message=message,
    )
    add_audit_event(
        'blingsmartscan_finished',
        area='SITE',
        step='entrada',
        status='OK' if quality.rows else 'AVISO',
        details={
            'platform': asdict(platform),
            'strategy': strategy,
            'quality': asdict(quality),
            'operation': operation,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return normalized_df, report


__all__ = ['SmartScanReport', 'run_bling_smartscan']
