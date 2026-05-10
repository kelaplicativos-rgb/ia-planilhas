from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from bling_app_zero.core.text import clean_cell, normalize_key

BLOCKED_RESOURCE_TYPES = {'image', 'media', 'font'}
BLOCKED_URL_TERMS = [
    'google-analytics', 'googletagmanager', 'facebook.com/tr', 'doubleclick', 'hotjar',
    'clarity.ms', 'tiktok', 'pinterest', 'adsystem', 'adservice', 'whatsapp',
]
PRODUCT_RESPONSE_TERMS = [
    'produto', 'product', 'sku', 'preco', 'price', 'description', 'descricao', 'estoque', 'stock',
]


@dataclass
class RenderedProductPage:
    url: str
    html: str = ''
    text: str = ''
    network_payloads: list[str] = field(default_factory=list)
    error: str = ''

    @property
    def ok(self) -> bool:
        return bool(self.html or self.text or self.network_payloads)


def _json_text(value: Any, limit: int = 12000) -> str:
    try:
        return json.dumps(value, ensure_ascii=False)[:limit]
    except Exception:
        return clean_cell(value)[:limit]


def _looks_like_product_payload(url: str, body: str) -> bool:
    key = normalize_key(f'{url} {body[:4000]}')
    if not key:
        return False
    return any(normalize_key(term) in key for term in PRODUCT_RESPONSE_TERMS)


def _safe_import_playwright():
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
        return sync_playwright, ''
    except Exception as exc:
        return None, str(exc)


def fetch_rendered_product_page(url: str, timeout_ms: int = 18000) -> RenderedProductPage:
    """Busca página renderizada com navegador real, inspirado no Chrome DevTools.

    Captura:
    - DOM final depois do JavaScript;
    - texto visível renderizado;
    - respostas JSON/text relevantes da aba Network.

    É opcional e defensivo: se Playwright/Chromium não estiver disponível,
    retorna erro controlado para o scraper HTTP continuar funcionando.
    """
    sync_playwright, import_error = _safe_import_playwright()
    if sync_playwright is None:
        return RenderedProductPage(url=url, error=f'Playwright indisponível: {import_error}')

    network_payloads: list[str] = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-gpu',
                    '--disable-extensions',
                    '--disable-background-networking',
                ],
            )
            context = browser.new_context(
                viewport={'width': 1366, 'height': 2200},
                user_agent=(
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/122.0.0.0 Safari/537.36'
                ),
                locale='pt-BR',
            )
            page = context.new_page()

            def should_block(route):
                request = route.request
                req_url = request.url.lower()
                if request.resource_type in BLOCKED_RESOURCE_TYPES:
                    return route.abort()
                if any(term in req_url for term in BLOCKED_URL_TERMS):
                    return route.abort()
                return route.continue_()

            def on_response(response):
                try:
                    content_type = response.headers.get('content-type', '')
                    resp_url = response.url
                    if not re.search(r'json|javascript|text|html', content_type, flags=re.I):
                        return
                    body = response.text()
                    if body and _looks_like_product_payload(resp_url, body):
                        network_payloads.append(_json_text({'url': resp_url, 'body': body}, limit=12000))
                except Exception:
                    return

            page.route('**/*', should_block)
            page.on('response', on_response)
            page.goto(url, wait_until='domcontentloaded', timeout=timeout_ms)
            try:
                page.wait_for_load_state('networkidle', timeout=6000)
            except Exception:
                pass
            try:
                page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                page.wait_for_timeout(900)
                page.evaluate('window.scrollTo(0, 0)')
            except Exception:
                pass

            html = page.content()
            try:
                text = page.locator('body').inner_text(timeout=3000)
            except Exception:
                text = ''

            context.close()
            browser.close()
            return RenderedProductPage(
                url=url,
                html=html or '',
                text=clean_cell(text),
                network_payloads=network_payloads[:20],
            )
    except Exception as exc:
        return RenderedProductPage(url=url, error=str(exc))
