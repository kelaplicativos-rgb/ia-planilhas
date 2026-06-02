from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable

import pandas as pd

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.column_contract import build_contract
from bling_app_zero.core.debug import add_debug
from bling_app_zero.engines.fast_site_scraper.completeness import is_complete_product, should_stop_early
from bling_app_zero.engines.fast_site_scraper.constants import (
    MAX_WORKERS,
    RESPONSIBLE_FILE,
    SAFE_CAPTURE_MAX_PAGES,
    SAFE_CAPTURE_MAX_PRODUCTS,
    SLOW_LINK_SECONDS,
    normalize_capture_limits,
)
from bling_app_zero.engines.fast_site_scraper.contract_rules import default_columns, important_kinds, needed_kinds
from bling_app_zero.engines.fast_site_scraper.models import FastProductData
from bling_app_zero.engines.fast_site_scraper.output_builder import ensure_columns, to_contract_row
from bling_app_zero.engines.fast_site_scraper.progress import emit
from bling_app_zero.engines.fast_site_scraper.rendered_fallback import enhance_products_sequentially
from bling_app_zero.engines.fast_site_scraper.scrape_worker import has_useful_data, scrape_one, url_only_row
from bling_app_zero.engines.fast_site_scraper.url_discovery import discover_product_urls


def _normalize_operation(operation: str) -> str:
    return 'estoque' if str(operation).strip().lower() == 'estoque' else 'cadastro'


def _limit_mode(normalized_operation: str, stop_early: bool) -> str:
    if normalized_operation == 'estoque' and not stop_early:
        return 'stock_balance_flow'
    return 'safe' if stop_early else 'deep'


def _prepare_contract(requested_columns: Iterable[str] | None, normalized_operation: str):
    columns = [str(column).strip() for column in (requested_columns or []) if str(column).strip()]
    if not columns:
        columns = default_columns(normalized_operation)
    contract = build_contract(columns)
    needed = needed_kinds(contract, normalized_operation)
    important = important_kinds(contract)
    return columns, contract, needed, important


