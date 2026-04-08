from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from bling_app_zero.core.fetcher import fetch_url

try:
    from bling_app_zero.utils.excel_logs import log_debug
except Exception:
    def log_debug(*args, **kwargs): pass

try:
    from bling_app_zero.core.playwright_fetcher import (
        fetch_playwright_payload,
        storage_state_path_por_dominio,
        tentar_fetch_com_fallback_js,
    )
except Exception:
    fetch_playwright_payload = None
    storage_state_path_por_dominio = None
    tentar_fetch_com_fallback_js = None


HTML_MINIMO_UTIL = 3000  # 🔥 aumentei (antes 1200)

DOMINIOS_PRIORIDADE_JS = {
    "atacadum.com.br",
    "megacentereletronicos.com.br",  # 🔥 FORÇA JS
}


def _safe_str(valor: Any) -> str:
    try:
        return str(valor or "").strip()
    except:
        return ""


def _normalizar_url(url: str) -> str:
    url = _safe_str(url)
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url


def _dominio(url: str) -> str:
    try:
        return urlparse(_normalizar_url(url)).netloc.lower().replace("www.", "")
    except:
        return ""


def _parece_html_fraco(html: str | None) -> bool:
    html = _safe_str(html)

    if not html:
        return True

    html_baixo = html.lower()

    if len(html) < HTML_MINIMO_UTIL:
        return True

    # 🔥 NOVO: detecta páginas vazias de produto
    sinais_ruins = [
        "access denied",
        "captcha",
        "cloudflare",
        "verify you are human",
        "carregando",
        "loading",
    ]

    if any(s in html_baixo for s in sinais_ruins):
        return True

    # 🔥 NOVO: não tem sinais de produto
    sinais_produto = [
        "price",
        "preco",
        "product",
        "produto",
        "add to cart",
        "comprar",
    ]

    if not any(s in html_baixo for s in sinais_produto):
        return True

    return False


def _storage_state(url: str) -> str | None:
    if storage_state_path_por_dominio is None:
        return None
    try:
        return storage_state_path_por_dominio(_normalizar_url(url))
    except:
        return None


def _payload_requests(url: str, html: str | None) -> dict:
    return {
        "ok": bool(html),
        "engine": "requests",
        "url": url,
        "final_url": url,
        "html": html,
        "network_records": [],
        "error": "" if html else "Falha requests",
    }


# ==========================================================
# MAIN
# ==========================================================
def fetch_payload_router(
    url: str,
    preferir_js: bool = False,
    wait_selector: str | None = None,
) -> dict:

    url = _normalizar_url(url)
    dominio = _dominio(url)

    log_debug(f"[FETCH_ROUTER] START | {url}")

    # 🔥 FORÇA JS PARA DOMÍNIOS
    if dominio in DOMINIOS_PRIORIDADE_JS:
        preferir_js = True

    # ======================================================
    # 1) JS DIRETO
    # ======================================================
    if preferir_js and fetch_playwright_payload:
        log_debug("[FETCH_ROUTER] FORÇANDO JS")

        payload = fetch_playwright_payload(url)

        if payload.get("ok"):
            return payload

    # ======================================================
    # 2) REQUESTS
    # ======================================================
    html = fetch_url(url)

    if html and not _parece_html_fraco(html):
        log_debug("[FETCH_ROUTER] HTML OK (requests)")
        return _payload_requests(url, html)

    # ======================================================
    # 3) FALLBACK JS
    # ======================================================
    if tentar_fetch_com_fallback_js:
        log_debug("[FETCH_ROUTER] FALLBACK JS")

        payload = tentar_fetch_com_fallback_js(
            url=url,
            html_requests=html,
        )

        if payload.get("ok"):
            return payload

    log_debug("[FETCH_ROUTER] FALHA TOTAL")

    return _payload_requests(url, html)
