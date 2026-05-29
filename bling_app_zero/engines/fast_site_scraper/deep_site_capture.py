from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from bling_app_zero.engines.fast_site_scraper.constants import (
    DEEP_CAPTURE_MAX_DEPTH,
    DEEP_CAPTURE_MAX_PAGES,
    DEEP_CAPTURE_MAX_PRODUCTS,
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


def discover_deep_product_urls(
    raw_urls: str,
    *,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_products: int = DEFAULT_MAX_PRODUCTS,
    max_depth: int = DEFAULT_MAX_DEPTH,
    progress_callback: Callable[[dict], None] | None = None,
) -> DeepCaptureResult:
    """Expande um domínio/categoria em links prováveis de produto com limite duro.

    BLINGFIX: antes a descoberta profunda podia aceitar até 5000 páginas e
    10000 produtos, pesado demais para execução síncrona no Streamlit Cloud.
    Agora ela respeita os mesmos tetos centrais usados pelo fluxo de captura.
    """
    starts = [norm_url(url) for url in split_urls(raw_urls) if norm_url(url)]
    starts = list(dict.fromkeys(starts))
    if not starts:
        return DeepCaptureResult([], 0, 0, 0, max_depth=0)

    max_pages = _clamp_int(max_pages, DEFAULT_MAX_PAGES, 1, DEEP_CAPTURE_MAX_PAGES)
    max_products = _clamp_int(max_products, DEFAULT_MAX_PRODUCTS, 1, DEEP_CAPTURE_MAX_PRODUCTS)
    max_depth = _clamp_int(max_depth, DEFAULT_MAX_DEPTH, 0, DEEP_CAPTURE_MAX_DEPTH)

    _emit(progress_callback, {
        'stage': 'Captura profunda controlada',
        'message': f'Expandindo site do fornecedor com limite de {max_pages} página(s), {max_products} produto(s) e profundidade {max_depth}.',
        'progress': 0.10,
        'max_pages': max_pages,
        'max_products': max_products,
        'max_depth': max_depth,
        'safe_limited': True,
    })

    queue: deque[tuple[str, int]] = deque((url, 0) for url in starts)
    queued = set(starts)
    visited: set[str] = set()
    products: list[str] = []
    ignored_external = 0
    scanned_pages = 0

    while queue and len(visited) < max_pages and len(products) < max_products:
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

        html = fetch_live(url, timeout=6)
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

        if scanned_pages % 10 == 0 or len(products) >= max_products:
            ratio = min(0.82, 0.12 + (0.70 * (len(visited) / max(max_pages, 1))))
            _emit(progress_callback, {
                'stage': 'Captura profunda controlada',
                'message': f'{len(visited)} página(s) varrida(s), {len(products)} produto(s) provável(is) encontrado(s).',
                'progress': ratio,
                'visited_pages': len(visited),
                'found_products': len(products),
                'queued_pages': len(queue),
                'safe_limited': True,
            })

    if len(products) < max_products:
        feed_budget = max_products - len(products)
        try:
            feed_urls = discover_from_feeds(starts, max_products=feed_budget)
        except Exception:
            feed_urls = []
        for link in feed_urls:
            if link not in products:
                products.append(link)
                if len(products) >= max_products:
                    break

    _emit(progress_callback, {
        'stage': 'Captura profunda pronta',
        'message': f'{len(products)} link(s) de produto preparado(s) para o motor existente.',
        'progress': 0.88,
        'visited_pages': len(visited),
        'found_products': len(products),
        'max_pages': max_pages,
        'max_products': max_products,
        'max_depth': max_depth,
        'safe_limited': True,
    })

    return DeepCaptureResult(
        product_urls=products[:max_products],
        visited_pages=len(visited),
        scanned_pages=scanned_pages,
        ignored_external_links=ignored_external,
        max_depth=max_depth,
    )


__all__ = ['DeepCaptureResult', 'discover_deep_product_urls']
