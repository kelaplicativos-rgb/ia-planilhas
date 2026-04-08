from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from bling_app_zero.core.fetcher import fetch_url

# ==========================================================
# LOG (BLINDADO)
# ==========================================================
try:
    from bling_app_zero.utils.excel_logs import log_debug  # type: ignore
except Exception:
    try:
        from bling_app_zero.utils.excel import log_debug  # type: ignore
    except Exception:
        def log_debug(_msg: str, _nivel: str = "INFO") -> None:
            return None


# ==========================================================
# IMPORT PLAYWRIGHT (BLINDADO)
# ==========================================================
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


# ==========================================================
# CONFIG
# ==========================================================
HTML_MINIMO_UTIL = 3000  # 🔥 aumentado

DOMINIOS_PRIORIDADE_JS = {
    "atacadum.com.br",
    "megacentereletronicos.com.br",  # 🔥 ADICIONADO
}


# ==========================================================
# HELPERS
# ==========================================================
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

    # 🔥 NOVO: precisa ter sinais de produto
    sinais_produto = [
        "price",
        "preco",
        "produto",
        "product",
        "comprar",
        "add to cart",
    ]

    if not any(s in html_baixo for s in sinais_produto):
        return True

    return False


def _usar_js_prioritario(url: str) -> bool:
    dominio = _dominio(url)
    return dominio in DOMINIOS_PRIORIDADE_JS


def _storage_state(url: str) -> str | None:
    if storage_state_path_por_dominio is None:
        return None
    try:
        return storage_state_path_por_dominio(_normalizar_url(url))
    except Exception:
        return None


def _payload_requests(url: str, html: str | None) -> dict[str, Any]:
    return {
        "ok": bool(html),
        "engine": "requests",
        "url": url,
        "final_url": url,
        "html": html,
        "network_records": [],
        "error": "" if html else "Falha no fetch via requests.",
    }


# ==========================================================
# MAIN
# ==========================================================
def fetch_payload_router(
    url: str,
    preferir_js: bool = False,
) -> dict[str, Any]:

    url = _normalizar_url(url)
    dominio = _dominio(url)

    log_debug(f"[FETCH_ROUTER] START | {url}")

    # ======================================================
    # 🔥 1) PRIORIDADE TOTAL PARA PLAYWRIGHT
    # ======================================================
    if fetch_playwright_payload:
        log_debug("[FETCH_ROUTER] TENTANDO PLAYWRIGHT")

        try:
            payload_js = fetch_playwright_payload(url)

            if payload_js.get("ok") and payload_js.get("html"):
                log_debug("[FETCH_ROUTER] PLAYWRIGHT OK")
                return payload_js

        except Exception as e:
            log_debug(f"[FETCH_ROUTER] erro playwright: {e}")

    # ======================================================
    # 2) REQUESTS
    # ======================================================
    html = fetch_url(url)

    if html and not _parece_html_fraco(html):
        log_debug("[FETCH_ROUTER] REQUESTS OK")
        return _payload_requests(url, html)

    # ======================================================
    # 3) FALLBACK FINAL
    # ======================================================
    if tentar_fetch_com_fallback_js:
        log_debug("[FETCH_ROUTER] FALLBACK JS FINAL")

        payload_js = tentar_fetch_com_fallback_js(
            url=url,
            html_requests=html,
        )

        if payload_js.get("ok"):
            return payload_js

    log_debug("[FETCH_ROUTER] FALHA TOTAL")

    return _payload_requests(url, html)
