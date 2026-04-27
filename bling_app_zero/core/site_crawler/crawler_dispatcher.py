from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import urlparse

from .crawler_utils import log

try:
    from bling_app_zero.core.playwright_fetcher import fetch_playwright_payload
except Exception:
    fetch_playwright_payload = None


JS_DOMAINS = {
    "megacentereletronicos.com.br",
    "www.megacentereletronicos.com.br",
    "stoqui.shop",
    "www.stoqui.shop",
}

MIN_HTML_UTIL = 1200


def _safe_str(valor: Any) -> str:
    try:
        return str(valor or "").strip()
    except Exception:
        return ""


def normalizar_url(url: Any) -> str:
    texto = _safe_str(url)
    if not texto:
        return ""
    if texto.startswith("//"):
        texto = "https:" + texto
    if not texto.startswith(("http://", "https://")):
        texto = "https://" + texto
    return texto


def dominio(url: str) -> str:
    try:
        return urlparse(normalizar_url(url)).netloc.lower()
    except Exception:
        return ""


def precisa_playwright(url: str) -> bool:
    host = dominio(url)
    return host in JS_DOMAINS or "megacenter" in host or "stoqui" in host


def html_fraco(html: str) -> bool:
    texto = (html or "").lower()

    if len(texto) < MIN_HTML_UTIL:
        return True

    sinais = [
        "produto",
        "product",
        "preço",
        "preco",
        "price",
        "sku",
        "gtin",
        "ean",
        "comprar",
        "addtocart",
        "application/ld+json",
    ]

    return not any(s in texto for s in sinais)


def fetch_http(session, url: str) -> str:
    try:
        resp = session.get(url, timeout=25, verify=False)
        return resp.text or ""
    except Exception as exc:
        log(f"[DISPATCHER HTTP] falha → {url} → {exc}")
        return ""


def fetch_js(url: str, auth_context: Optional[Dict] = None) -> str:
    if fetch_playwright_payload is None:
        log("[DISPATCHER JS] Playwright não encontrado no projeto.")
        return ""

    try:
        payload = fetch_playwright_payload(
            url=url,
            auth_config=auth_context or {},
            headless=True,
            screenshot_on_error=False,
        )

        html = payload.get("html") or ""
        ok = bool(payload.get("ok"))
        status = payload.get("status") or ""
        erro = payload.get("error") or ""

        log(
            "[DISPATCHER JS] retorno "
            f"| ok={ok} "
            f"| status={status} "
            f"| html_len={len(html)} "
            f"| erro={erro}"
        )

        return html
    except Exception as exc:
        log(f"[DISPATCHER JS] erro → {url} → {exc}")
        return ""


def fetch_html(
    session,
    url: str,
    *,
    auth_context: Optional[Dict] = None,
    preferir_playwright: Optional[bool] = None,
) -> str:
    url = normalizar_url(url)
    if not url:
        return ""

    usar_js_primeiro = precisa_playwright(url) if preferir_playwright is None else bool(preferir_playwright)

    if usar_js_primeiro:
        log(f"[DISPATCHER] JS primeiro → {url}")
        html_js = fetch_js(url, auth_context=auth_context)

        if html_js and not html_fraco(html_js):
            return html_js

        log("[DISPATCHER] JS fraco/indisponível; tentando HTTP fallback.")
        html_http = fetch_http(session, url)
        return html_http or html_js

    log(f"[DISPATCHER] HTTP primeiro → {url}")
    html_http = fetch_http(session, url)

    if html_fraco(html_http):
        log(f"[DISPATCHER] HTTP fraco; acionando JS fallback → {url}")
        html_js = fetch_js(url, auth_context=auth_context)
        return html_js or html_http

    return html_http