def _audit_contract(normalized_operation: str, columns: list[str], needed: set[str]) -> None:
    add_audit_event(
        'site_scraper_contract_built',
        area='SITE',
        details={
            'operation': normalized_operation,
            'columns': columns[:80],
            'needed_kinds': sorted(needed),
            'dynamic_render_fallback_enabled': True,
            'rich_description_enabled': 'descricao_complementar' in needed,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _read_products_parallel(
    *,
    urls: list[str],
    needed: set[str],
    important: set[str],
    max_products: int,
    stop_early: bool,
    progress_callback: Callable[[dict], None] | None,
) -> tuple[list[tuple[str, FastProductData]], int, int, int, str, list[dict[str, object]]]:
    products_by_url: list[tuple[str, FastProductData]] = []
    errors = 0
    complete_count = 0
    last_gain_at = 0
    stop_reason = ''
    slow_links: list[dict[str, object]] = []
    workers = max(1, min(MAX_WORKERS, len(urls)))
    total = len(urls[:max_products])
    processed = 0
    last_emit = time.perf_counter()

    emit(progress_callback, {
        'stage': 'Lendo produtos',
        'message': f'Lendo até {total} produto(s). Fallback dinâmico ativo para páginas carregadas por JavaScript.',
        'progress': 0.28,
        'processed': 0,
        'total': total,
        'workers': workers,
        'stop_early': bool(stop_early),
        'rich_description_enabled': 'descricao_complementar' in needed,
        'dynamic_render_fallback_enabled': True,
    })

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(scrape_one, url, needed): url for url in urls[:max_products]}
        for future in as_completed(futures):
            processed += 1
            try:
                url, product, elapsed, failed = future.result()
                if failed:
                    errors += 1
                if elapsed >= SLOW_LINK_SECONDS:
                    slow_links.append({'url': url, 'seconds': round(elapsed, 2)})
                if has_useful_data(product, needed):
                    products_by_url.append((url, product))
                    last_gain_at = processed
                    if is_complete_product(product, important):
                        complete_count += 1
            except Exception:
                errors += 1

            if stop_early:
                should_stop, reason = should_stop_early(
                    processed=processed,
                    products=[product for _, product in products_by_url],
                    complete_count=complete_count,
                    last_gain_at=last_gain_at,
                )
                if should_stop:
                    stop_reason = reason
                    for pending in futures:
                        if not pending.done():
                            pending.cancel()
                    emit(progress_callback, {
                        'stage': 'Busca suficiente',
                        'message': stop_reason,
                        'progress': 0.86,
                        'processed': processed,
                        'total': total,
                        'found': len(products_by_url),
                        'complete': complete_count,
                        'errors': errors,
                        'devtools': 0,
                        'slow_links': slow_links[-5:],
                    })
                    break

            now = time.perf_counter()
            if now - last_emit >= 0.5 or processed == total:
                ratio = processed / max(total, 1)
                emit(progress_callback, {
                    'stage': 'Lendo produtos',
                    'message': f'{processed}/{total} produto(s) lido(s).',
                    'progress': 0.28 + (0.58 * ratio),
                    'processed': processed,
                    'total': total,
                    'found': len(products_by_url),
                    'complete': complete_count,
                    'errors': errors,
                    'devtools': 0,
                    'slow_links': slow_links[-5:],
                    'stop_early': bool(stop_early),
                    'rich_description_enabled': 'descricao_complementar' in needed,
                    'dynamic_render_fallback_enabled': True,
                })
                last_emit = now

    return products_by_url, processed, errors, complete_count, stop_reason, slow_links


def _audit_finished(
    *,
    normalized_operation: str,
    products: list[FastProductData],
    rendered_fallbacks: int,
    errors: int,
    needed: set[str],
) -> tuple[int, int]:
    rich_ok = sum(1 for product in products if len(str(product.descricao_complementar or '').strip()) >= 80)
    rich_empty = sum(1 for product in products if not str(product.descricao_complementar or '').strip())

    add_audit_event(
        'site_scraper_finished',
        area='SITE',
        status='OK',
        details={
            'operation': normalized_operation,
            'products': len(products),
            'dynamic_render_fallback_enabled': True,
            'rich_description_enabled': 'descricao_complementar' in needed,
            'rich_description_ok': rich_ok,
            'rich_description_empty': rich_empty,
            'devtools': rendered_fallbacks,
            'errors': errors,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    add_debug(
        f'Busca por site finalizada: {len(products)} produto(s), DevTools reforçou {rendered_fallbacks}, descrição rica OK em {rich_ok}, vazia em {rich_empty}.',
        origin='SITE_CAPTURA_DINAMICA',
        level='INFO',
        file_name=RESPONSIBLE_FILE,
        details={'rich_description_enabled': 'descricao_complementar' in needed, 'dynamic_render_fallback_enabled': True, 'devtools': rendered_fallbacks, 'errors': errors},
    )
    return rich_ok, rich_empty


def run_fast_site_scraper(
    raw_urls: str,
    requested_columns: Iterable[str] | None = None,
    operation: str = 'cadastro',
    max_pages: int = SAFE_CAPTURE_MAX_PAGES,
    max_products: int = SAFE_CAPTURE_MAX_PRODUCTS,
    stop_early: bool = True,
    progress_callback: Callable[[dict], None] | None = None,
) -> pd.DataFrame:
    total_started = time.perf_counter()
    normalized_operation = _normalize_operation(operation)
    columns, contract, needed, important = _prepare_contract(requested_columns, normalized_operation)

    limits = normalize_capture_limits(
        max_pages=max_pages,
        max_products=max_products,
        mode=_limit_mode(normalized_operation, stop_early),
    )
    max_pages = int(limits['max_pages'])
    max_products = int(limits['max_products'])
    safe_limited = bool(limits.get('safe_limited'))
    flow_mode = bool(limits.get('flow_mode'))

    _audit_contract(normalized_operation, columns, needed)
    add_audit_event(
        'site_scraper_limits_normalized',
        area='SITE',
        status='OK',
        details={
            'operation': normalized_operation,
            'max_pages': int(max_pages),
            'max_products': int(max_products),
            'stop_early': bool(stop_early),
            'safe_limited': safe_limited,
            'flow_mode': flow_mode,
            'limit_mode': _limit_mode(normalized_operation, stop_early),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )

    emit(progress_callback, {
        'stage': 'Procurando links em fluxo contínuo' if flow_mode else 'Procurando links',
        'message': f'Procurando produtos nos links informados com limite técnico de {max_pages} página(s) e {max_products} produto(s)...',
        'progress': 0.08,
        'columns': len(columns),
        'max_pages': max_pages,
        'max_products': max_products,
        'safe_limited': safe_limited,
        'flow_mode': flow_mode,
    })
    discovery_started = time.perf_counter()
    urls = discover_product_urls(raw_urls, max_pages=max_pages, max_products=max_products)
    discovery_seconds = time.perf_counter() - discovery_started

    if len(urls) > max_products:
        urls = urls[:max_products]

    emit(progress_callback, {
        'stage': 'Links encontrados',
        'message': f'{len(urls)} link(s) de produto separados para leitura.',
        'progress': 0.22,
        'urls_found': len(urls),
        'discovery_seconds': round(discovery_seconds, 2),
        'max_products': max_products,
        'safe_limited': safe_limited,
        'flow_mode': flow_mode,
    })
    if not urls:
        emit(progress_callback, {'stage': 'Nada encontrado', 'message': 'Não encontrei produtos nos links informados. Confira se o link abre produtos ou categorias.', 'progress': 1.0, 'urls_found': 0})
        return pd.DataFrame(columns=columns)

    if needed <= {'url'}:
        rows = [to_contract_row(url_only_row(url), contract) for url in urls[:max_products]]
        emit(progress_callback, {
            'stage': 'Pronto',
            'message': f'{len(rows)} link(s) preparados para a origem.',
            'progress': 0.92,
            'processed': len(rows),
            'urls_found': len(urls),
            'total_seconds': round(time.perf_counter() - total_started, 2),
            'safe_limited': safe_limited,
            'flow_mode': flow_mode,
        })
        return ensure_columns(pd.DataFrame(rows).fillna(''), columns)

    products_by_url, processed, errors, complete_count, stop_reason, slow_links = _read_products_parallel(
        urls=urls,
        needed=needed,
        important=important,
        max_products=max_products,
        stop_early=stop_early,
        progress_callback=progress_callback,
    )

    products, rendered_fallbacks = enhance_products_sequentially(products_by_url, needed, progress_callback)
    rich_ok, rich_empty = _audit_finished(
        normalized_operation=normalized_operation,
        products=products,
        rendered_fallbacks=rendered_fallbacks,
        errors=errors,
        needed=needed,
    )

    rows = [to_contract_row(product, contract) for product in products]
    final_message = f'Montando origem com {len(rows)} produto(s).'
    if rendered_fallbacks:
        final_message = f'{final_message} DevTools reforçou {rendered_fallbacks} página(s), em fila.'
    if stop_reason:
        final_message = f'{final_message} {stop_reason}'
    emit(progress_callback, {
        'stage': 'Montando origem',
        'message': final_message,
        'progress': 0.91,
        'processed': processed,
        'found': len(products),
        'complete': complete_count,
        'errors': errors,
        'devtools': rendered_fallbacks,
        'slow_links': slow_links[-10:],
        'total_seconds': round(time.perf_counter() - total_started, 2),
        'stop_early': bool(stop_early),
        'rich_description_ok': rich_ok,
        'rich_description_empty': rich_empty,
        'dynamic_render_fallback_enabled': True,
        'max_pages': max_pages,
        'max_products': max_products,
        'safe_limited': safe_limited,
        'flow_mode': flow_mode,
    })
    return ensure_columns(pd.DataFrame(rows).fillna(''), columns)


__all__ = ['run_fast_site_scraper']
