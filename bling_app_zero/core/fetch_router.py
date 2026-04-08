from __future__ import annotations

from typing import Any

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
HTML_MINIMO_UTIL = 1200

DOMINIOS_PRIORIDADE_JS = {
    "atacadum.com.br",
}

SELETORES_ESPERA: dict[str, list[str]] = {
    "megacentereletronicos.com.br": [
        "h1",
        ".product-title",
        ".product-name",
        ".price",
        ".preco",
        ".product-price",
        "main",
    ],
    "atacadum.com.br": [
        "h1",
        ".product-title",
        ".product-name",
        ".price",
        ".preco",
        ".product-price",
        "main",
    ],
}


# ==========================================================
# HELPERS
# ==========================================================
def _safe_str(valor: Any) -> str:
    if valor is None:
        return ""
    try:
        return str(valor).strip()
    except Exception:
        return ""


def _dominio(url: str) -> str:
    try:
        from urllib.parse import urlparse

        return urlparse(_safe_str(url)).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _parece_html_fraco(html: str | None) -> bool:
    html = _safe_str(html)
    if not html:
        return True

    html_baixo = html.lower()

    if len(html) < HTML_MINIMO_UTIL:
        return True

    sinais = [
        "access denied",
        "forbidden",
        "captcha",
        "cloudflare",
        "attention required",
        "security check",
        "verify you are human",
        "cf-browser-verification",
        "please enable cookies",
    ]
    if any(s in html_baixo for s in sinais):
        return True

    if 'id="__next"' in html_baixo and len(html) < 5000:
        return True

    if 'id="app"' in html_baixo and len(html) < 5000:
        return True

    if "__nuxt" in html_baixo and len(html) < 5000:
        return True

    return False


def _selector_por_dominio(url: str) -> str | None:
    dominio = _dominio(url)
    candidatos = SELETORES_ESPERA.get(dominio, [])

    for seletor in candidatos:
        if _safe_str(seletor):
            return seletor

    return None


def _usar_js_prioritario(url: str) -> bool:
    dominio = _dominio(url)
    return dominio in DOMINIOS_PRIORIDADE_JS


def _storage_state(url: str) -> str | None:
    if storage_state_path_por_dominio is None:
        return None

    try:
        return storage_state_path_por_dominio(url)
    except Exception:
        return None


def _payload_requests(url: str, html: str | None) -> dict[str, Any]:
    html = html if isinstance(html, str) else None
    return {
        "ok": bool(html),
        "engine": "requests",
        "url": url,
        "final_url": url,
        "html": html,
        "title": "",
        "status_hint": None,
        "blocked_hint": _parece_html_fraco(html),
        "network_records": [],
        "screenshot_path": None,
        "storage_state_path": None,
        "error": "" if html else "Falha no fetch via requests.",
    }


# ==========================================================
# API PRINCIPAL
# ==========================================================
def fetch_html_router(
    url: str,
    preferir_js: bool = False,
    wait_selector: str | None = None,
) -> str | None:
    payload = fetch_payload_router(
        url=url,
        preferir_js=preferir_js,
        wait_selector=wait_selector,
    )
    html = payload.get("html")
    return html if isinstance(html, str) and html.strip() else None


def fetch_payload_router(
    url: str,
    preferir_js: bool = False,
    wait_selector: str | None = None,
) -> dict[str, Any]:
    url = _safe_str(url)

    if not url:
        log_debug("[FETCH_ROUTER] URL vazia recebida.", "ERROR")
        return {
            "ok": False,
            "engine": "router",
            "url": "",
            "final_url": "",
            "html": None,
            "title": "",
            "status_hint": None,
            "blocked_hint": False,
            "network_records": [],
            "screenshot_path": None,
            "storage_state_path": None,
            "error": "URL vazia.",
        }

    dominio = _dominio(url)
    seletor_final = wait_selector or _selector_por_dominio(url)
    state_path = _storage_state(url)

    log_debug(
        f"[FETCH_ROUTER] Início | dominio={dominio} | preferir_js={preferir_js} | url={url}"
    )

    # ======================================================
    # 1) JS prioritário por domínio ou por chamada explícita
    # ======================================================
    if preferir_js or _usar_js_prioritario(url):
        if fetch_playwright_payload is not None:
            log_debug(
                f"[FETCH_ROUTER] JS prioritário acionado | dominio={dominio} | url={url}"
            )
            try:
                payload_js = fetch_playwright_payload(
                    url=url,
                    wait_selector=seletor_final,
                    storage_state_path=state_path,
                    screenshot_on_error=True,
                    headless=True,
                )
                if payload_js.get("ok") and payload_js.get("html"):
                    return payload_js

                log_debug(
                    f"[FETCH_ROUTER] JS prioritário falhou, tentando requests | "
                    f"dominio={dominio} | erro={payload_js.get('error', '')}",
                    "WARNING",
                )
            except Exception as exc:
                log_debug(
                    f"[FETCH_ROUTER] Erro no JS prioritário | {type(exc).__name__}: {exc}",
                    "WARNING",
                )

        html_requests = fetch_url(url)
        return _payload_requests(url, html_requests)

    # ======================================================
    # 2) Primeiro requests
    # ======================================================
    html_requests = fetch_url(url)
    payload_req = _payload_requests(url, html_requests)

    if html_requests and not _parece_html_fraco(html_requests):
        log_debug(
            f"[FETCH_ROUTER] Requests suficiente | dominio={dominio} | url={url}"
        )
        return payload_req

    # ======================================================
    # 3) Fallback JS inteligente
    # ======================================================
    if tentar_fetch_com_fallback_js is not None:
        try:
            log_debug(
                f"[FETCH_ROUTER] Acionando fallback JS | dominio={dominio} | url={url}"
            )

            payload_js = tentar_fetch_com_fallback_js(
                url=url,
                html_requests=html_requests,
                wait_selector=seletor_final,
                storage_state_path=state_path,
            )

            if payload_js.get("ok") and payload_js.get("html"):
                return payload_js

            log_debug(
                f"[FETCH_ROUTER] Fallback JS sem sucesso | dominio={dominio} | "
                f"erro={payload_js.get('error', '')}",
                "WARNING",
            )
        except Exception as exc:
            log_debug(
                f"[FETCH_ROUTER] Erro no fallback JS | {type(exc).__name__}: {exc}",
                "WARNING",
            )

    return payload_req


# ==========================================================
# API AUXILIAR DE DIAGNÓSTICO
# ==========================================================
def diagnosticar_fetch(
    url: str,
    preferir_js: bool = False,
    wait_selector: str | None = None,
) -> dict[str, Any]:
    payload = fetch_payload_router(
        url=url,
        preferir_js=preferir_js,
        wait_selector=wait_selector,
    )

    html = _safe_str(payload.get("html"))
    payload["html_len"] = len(html)
    payload["dominio"] = _dominio(url)
    payload["usou_js"] = payload.get("engine") == "playwright"
    payload["html_fraco"] = _parece_html_fraco(html)

    return payload
