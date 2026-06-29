from __future__ import annotations

import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Callable, Iterable
from urllib.parse import urlencode, urlparse

import pandas as pd

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.column_contract import build_contract
from bling_app_zero.core.debug import add_debug
from bling_app_zero.engines.fast_site_scraper.completeness import is_complete_product, should_stop_early
from bling_app_zero.engines.fast_site_scraper.constants import (
    MAX_WORKERS,
    PRODUCT_READ_BUDGET_SECONDS,
    RESPONSIBLE_FILE,
    SAFE_CAPTURE_MAX_PAGES,
    SAFE_CAPTURE_MAX_PRODUCTS,
    SLOW_LINK_SECONDS,
    STREAMLIT_HARD_BUDGET_SECONDS,
    normalize_capture_limits,
)
from bling_app_zero.engines.fast_site_scraper.contract_rules import default_columns, important_kinds, needed_kinds
from bling_app_zero.engines.fast_site_scraper.http_client import fetch_many_live
from bling_app_zero.engines.fast_site_scraper.models import FastProductData
from bling_app_zero.engines.fast_site_scraper.openai_catalog_fallback import openai_catalog_products
from bling_app_zero.engines.fast_site_scraper.output_builder import ensure_columns, to_contract_row
from bling_app_zero.engines.fast_site_scraper.progress import emit
from bling_app_zero.engines.fast_site_scraper.rendered_fallback import enhance_products_sequentially
from bling_app_zero.engines.fast_site_scraper.scrape_worker import has_useful_data, scrape_one, url_only_row
from bling_app_zero.engines.fast_site_scraper.url_discovery import discover_product_urls, norm_url, split_urls
from bling_app_zero.engines.fast_site_scraper.wbuy_parser import wbuy_listing_products

WBUY_FALLBACK_MIN_PRODUCTS = 24
WBUY_FALLBACK_PAGE_LIMIT = 48
WBUY_FALLBACK_SEARCH_TERMS = (
    'smartwatch', 'relogio', 'relógio', 'peje', 'microwear', 'fone', 'fone bluetooth',
    'caixa', 'caixa som', 'camera', 'câmera', 'xiaomi', 'iphone', 'celular',
    'carregador', 'cabo', 'usb', 'tipo c', 'pelicula', 'película', 'capinha',
    'suporte', 'power bank', 'controle', 'teclado', 'mouse', 'microfone', 'lanterna',
    'produto',
)
WBUY_FALLBACK_QUERY_KEYS = ('q', 'term', 'query', 'keyword', 'palavra', 'palavra_busca', 'busca')
WBUY_FALLBACK_BROWSE_PATHS = (
    '/',
    '/produtos',
    '/produtos/',
    '/mais-produtos',
    '/categoria/mais-produtos',
    '/smartwatch',
    '/acessorios',
    '/celulares-smartphone',
)
WBUY_FALLBACK_SEARCH_ENDPOINTS = (
    '/produtos_autocomplete.php',
    '/busca/',
    '/busca',
    '/buscar',
    '/pesquisa',
)


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
            'partial_checkpoint_enabled': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _seconds_left(started: float, budget_seconds: float) -> float:
    return max(0.0, float(budget_seconds) - (time.perf_counter() - started))


def _root_url(url: str) -> str:
    parsed = urlparse(str(url or '').strip())
    if not parsed.scheme or not parsed.netloc:
        return ''
    return f'{parsed.scheme}://{parsed.netloc}'


def _append_unique_url(target: list[str], url: str) -> None:
    clean = norm_url(url)
    if clean and clean not in target:
        target.append(clean)


