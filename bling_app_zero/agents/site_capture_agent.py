from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

import pandas as pd

from bling_app_zero.agents.api_finder import ApiFinderResult, find_site_api, try_read_api_table
from bling_app_zero.agents.blingsmartcore import apply_blingsmartcore
from bling_app_zero.agents.site_ai_validator import SmartScanQuality
from bling_app_zero.agents.site_platform_detector import SitePlatformSignal, detect_site_platform
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.engines.fast_site_scraper import run_fast_site_scraper

RESPONSIBLE_FILE = 'bling_app_zero/agents/site_capture_agent.py'
SMARTSCAN_SAFE_URL_BATCH = 1200
PLATFORM_HINT_SCRAPER = {'shopify', 'woocommerce', 'loja_integrada', 'nuvemshop', 'tray', 'wbuy'}


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
    if platform.platform in PLATFORM_HINT_SCRAPER:
        return 'platform_hints_then_fast_scraper'
    return 'generic_safe_batch_with_ai_validation'


def _should_try_api(strategy: str, platform: SitePlatformSignal) -> bool:
    return strategy.startswith('api_first') or platform.platform in {'stoqui', 'mega_center', *PLATFORM_HINT_SCRAPER}


def _url_lines(raw_urls: str) -> list[str]:
    lines = [line.strip() for line in re.split(r'[\n,;]+', str(raw_urls or '')) if line.strip().startswith(('http://', 'https://'))]
    return list(dict.fromkeys(lines))


def _limit_raw_urls(raw_urls: str, *, max_products: int) -> tuple[str, int, int]:
    lines = _url_lines(raw_urls)
    original = len(lines)
    if not lines:
        return str(raw_urls or ''), 0, 0
    limit = max(1, min(int(max_products or SMARTSCAN_SAFE_URL_BATCH), SMARTSCAN_SAFE_URL_BATCH))
    limited = lines[:limit]
    return '\n'.join(limited), original, len(limited)


def _url_key(value: object) -> str:
    text = str(value or '').strip()
    if not text.startswith(('http://', 'https://')):
        return ''
    try:
        parts = urlsplit(text)
        path = re.sub(r'/+$', '', parts.path or '')
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, '', ''))
    except Exception:
        return text.rstrip('/').lower()


def _url_column(df: pd.DataFrame) -> str:
    if not isinstance(df, pd.DataFrame):
        return ''
    for column in df.columns:
        key = re.sub(r'[^a-z0-9]+', ' ', str(column or '').strip().lower()).strip()
        if key in {'url', 'link', 'produto url', 'url produto', 'link produto'}:
            return str(column)
    for column in df.columns:
        key = str(column or '').strip().lower()
        if 'url' in key or 'link' in key:
            return str(column)
    return ''


def _pending_urls(raw_urls: str, df: pd.DataFrame) -> tuple[list[str], list[str]]:
    source_urls = _url_lines(raw_urls)
    if len(source_urls) <= 1 or not isinstance(df, pd.DataFrame) or df.empty:
        return [], []
    url_col = _url_column(df)
    if not url_col:
        return [], []
    processed_keys = {_url_key(value) for value in df[url_col].tolist() if _url_key(value)}
    processed_urls = [url for url in source_urls if _url_key(url) in processed_keys]
    pending = [url for url in source_urls if _url_key(url) not in processed_keys]
    return pending, processed_urls


