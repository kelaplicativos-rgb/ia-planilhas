from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.engines.fast_site_scraper.constants import (
    DEEP_CAPTURE_MAX_DEPTH,
    DEEP_CAPTURE_MAX_PAGES,
    DEEP_CAPTURE_MAX_PRODUCTS,
    DISCOVERY_BUDGET_SECONDS,
    FLOW_CAPTURE_MAX_DEPTH,
    FLOW_CAPTURE_MAX_PAGES,
    FLOW_CAPTURE_MAX_PRODUCTS,
)
from bling_app_zero.engines.fast_site_scraper.http_client import fetch_live
from bling_app_zero.engines.fast_site_scraper.url_discovery import (
    allowed_url,
    discover_from_feeds,
    norm_url,
    productish_url,
    same_domain,
    split_urls,
)

RESPONSIBLE_FILE = 'bling_app_zero/engines/fast_site_scraper/deep_site_capture.py'
DEFAULT_MAX_PAGES = DEEP_CAPTURE_MAX_PAGES
DEFAULT_MAX_PRODUCTS = DEEP_CAPTURE_MAX_PRODUCTS
DEFAULT_MAX_DEPTH = DEEP_CAPTURE_MAX_DEPTH


@dataclass(frozen=True)
class DeepCaptureResult:
    product_urls: list[str]
    visited_pages: int
    scanned_pages: int
    ignored_external_links: int
    max_depth: int
    stopped_by_budget: bool = False
    stop_reason: str = ''

    @property
    def raw_urls(self) -> str:
        return '\n'.join(self.product_urls)


def _emit(progress_callback: Callable[[dict], None] | None, payload: dict) -> None:
    if not progress_callback:
        return
    try:
        progress_callback(payload)
    except Exception:
        pass


def _links_from_html(url: str, html: str) -> tuple[list[str], int]:
    soup = BeautifulSoup(html or '', 'html.parser')
    links: list[str] = []
    external_or_blocked = 0
    for node in soup.find_all('a', href=True):
        href = norm_url(urljoin(url, str(node.get('href') or '')))
        if not href:
            continue
        if allowed_url(href, url):
            if href not in links:
                links.append(href)
        else:
            external_or_blocked += 1
    return sorted(links, key=lambda item: 0 if productish_url(item) else 1), external_or_blocked


def _clamp_int(value: int | None, fallback: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value or fallback)
    except Exception:
        number = fallback
    return max(minimum, min(maximum, number))


def _technical_max_pages(max_pages: int | None) -> int:
    try:
        requested = int(max_pages or DEFAULT_MAX_PAGES)
    except Exception:
        requested = DEFAULT_MAX_PAGES
    if requested > DEEP_CAPTURE_MAX_PAGES:
        return FLOW_CAPTURE_MAX_PAGES
    return DEEP_CAPTURE_MAX_PAGES


def _technical_max_products(max_products: int | None) -> int:
    try:
        requested = int(max_products or DEFAULT_MAX_PRODUCTS)
    except Exception:
        requested = DEFAULT_MAX_PRODUCTS
    if requested > DEEP_CAPTURE_MAX_PRODUCTS:
        return FLOW_CAPTURE_MAX_PRODUCTS
    return DEEP_CAPTURE_MAX_PRODUCTS


def _technical_max_depth(max_depth: int | None) -> int:
    try:
        requested = int(max_depth or DEFAULT_MAX_DEPTH)
    except Exception:
        requested = DEFAULT_MAX_DEPTH
    if requested > DEEP_CAPTURE_MAX_DEPTH:
        return FLOW_CAPTURE_MAX_DEPTH
    return DEEP_CAPTURE_MAX_DEPTH


def _time_left(started: float, budget_seconds: float) -> float:
    return max(0.0, float(budget_seconds) - (time.perf_counter() - started))


def _all_starts_are_product_pages(starts: list[str]) -> bool:
    return bool(starts) and all(productish_url(url) for url in starts)