def _wbuy_candidate_pages(raw_urls: str, max_products: int) -> list[str]:
    starts = [norm_url(url) for url in split_urls(raw_urls) if norm_url(url)]
    starts = list(dict.fromkeys(starts))
    roots = list(dict.fromkeys(root for root in (_root_url(url) for url in starts) if root))
    pages: list[str] = []

    for start in starts:
        _append_unique_url(pages, start)

    page_count = max(2, min(6, int(max_products or WBUY_FALLBACK_MIN_PRODUCTS) // 24 + 2))
    for root in roots:
        for path in WBUY_FALLBACK_BROWSE_PATHS:
            _append_unique_url(pages, f'{root}{path}')
            separator = '&' if '?' in path else '?'
            for page in range(2, page_count + 1):
                for page_key in ('pg', 'page', 'pagina'):
                    _append_unique_url(pages, f'{root}{path}{separator}{urlencode({page_key: page})}')

        for term in WBUY_FALLBACK_SEARCH_TERMS:
            for endpoint in WBUY_FALLBACK_SEARCH_ENDPOINTS:
                for query_key in WBUY_FALLBACK_QUERY_KEYS:
                    _append_unique_url(pages, f'{root}{endpoint}?{urlencode({query_key: term})}')

    return pages[:WBUY_FALLBACK_PAGE_LIMIT]


def _product_identity(product: FastProductData) -> str:
    for value in (product.codigo, product.gtin, product.url, product.descricao):
        text = str(value or '').strip().lower()
        if text:
            return text
    return ''


def _merge_products_by_identity(
    primary: list[FastProductData],
    extra: list[FastProductData],
    *,
    max_products: int,
) -> list[FastProductData]:
    merged: list[FastProductData] = []
    seen: set[str] = set()
    for product in [*primary, *extra]:
        key = _product_identity(product)
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        merged.append(product)
        if len(merged) >= max_products:
            break
    return merged


def _partial_checkpoint_payload(
    *,
    products_by_url: list[tuple[str, FastProductData]],
    contract,
    columns: list[str],
    normalized_operation: str,
) -> dict[str, object]:
    if not products_by_url:
        return {'partial_checkpoint_found': 0, 'partial_checkpoint_enabled': True}
    rows: list[dict[str, object]] = []
    for _url, product in products_by_url:
        try:
            rows.append(to_contract_row(product, contract))
        except Exception:
            continue
    if not rows:
        return {'partial_checkpoint_found': 0, 'partial_checkpoint_enabled': True}
    return {
        'partial_checkpoint_enabled': True,
        'partial_checkpoint_rows': rows,
        'partial_checkpoint_columns': columns,
        'partial_checkpoint_operation': normalized_operation,
        'partial_checkpoint_found': len(rows),
    }


def _read_products_parallel(
    *,
    urls: list[str],
    needed: set[str],
    important: set[str],
    max_products: int,
    stop_early: bool,
    progress_callback: Callable[[dict], None] | None,
    contract,
    columns: list[str],
    normalized_operation: str,
    budget_seconds: int | float = PRODUCT_READ_BUDGET_SECONDS,
) -> tuple[list[tuple[str, FastProductData]], int, int, int, str, list[dict[str, object]]]:
    products_by_url: list[tuple[str, FastProductData]] = []
    errors = 0
    complete_count = 0
    last_gain_at = 0
    stop_reason = ''
    slow_links: list[dict[str, object]] = []
    started = time.perf_counter()
    workers = max(1, min(MAX_WORKERS, len(urls)))
    total = min(len(urls), max_products)
    processed = 0
    last_emit = time.perf_counter()
    pending_urls = urls[:max_products]

    emit(progress_callback, {
        'stage': 'Lendo produtos em lote seguro',
        'message': f'Lendo até {total} produto(s), com orçamento de {int(budget_seconds)}s para não derrubar o app.',
        'progress': 0.28,
        'processed': 0,
        'total': total,
        'workers': workers,
        'stop_early': bool(stop_early),
        'rich_description_enabled': 'descricao_complementar' in needed,
        'dynamic_render_fallback_enabled': True,
        'budget_seconds': int(budget_seconds),
        'partial_checkpoint_enabled': True,
    })

    while pending_urls and processed < total:
        if _seconds_left(started, budget_seconds) <= 2:
            stop_reason = 'Leitura pausada por limite de tempo técnico. Resultado parcial preservado.'
            break

        batch_size = min(max(workers * 2, 8), len(pending_urls), total - processed)
        batch = pending_urls[:batch_size]
        pending_urls = pending_urls[batch_size:]
        executor = ThreadPoolExecutor(max_workers=workers)
        futures = {executor.submit(scrape_one, url, needed): url for url in batch}
        unfinished = set(futures.keys())
        batch_idle_started = time.perf_counter()

        try:
            while unfinished:
                left = _seconds_left(started, budget_seconds)
                if left <= 1:
                    stop_reason = 'Leitura pausada por limite de tempo técnico. Resultado parcial preservado.'
                    break

                done, unfinished = wait(unfinished, timeout=min(1.0, max(0.1, left)), return_when=FIRST_COMPLETED)
                if not done:
                    if time.perf_counter() - batch_idle_started >= 10:
                        stop_reason = 'Leitura pausada por link lento. Resultado parcial preservado.'
                        break
                    continue

                batch_idle_started = time.perf_counter()
                for future in done:
                    processed += 1
                    product = FastProductData(url=futures.get(future, ''))
                    try:
                        url, product, elapsed, failed = future.result(timeout=0)
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
                            pending_urls = []
                            payload = {
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
                            }
                            payload.update(_partial_checkpoint_payload(products_by_url=products_by_url, contract=contract, columns=columns, normalized_operation=normalized_operation))
                            emit(progress_callback, payload)
                            break

                    now = time.perf_counter()
                    if now - last_emit >= 0.5 or processed == total:
                        ratio = processed / max(total, 1)
                        payload = {
                            'stage': 'Lendo produtos em lote seguro',
                            'message': f'{processed}/{total} produto(s) lido(s). {len(products_by_url)} com dados úteis.',
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
                            'seconds_left': round(_seconds_left(started, budget_seconds), 1),
                        }
                        payload.update(_partial_checkpoint_payload(products_by_url=products_by_url, contract=contract, columns=columns, normalized_operation=normalized_operation))
                        emit(progress_callback, payload)
                        last_emit = now

                if stop_reason:
                    break
        finally:
            if unfinished:
                for future in unfinished:
                    future.cancel()
                errors += len(unfinished)
                add_audit_event(
                    'site_scraper_slow_futures_cancelled',
                    area='SITE',
                    step='entrada',
                    status='AVISO',
                    details={
                        'cancelled': len(unfinished),
                        'processed': processed,
                        'found': len(products_by_url),
                        'reason': stop_reason or 'lote_sem_resposta',
                        'partial_checkpoint_found': len(products_by_url),
                        'responsible_file': RESPONSIBLE_FILE,
                    },
                )
            executor.shutdown(wait=False, cancel_futures=True)

        if stop_reason:
            break

    if products_by_url:
        payload = {
            'stage': 'Checkpoint preservado',
            'message': f'{len(products_by_url)} produto(s) já preservado(s). Se a tela cair, será possível continuar com este resultado parcial.',
            'progress': 0.86,
            'processed': processed,
            'total': total,
            'found': len(products_by_url),
            'complete': complete_count,
            'errors': errors,
        }
        payload.update(_partial_checkpoint_payload(products_by_url=products_by_url, contract=contract, columns=columns, normalized_operation=normalized_operation))
        emit(progress_callback, payload)

    if stop_reason and ('limite de tempo' in stop_reason or 'link lento' in stop_reason):
        add_audit_event(
            'site_scraper_read_budget_reached',
            area='SITE',
            step='entrada',
            status='AVISO',
            details={
                'processed': processed,
                'total': total,
                'found': len(products_by_url),
                'errors': errors,
                'budget_seconds': int(budget_seconds),
                'stop_reason': stop_reason,
                'partial_checkpoint_found': len(products_by_url),
                'responsible_file': RESPONSIBLE_FILE,
            },
        )

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
            'partial_checkpoint_enabled': True,
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


def _wbuy_listing_fallback_products(
    *,
    raw_urls: str,
    max_products: int,
    progress_callback: Callable[[dict], None] | None,
    allow_catalog_fallback: bool = True,
) -> list[FastProductData]:
    starts = _wbuy_candidate_pages(raw_urls, max_products)
    if not starts:
        return []

    emit(progress_callback, {
        'stage': 'Fallback wBuy',
        'message': 'Tentando complementar a captura com vitrines, buscas e cards públicos wBuy.',
        'progress': 0.88,
        'starts': len(starts),
    })
    fetched = fetch_many_live(starts, timeout=9, workers=min(12, len(starts)))
    products: list[FastProductData] = []
    seen: set[str] = set()
    for url, html in fetched.items():
        remaining = max(0, int(max_products) - len(products))
        if remaining <= 0:
            break
        for product in wbuy_listing_products(url, html, limit=remaining):
            key = _product_identity(product)
            if not key or key in seen:
                continue
            seen.add(key)
            products.append(product)
            if len(products) >= max_products:
                break

    if not products and starts and allow_catalog_fallback:
        emit(progress_callback, {
            'stage': 'Fallback OpenAI catálogo',
            'message': 'Tentando localizar produtos públicos do domínio porque o HTML wBuy não trouxe cards úteis.',
            'progress': 0.895,
            'starts': len(starts),
        })
        openai_limit = max(1, min(int(max_products or 40), 80))
        products = openai_catalog_products(starts[0], limit=openai_limit)

    add_audit_event(
        'site_scraper_wbuy_listing_fallback',
        area='SITE',
        step='entrada',
        status='OK' if products else 'INFO',
        details={
            'starts': len(starts),
            'html_pages': sum(1 for raw in fetched.values() if raw),
            'products': len(products),
            'catalog_fallback_allowed': bool(allow_catalog_fallback),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    if products:
        emit(progress_callback, {
            'stage': 'Fallback wBuy aplicado',
            'message': f'{len(products)} produto(s) recuperado(s) por fallback wBuy/catálogo.',
            'progress': 0.90,
            'found': len(products),
        })
    return products


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
            'partial_checkpoint_enabled': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )

    emit(progress_callback, {
        'stage': 'Procurando links em lote seguro',
        'message': f'Procurando produtos com limite técnico de {max_pages} página(s) e {max_products} produto(s).',
        'progress': 0.08,
        'columns': len(columns),
        'max_pages': max_pages,
        'max_products': max_products,
        'safe_limited': safe_limited,
        'flow_mode': flow_mode,
        'partial_checkpoint_enabled': True,
    })
    discovery_started = time.perf_counter()
    urls = discover_product_urls(raw_urls, max_pages=max_pages, max_products=max_products)
    discovery_seconds = time.perf_counter() - discovery_started

    if len(urls) > max_products:
        urls = urls[:max_products]

    emit(progress_callback, {
        'stage': 'Links encontrados',
        'message': f'{len(urls)} link(s) de produto separado(s) para leitura.',
        'progress': 0.22,
        'urls_found': len(urls),
        'discovery_seconds': round(discovery_seconds, 2),
        'max_products': max_products,
        'safe_limited': safe_limited,
        'flow_mode': flow_mode,
        'partial_checkpoint_enabled': True,
    })
    if not urls:
        fallback_products = _wbuy_listing_fallback_products(
            raw_urls=raw_urls,
            max_products=max_products,
            progress_callback=progress_callback,
            allow_catalog_fallback=True,
        )
        if fallback_products:
            rows = [to_contract_row(product, contract) for product in fallback_products]
            emit(progress_callback, {
                'stage': 'Montando origem',
                'message': f'Montando origem com {len(rows)} produto(s) recuperado(s) dos cards wBuy.',
                'progress': 0.91,
                'found': len(rows),
                'urls_found': 0,
                'total_seconds': round(time.perf_counter() - total_started, 2),
                'partial_checkpoint_enabled': True,
                'partial_checkpoint_rows': rows,
                'partial_checkpoint_columns': columns,
                'partial_checkpoint_operation': normalized_operation,
                'partial_checkpoint_found': len(rows),
            })
            _audit_finished(
                normalized_operation=normalized_operation,
                products=fallback_products,
                rendered_fallbacks=0,
                errors=0,
                needed=needed,
            )
            return ensure_columns(pd.DataFrame(rows).fillna(''), columns)
        emit(progress_callback, {'stage': 'Nada encontrado', 'message': 'Não encontrei produtos nos links informados. Confira se o link abre produtos ou categorias.', 'progress': 1.0, 'urls_found': 0})
        return pd.DataFrame(columns=columns)

    if needed <= {'url'}:
        rows = [to_contract_row(url_only_row(url), contract) for url in urls[:max_products]]
        emit(progress_callback, {
            'stage': 'Pronto',
            'message': f'{len(rows)} link(s) preparado(s) para a origem.',
            'progress': 0.92,
            'processed': len(rows),
            'urls_found': len(urls),
            'total_seconds': round(time.perf_counter() - total_started, 2),
            'safe_limited': safe_limited,
            'flow_mode': flow_mode,
            'partial_checkpoint_enabled': True,
            'partial_checkpoint_rows': rows,
            'partial_checkpoint_columns': columns,
            'partial_checkpoint_operation': normalized_operation,
            'partial_checkpoint_found': len(rows),
        })
        return ensure_columns(pd.DataFrame(rows).fillna(''), columns)

    remaining_budget = max(12, min(PRODUCT_READ_BUDGET_SECONDS, STREAMLIT_HARD_BUDGET_SECONDS - int(time.perf_counter() - total_started) - 8))
    products_by_url, processed, errors, complete_count, stop_reason, slow_links = _read_products_parallel(
        urls=urls,
        needed=needed,
        important=important,
        max_products=max_products,
        stop_early=stop_early,
        progress_callback=progress_callback,
        contract=contract,
        columns=columns,
        normalized_operation=normalized_operation,
        budget_seconds=remaining_budget,
    )

    products, rendered_fallbacks = enhance_products_sequentially(products_by_url, needed, progress_callback)
    fallback_products: list[FastProductData] = []
    min_target = min(WBUY_FALLBACK_MIN_PRODUCTS, max(1, int(max_products or WBUY_FALLBACK_MIN_PRODUCTS)))
    if len(products) < min_target:
        fallback_products = _wbuy_listing_fallback_products(
            raw_urls=raw_urls,
            max_products=max_products,
            progress_callback=progress_callback,
            allow_catalog_fallback=False,
        )
        if fallback_products:
            before = len(products)
            products = _merge_products_by_identity(products, fallback_products, max_products=max_products)
            added = len(products) - before
            if added:
                add_audit_event(
                    'site_scraper_wbuy_listing_fallback_merged',
                    area='SITE',
                    step='entrada',
                    status='OK',
                    details={
                        'before': before,
                        'fallback_products': len(fallback_products),
                        'added': added,
                        'after': len(products),
                        'min_target': min_target,
                        'responsible_file': RESPONSIBLE_FILE,
                    },
                )
                emit(progress_callback, {
                    'stage': 'Fallback wBuy complementou',
                    'message': f'Capturei mais {added} produto(s) por vitrines/cards wBuy.',
                    'progress': 0.905,
                    'found': len(products),
                    'added': added,
                })
    if not products:
        products = fallback_products or _wbuy_listing_fallback_products(
            raw_urls=raw_urls,
            max_products=max_products,
            progress_callback=progress_callback,
            allow_catalog_fallback=True,
        )
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
        'stop_reason': stop_reason,
        'partial_checkpoint_enabled': True,
        'partial_checkpoint_rows': rows,
        'partial_checkpoint_columns': columns,
        'partial_checkpoint_operation': normalized_operation,
        'partial_checkpoint_found': len(rows),
    })
    return ensure_columns(pd.DataFrame(rows).fillna(''), columns)


__all__ = ['run_fast_site_scraper']