def _checkpoint_and_resume_if_partial(
    *,
    raw_urls: str,
    df: pd.DataFrame,
    operation: str,
    requested_columns: list[str] | None,
    progress_callback: Callable[[dict], None] | None,
) -> None:
    pending, processed_urls = _pending_urls(raw_urls, df)
    if not pending:
        return

    rows = df.fillna('').to_dict(orient='records')
    payload = {
        'stage': 'Lote parcial preservado',
        'message': f'{len(df)} produto(s) lido(s). Restam {len(pending)}; a busca continuará automaticamente.',
        'progress': 0.88,
        'processed': len(processed_urls),
        'total': len(processed_urls) + len(pending),
        'found': len(df),
        'partial_checkpoint_enabled': True,
        'partial_checkpoint_rows': rows,
        'partial_checkpoint_columns': [str(column) for column in df.columns],
        'partial_checkpoint_operation': operation,
        'partial_checkpoint_found': len(df),
        'partial_checkpoint_processed_urls': processed_urls,
        'partial_checkpoint_pending_urls': pending,
        'remaining_products': len(pending),
    }
    _emit(progress_callback, payload)
    add_audit_event(
        'blingsmartscan_partial_batch_resume_required',
        area='SITE',
        step='entrada',
        status='AVISO',
        details={
            'operation': operation,
            'source_urls': len(processed_urls) + len(pending),
            'captured_rows': len(df),
            'processed_urls': len(processed_urls),
            'pending_urls': len(pending),
            'requested_columns_count': len(requested_columns or []),
            'auto_resume': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    raise RuntimeError(
        f'Lote parcial preservado: {len(df)} produto(s) lido(s) e {len(pending)} restante(s). '
        'A continuação automática foi preparada.'
    )


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


def _empty_df(df: pd.DataFrame) -> bool:
    return not isinstance(df, pd.DataFrame) or df.empty


def _force_wbuy_empty_retry(
    *,
    raw_urls: str,
    operation: str,
    requested_columns: list[str] | None,
    all_products: bool,
    max_pages: int,
    max_products: int,
    progress_callback: Callable[[dict], None] | None,
) -> pd.DataFrame:
    _emit(progress_callback, {
        'stage': 'Fallback wBuy obrigatório',
        'message': 'A captura principal voltou vazia em plataforma wBuy. Tentando vitrines, buscas e cards públicos antes de encerrar.',
        'progress': 0.875,
        'platform': 'wbuy',
    })
    add_audit_event(
        'blingsmartscan_wbuy_empty_retry_started',
        area='SITE',
        step='entrada',
        status='AVISO',
        details={
            'operation': operation,
            'requested_columns_count': len(requested_columns or []),
            'all_products': bool(all_products),
            'max_pages': int(max_pages),
            'max_products': int(max_products),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    try:
        retry_df = run_fast_site_scraper(
            raw_urls=raw_urls,
            requested_columns=requested_columns,
            operation=operation,
            max_pages=max_pages,
            max_products=max_products,
            stop_early=not bool(all_products),
            progress_callback=progress_callback,
        )
    except Exception as exc:
        add_audit_event(
            'blingsmartscan_wbuy_empty_retry_failed',
            area='SITE',
            step='entrada',
            status='ERRO',
            details={
                'operation': operation,
                'error': str(exc),
                'error_type': exc.__class__.__name__,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return pd.DataFrame()

    rows = len(retry_df) if isinstance(retry_df, pd.DataFrame) else 0
    add_audit_event(
        'blingsmartscan_wbuy_empty_retry_finished',
        area='SITE',
        step='entrada',
        status='OK' if rows else 'AVISO',
        details={
            'operation': operation,
            'rows': rows,
            'columns': len(retry_df.columns) if isinstance(retry_df, pd.DataFrame) else 0,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    if rows:
        _emit(progress_callback, {
            'stage': 'Fallback wBuy recuperou produtos',
            'message': f'{rows} produto(s) recuperado(s) depois da captura principal vazia.',
            'progress': 0.91,
            'found': rows,
            'platform': 'wbuy',
        })
    return retry_df if isinstance(retry_df, pd.DataFrame) else pd.DataFrame()


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
    platform = detect_site_platform(raw_urls)
    strategy = _strategy_for(platform, operation)
    max_products = max(1, min(int(max_products or SMARTSCAN_SAFE_URL_BATCH), SMARTSCAN_SAFE_URL_BATCH))
    raw_urls, original_urls, used_urls = _limit_raw_urls(raw_urls, max_products=max_products)
    if original_urls > used_urls:
        add_audit_event(
            'site_smartscan_url_batch_limited',
            area='SITE',
            step='entrada',
            status='OK',
            details={
                'operation': operation,
                'original_urls': original_urls,
                'used_urls': used_urls,
                'reason': 'Evitar trava do Streamlit; captura roda em lote curto.',
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        _emit(progress_callback, {
            'stage': 'Lote seguro',
            'message': f'{original_urls} links encontrados. Processando primeiro lote com {used_urls} para evitar travamento.',
            'progress': 0.18,
            'original_urls': original_urls,
            'used_urls': used_urls,
        })

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
            'url_batch_original': original_urls,
            'url_batch_used': used_urls,
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
        if platform.platform == 'wbuy' and _empty_df(df):
            df = _force_wbuy_empty_retry(
                raw_urls=raw_urls,
                operation=operation,
                requested_columns=requested_columns,
                all_products=all_products,
                max_pages=max_pages,
                max_products=max_products,
                progress_callback=progress_callback,
            )
        _checkpoint_and_resume_if_partial(
            raw_urls=raw_urls,
            df=df,
            operation=operation,
            requested_columns=requested_columns,
            progress_callback=progress_callback,
        )

    normalized_df, core_result = apply_blingsmartcore(df, origin='site', operation=operation)
    quality = core_result.quality
    source = 'API interna' if used_api else 'scraper seguro'
    message = f'Busca por site finalizada via {source} com nota {quality.score}/100 e {quality.rows} produto(s) capturado(s).'
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
            'url_batch_original': original_urls,
            'url_batch_used': used_urls,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return normalized_df, report


__all__ = ['SmartScanReport', 'run_bling_smartscan']