def discover_deep_product_urls(
    raw_urls: str,
    *,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_products: int = DEFAULT_MAX_PRODUCTS,
    max_depth: int = DEFAULT_MAX_DEPTH,
    progress_callback: Callable[[dict], None] | None = None,
    budget_seconds: int | float = DISCOVERY_BUDGET_SECONDS,
) -> DeepCaptureResult:
    """Expande um domínio/categoria em links prováveis de produto sem travar o app.

    BLINGFIX: se todos os links informados já forem páginas de produto, a busca
    profunda não deve abrir o site inteiro. Nesse caso, preserva exatamente os
    links informados e devolve varredura zerada.
    """
    started = time.perf_counter()
    starts = [norm_url(url) for url in split_urls(raw_urls) if norm_url(url)]
    starts = list(dict.fromkeys(starts))
    if not starts:
        return DeepCaptureResult([], 0, 0, 0, max_depth=0)

    if _all_starts_are_product_pages(starts):
        limited = starts[: max(1, int(max_products or len(starts)))]
        _emit(progress_callback, {
            'stage': 'Links diretos de produto',
            'message': f'{len(limited)} link(s) direto(s) de produto recebido(s). Varredura profunda bloqueada para não abrir o site inteiro.',
            'progress': 0.88,
            'visited_pages': 0,
            'found_products': len(limited),
            'max_pages': 0,
            'max_products': len(limited),
            'max_depth': 0,
            'safe_limited': True,
            'flow_mode': 'product_detail_urls_only',
            'stopped_by_budget': False,
            'stop_reason': 'Entrada já era página de produto; deep crawler não executado.',
        })
        add_audit_event(
            'site_deep_capture_product_url_scope_locked',
            area='SITE',
            step='entrada',
            status='OK',
            details={
                'input_urls': len(starts),
                'product_urls': len(limited),
                'scan_mode': 'product_detail_urls_only',
                'reason': 'URL direta de produto não deve virar varredura de site inteiro.',
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return DeepCaptureResult(
            product_urls=limited,
            visited_pages=0,
            scanned_pages=0,
            ignored_external_links=0,
            max_depth=0,
            stopped_by_budget=False,
            stop_reason='Entrada já era página de produto; deep crawler não executado.',
        )

    technical_pages = _technical_max_pages(max_pages)
    technical_products = _technical_max_products(max_products)
    technical_depth = _technical_max_depth(max_depth)
    max_pages = _clamp_int(max_pages, DEFAULT_MAX_PAGES, 1, technical_pages)
    max_products = _clamp_int(max_products, DEFAULT_MAX_PRODUCTS, 1, technical_products)
    max_depth = _clamp_int(max_depth, DEFAULT_MAX_DEPTH, 0, technical_depth)
    flow_mode = max_pages > DEEP_CAPTURE_MAX_PAGES or max_products > DEEP_CAPTURE_MAX_PRODUCTS or max_depth > DEEP_CAPTURE_MAX_DEPTH
    budget_seconds = max(8.0, float(budget_seconds or DISCOVERY_BUDGET_SECONDS))

    _emit(progress_callback, {
        'stage': 'Captura profunda controlada',
        'message': f'Expandindo site com limite seguro de {max_pages} página(s), {max_products} produto(s), profundidade {max_depth} e orçamento de {int(budget_seconds)}s.',
        'progress': 0.10,
        'max_pages': max_pages,
        'max_products': max_products,
        'max_depth': max_depth,
        'safe_limited': True,
        'flow_mode': flow_mode,
        'budget_seconds': int(budget_seconds),
    })

    queue: deque[tuple[str, int]] = deque((url, 0) for url in starts)
    queued = set(starts)
    visited: set[str] = set()
    products: list[str] = []
    ignored_external = 0
    scanned_pages = 0
    stopped_by_budget = False
    stop_reason = ''

    while queue and len(visited) < max_pages and len(products) < max_products:
        if _time_left(started, budget_seconds) <= 1.5:
            stopped_by_budget = True
            stop_reason = 'Busca pausada por limite de tempo técnico. Resultado parcial preservado.'
            break

        url, depth = queue.popleft()
        if url in visited:
            continue
        visited.add(url)

        if productish_url(url) and url not in products:
            products.append(url)
            if len(products) >= max_products:
                break

        if depth > max_depth:
            continue

        fetch_timeout = min(4.0, max(1.5, _time_left(started, budget_seconds)))
        html = fetch_live(url, timeout=fetch_timeout)
        scanned_pages += 1
        if not html:
            continue

        links, ignored = _links_from_html(url, html)
        ignored_external += ignored
        for link in links:
            if len(products) >= max_products:
                break
            if not any(same_domain(link, start) for start in starts):
                ignored_external += 1
                continue
            if productish_url(link) and link not in products:
                products.append(link)
                continue
            if depth < max_depth and link not in visited and link not in queued and len(visited) + len(queue) < max_pages:
                queued.add(link)
                queue.append((link, depth + 1))

        if scanned_pages % 8 == 0 or len(products) >= max_products:
            ratio = min(0.82, 0.12 + (0.70 * (len(visited) / max(max_pages, 1))))
            _emit(progress_callback, {
                'stage': 'Captura profunda controlada',
                'message': f'{len(visited)} página(s) varrida(s), {len(products)} produto(s) provável(is) encontrado(s).',
                'progress': ratio,
                'visited_pages': len(visited),
                'found_products': len(products),
                'queued_pages': len(queue),
                'safe_limited': True,
                'flow_mode': flow_mode,
                'seconds_left': round(_time_left(started, budget_seconds), 1),
            })

    if len(products) < max_products and _time_left(started, budget_seconds) > 5:
        feed_budget = min(max_products - len(products), 250)
        try:
            feed_urls = discover_from_feeds(starts, max_products=feed_budget)
        except Exception:
            feed_urls = []
        for link in feed_urls:
            if link not in products:
                products.append(link)
                if len(products) >= max_products:
                    break

    if stopped_by_budget:
        add_audit_event(
            'site_deep_capture_budget_reached',
            area='SITE',
            step='entrada',
            status='AVISO',
            details={
                'visited_pages': len(visited),
                'scanned_pages': scanned_pages,
                'found_products': len(products),
                'max_pages': max_pages,
                'max_products': max_products,
                'budget_seconds': int(budget_seconds),
                'stop_reason': stop_reason,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )

    _emit(progress_callback, {
        'stage': 'Captura profunda pronta',
        'message': f'{len(products)} link(s) de produto preparado(s). {stop_reason}'.strip(),
        'progress': 0.88,
        'visited_pages': len(visited),
        'found_products': len(products),
        'max_pages': max_pages,
        'max_products': max_products,
        'max_depth': max_depth,
        'safe_limited': True,
        'flow_mode': flow_mode,
        'stopped_by_budget': stopped_by_budget,
        'stop_reason': stop_reason,
    })

    return DeepCaptureResult(
        product_urls=products[:max_products],
        visited_pages=len(visited),
        scanned_pages=scanned_pages,
        ignored_external_links=ignored_external,
        max_depth=max_depth,
        stopped_by_budget=stopped_by_budget,
        stop_reason=stop_reason,
    )


__all__ = ['DeepCaptureResult', 'discover_deep_product_urls']
