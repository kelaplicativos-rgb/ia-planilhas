from __future__ import annotations

from typing import Any

from bling_app_zero.core.fetcher import fetch_url

# ==========================================================
# LOG
# ==========================================================
try:
    from bling_app_zero.utils.excel_logs import log_debug
except Exception:
    def log_debug(_msg: str, _nivel: str = "INFO") -> None:
        return None


# ==========================================================
# PLAYWRIGHT
# ==========================================================
try:
    from bling_app_zero.core.playwright_fetcher import fetch_playwright_payload
except Exception:
    fetch_playwright_payload = None


# ==========================================================
# VERSION (DEBUG)
# ==========================================================
ROUTER_VERSION = "V2_MODULAR_OK"


# ==========================================================
# HELPERS
# ==========================================================
def _safe_str(v: Any) -> str:
    try:
        return str(v or "").strip()
    except Exception:
        return ""


def _normalizar_url(url: str) -> str:
    url = _safe_str(url)
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url


def _html_ruim(html: str | None) -> bool:
    if not html:
        return True

    html = str(html).strip()
    if not html:
        return True

    # HTML grande deve ser aceito
    if len(html) > 2000:
        return False

    h = html.lower()

    # somente sinais reais de bloqueio/dependência crítica de JS
    sinais_bloqueio = [
        "captcha",
        "cloudflare",
        "access denied",
        "forbidden",
        "enable javascript",
        "javascript required",
    ]

    if any(s in h for s in sinais_bloqueio):
        return True

    return False


# ==========================================================
# REQUESTS
# ==========================================================
def _fetch_requests(url: str) -> dict[str, Any]:
    try:
        html = fetch_url(url)
        html = _safe_str(html)

        return {
            "ok": bool(html),
            "engine": "requests",
            "url": url,
            "html": html,
            "error": "" if html else "html_vazio",
        }
    except Exception as e:
        return {
            "ok": False,
            "engine": "requests",
            "url": url,
            "html": "",
            "error": str(e),
        }


# ==========================================================
# PLAYWRIGHT
# ==========================================================
def _fetch_playwright(url: str) -> dict[str, Any]:
    if not fetch_playwright_payload:
        return {
            "ok": False,
            "engine": "playwright",
            "url": url,
            "html": "",
            "error": "playwright_indisponivel",
        }

    try:
        payload = fetch_playwright_payload(url)
        html = _safe_str(payload.get("html"))

        return {
            "ok": bool(html),
            "engine": "playwright",
            "url": url,
            "html": html,
            "error": _safe_str(payload.get("error")),
        }

    except Exception as e:
        return {
            "ok": False,
            "engine": "playwright",
            "url": url,
            "html": "",
            "error": str(e),
        }


# ==========================================================
# MAIN ROUTER
# ==========================================================
def fetch_payload_router(
    url: str,
    preferir_js: bool = False,
) -> dict[str, Any]:

    url = _normalizar_url(url)

    if not url:
        return {
            "ok": False,
            "engine": "none",
            "url": "",
            "html": "",
            "error": "url_invalida",
        }

    log_debug(f"[FETCH_ROUTER] START {url}", "INFO")

    # ======================================================
    # PRIORIDADE PLAYWRIGHT
    # ======================================================
    if preferir_js:
        log_debug("[FETCH_ROUTER] FORCANDO PLAYWRIGHT", "INFO")

        payload = _fetch_playwright(url)

        if payload["ok"] and not _html_ruim(payload["html"]):
            return payload

        log_debug("[FETCH_ROUTER] PLAYWRIGHT FALHOU, tentando requests", "WARNING")

    # ======================================================
    # REQUESTS
    # ======================================================
    payload = _fetch_requests(url)

    if payload["ok"] and not _html_ruim(payload["html"]):
        log_debug("[FETCH_ROUTER] REQUESTS OK", "INFO")
        return payload

    log_debug("[FETCH_ROUTER] REQUESTS FRACO → PLAYWRIGHT", "WARNING")

    # ======================================================
    # FALLBACK PLAYWRIGHT
    # ======================================================
    payload_js = _fetch_playwright(url)

    if payload_js["ok"] and not _html_ruim(payload_js["html"]):
        log_debug("[FETCH_ROUTER] PLAYWRIGHT OK", "INFO")
        return payload_js

    # ======================================================
    # FALHA TOTAL
    # ======================================================
    log_debug("[FETCH_ROUTER] FALHA TOTAL", "ERROR")

    return {
        "ok": False,
        "engine": "none",
        "url": url,
        "html": "",
        "error": "falha_total_fetch",
    }
