from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable

import pandas as pd

from bling_app_zero.agents.api_finder import ApiFinderResult, find_site_api, try_read_api_table
from bling_app_zero.agents.blingsmartcore import apply_blingsmartcore
from bling_app_zero.agents.site_ai_validator import SmartScanQuality
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
    api_finder: ApiFinderResult | None = None
    used_api: bool = False


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


def _should_try_api(strategy: str, platform: SitePlatformSignal) -> bool:
    return strategy.startswith('api_first') or platform.platform in {'stoqui', 'mega_center', 'shopify', 'woocommerce', 'loja_integrada', 'nuvemshop', 'tray'}


def _run_engine(
    *,
    raw_urls: str,
    operation: str,
    requested_columns: list[str] | None,
    engine_runner: Callable[..., pd.DataFrame],
    all_products: bool,
    max_pages: int,
    max_products: int,
    progress_callback: Callable[[dict], None] | None,
) -> pd.DataFrame:
    return engine_runner(
        operation=operation,
        raw_urls=raw_urls,
        requested_columns=requested_columns,
        all_products=all_products,
        max_pages=max_pages,
        max_products=max_products,
        progress_callback=progress_callback,
    )


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
    """Executa captura inteligente com API Finder + validação BLINGSMARTCORE."""
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

    api_result: ApiFinderResult | None = None
    used_api = False
    df = pd.DataFrame()
    if _should_try_api(strategy, platform):
        _emit(progress_callback, {
            'stage': 'API Finder',
            'message': 'Procurando API interna antes de raspar HTML...',
            'progress': 0.08,
            'platform': platform.platform,
        })
        api_result = find_site_api(raw_urls, platform=platform.platform)
        if api_result.found:
            api_df = try_read_api_table(api_result, max_items=max_products)
            if isinstance(api_df, pd.DataFrame) and not api_df.empty:
                df = api_df
                used_api = True
                _emit(progress_callback, {
                    'stage': 'API Finder',
                    'message': f'API interna usada como fonte principal: {len(df)} registro(s).',
                    'progress': 0.18,
                    'api_url': api_result.best_url,
                    'rows': len(df),
                })

    if not used_api:
        if api_result is not None:
            _emit(progress_callback, {
                'stage': 'API Finder',
                'message': f'{api_result.message} Continuando com scraper seguro.',
                'progress': 0.14,
                'candidates': len(api_result.candidates),
            })
        df = _run_engine(
            operation=operation,
            raw_urls=raw_urls,
            requested_columns=requested_columns,
            engine_runner=engine_runner,
            all_products=all_products,
            max_pages=max_pages,
            max_products=max_products,
            progress_callback=progress_callback,
        )

    normalized_df, core_result = apply_blingsmartcore(df, origin='site', operation=operation)
    quality = core_result.quality
    source = 'API interna' if used_api else 'scraper seguro'
    message = f'BLINGSMARTSCAN finalizado via {source} com nota {quality.score}/100 e {quality.rows} produto(s) capturado(s).'
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
        'used_api': used_api,
    })

    report = SmartScanReport(
        platform=platform,
        quality=quality,
        strategy=strategy,
        used_ai_validation=True,
        message=message,
        api_finder=api_result,
        used_api=used_api,
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
            'used_api': used_api,
            'api_finder': asdict(api_result) if api_result is not None else None,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return normalized_df, report


__all__ = ['SmartScanReport', 'run_bling_smartscan']
