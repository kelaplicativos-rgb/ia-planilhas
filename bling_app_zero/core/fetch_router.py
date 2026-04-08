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
        tentar_fetch_com_fallback_js,
    )
except Exception:
    fetch_playwright_payload = None
    tentar_fetch_com_fallback_js = None


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

    log_debug(f"[FETCH_ROUTER] START | {url}")

    # ======================================================
    # 🔥 1) PLAYWRIGHT PRIMEIRO (ACEITA HTML MESMO SEM ok)
    # ======================================================
    if fetch_playwright_payload:
        log_debug("[FETCH_ROUTER] TENTANDO PLAYWRIGHT")

        try:
            payload_js = fetch_playwright_payload(url)

            html_js = payload_js.get("html")

            # 🔥 CORREÇÃO PRINCIPAL
            if html_js and len(html_js) > 1000:
                log_debug("[FETCH_ROUTER] PLAYWRIGHT HTML OK")
                return payload_js

        except Exception as e:
            log_debug(f"[FETCH_ROUTER] erro playwright: {e}")

    # ======================================================
    # 2) REQUESTS
    # ======================================================
    html = fetch_url(url)

    if html:
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

        if payload_js.get("html"):
            return payload_js

    log_debug("[FETCH_ROUTER] FALHA TOTAL")

    return _payload_requests(url, html)
