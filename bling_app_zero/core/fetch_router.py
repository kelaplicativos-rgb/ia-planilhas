from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from bling_app_zero.core.fetcher import fetch_url

# ==========================================================
# LOG
# ==========================================================
try:
    from bling_app_zero.utils.excel_logs import log_debug
except Exception:
    try:
        from bling_app_zero.utils.excel import log_debug
    except Exception:
        def log_debug(_msg: str, _nivel: str = "INFO") -> None:
            return None


# ==========================================================
# PLAYWRIGHT
# ==========================================================
try:
    from bling_app_zero.core.playwright_fetcher import (
        fetch_playwright_payload,
    )
except Exception:
    fetch_playwright_payload = None


# ==========================================================
# HELPERS
# ==========================================================
def _safe_str(valor: Any) -> str:
    try:
        return str(valor or "").strip()
    except Exception:
        return ""


def _normalizar_url(url: str) -> str:
    url = _safe_str(url)
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url


def _html_parece_vazio(html: str | None) -> bool:
    if not html:
        return True

    html_lower = html.lower()

    sinais_vazio = [
        "carregando",
        "loading",
        "javascript required",
        "enable javascript",
    ]

    if any(x in html_lower for x in sinais_vazio):
        return True

    # pouco conteúdo real
    if len(html) < 5000:
        return True

    return False


def _payload_requests(url: str, html: str | None, erro: str = "") -> dict[str, Any]:
    url = _normalizar_url(url)
    return {
        "ok": bool(html),
        "engine": "requests",
        "url": url,
        "final_url": url,
        "html": html,
        "network_records": [],
        "error": erro if erro else ("" if html else "Falha no fetch via requests."),
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
    # 1. REQUESTS
    # ======================================================
    html = fetch_url(url)

    if html:
        log_debug("[FETCH_ROUTER] REQUESTS OK")

        # 🔥 DETECTA HTML FALSO
        if _html_parece_vazio(html):
            log_debug("[FETCH_ROUTER] HTML VAZIO DETECTADO → USANDO PLAYWRIGHT")

            if fetch_playwright_payload:
                try:
                    payload_js = fetch_playwright_payload(url)

                    if payload_js.get("html"):
                        log_debug("[FETCH_ROUTER] PLAYWRIGHT OK")
                        return payload_js

                except Exception as e:
                    log_debug(f"[FETCH_ROUTER] erro playwright: {e}", "WARNING")

        return _payload_requests(url, html)

    # ======================================================
    # 2. PLAYWRIGHT (FALLBACK TOTAL)
    # ======================================================
    if fetch_playwright_payload:
        log_debug("[FETCH_ROUTER] FALLBACK TOTAL PLAYWRIGHT")

        try:
            payload_js = fetch_playwright_payload(url)

            if payload_js.get("html"):
                return payload_js

        except Exception as e:
            log_debug(f"[FETCH_ROUTER] erro playwright: {e}", "WARNING")

    log_debug("[FETCH_ROUTER] FALHA TOTAL")

    return _payload_requests(url, html)
