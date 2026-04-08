from __future__ import annotations

import json
import os
import re
import tempfile
import time
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# ==========================================================
# GARANTE CHROMIUM NO AMBIENTE
# ==========================================================
try:
    subprocess.run(
        ["playwright", "install", "chromium"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
except Exception:
    pass

# ==========================================================
# LOG (BLINDADO)
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
# IMPORT PLAYWRIGHT
# ==========================================================
try:
    from playwright.sync_api import (
        TimeoutError as PlaywrightTimeoutError,
        sync_playwright,
    )
except Exception:
    sync_playwright = None
    PlaywrightTimeoutError = Exception


# ==========================================================
# CONFIG
# ==========================================================
PLAYWRIGHT_DEFAULT_TIMEOUT_MS = 30000
PLAYWRIGHT_NAV_TIMEOUT_MS = 45000
PLAYWRIGHT_WAIT_AFTER_LOAD_MS = 2500
PLAYWRIGHT_MAX_SCROLLS = 6
PLAYWRIGHT_SCROLL_PAUSE_MS = 800
PLAYWRIGHT_HTML_MAX_CHARS = 6_000_000
PLAYWRIGHT_MAX_NETWORK_RECORDS = 120

USER_AGENT_CHROMIUM = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


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


def _normalizar_url(url: str) -> str:
    url = _safe_str(url)
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _dominio(url: str) -> str:
    try:
        return urlparse(_normalizar_url(url)).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _arquivo_temp(prefixo: str, sufixo: str) -> str:
    pasta = Path(tempfile.gettempdir()) / "ia_planilhas_playwright"
    pasta.mkdir(parents=True, exist_ok=True)
    nome = f"{prefixo}_{int(time.time() * 1000)}{sufixo}"
    return str(pasta / nome)


def _normalizar_html(html: str) -> str:
    html = html or ""
    if len(html) > PLAYWRIGHT_HTML_MAX_CHARS:
        return html[:PLAYWRIGHT_HTML_MAX_CHARS]
    return html


def _parece_bloqueio(texto: str) -> bool:
    t = (texto or "").lower()
    sinais = [
        "access denied",
        "forbidden",
        "captcha",
        "cloudflare",
        "attention required",
        "security check",
        "verify you are human",
        "robot or human",
        "cf-browser-verification",
        "please enable cookies",
    ]
    return any(s in t for s in sinais)


def _contexto_opcoes(storage_state_path: str | None = None) -> dict[str, Any]:
    opcoes: dict[str, Any] = {
        "user_agent": USER_AGENT_CHROMIUM,
        "locale": "pt-BR",
        "timezone_id": "America/Sao_Paulo",
        "ignore_https_errors": True,
        "java_script_enabled": True,
        "viewport": {"width": 1440, "height": 2200},
        "extra_http_headers": {
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "DNT": "1",
        },
    }

    if storage_state_path and os.path.exists(storage_state_path):
        opcoes["storage_state"] = storage_state_path

    return opcoes


def _auto_scroll(page: Any, max_scrolls: int = PLAYWRIGHT_MAX_SCROLLS) -> None:
    try:
        altura_anterior = -1

        for i in range(max_scrolls):
            try:
                altura_atual = page.evaluate("() => document.body.scrollHeight")
            except Exception:
                altura_atual = None

            page.evaluate(
                """
                () => {
                    window.scrollTo({
                        top: document.body.scrollHeight,
                        behavior: 'instant'
                    });
                }
                """
            )
            page.wait_for_timeout(PLAYWRIGHT_SCROLL_PAUSE_MS)

            if altura_atual == altura_anterior:
                log_debug(f"[PLAYWRIGHT] Scroll estabilizado na iteração {i + 1}")
                break

            altura_anterior = altura_atual
    except Exception as exc:
        log_debug(
            f"[PLAYWRIGHT] Falha no auto scroll: {type(exc).__name__}: {exc}",
            "WARNING",
        )


def _esperar_estabilidade_basica(page: Any) -> None:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=PLAYWRIGHT_NAV_TIMEOUT_MS)
    except Exception:
        pass

    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass

    try:
        page.wait_for_timeout(PLAYWRIGHT_WAIT_AFTER_LOAD_MS)
    except Exception:
        pass


def _serializar_json_seguro(valor: Any) -> str:
    try:
        return json.dumps(valor, ensure_ascii=False)
    except Exception:
        try:
            return str(valor)
        except Exception:
            return ""


def _limpar_texto_curto(texto: Any, limite: int = 500) -> str:
    s = re.sub(r"\s+", " ", _safe_str(texto))
    if len(s) > limite:
        return s[:limite]
    return s


def _extrair_json_de_response(response: Any) -> Any:
    try:
        request = response.request
        resource_type = _safe_str(getattr(request, "resource_type", ""))
        headers = getattr(response, "headers", {}) or {}
        content_type = _safe_str(headers.get("content-type", "")).lower()
        url = _safe_str(getattr(response, "url", ""))

        if "json" in content_type or resource_type in {"xhr", "fetch"} or url.endswith(".json"):
            try:
                return response.json()
            except Exception:
                try:
                    return response.text()
                except Exception:
                    return None
    except Exception:
        return None

    return None


# ==========================================================
# NETWORK
# ==========================================================
def _preparar_captura_network(page: Any, registros: list[dict[str, Any]]) -> None:
    def _on_response(response: Any) -> None:
        if len(registros) >= PLAYWRIGHT_MAX_NETWORK_RECORDS:
            return

        try:
            request = response.request
            item: dict[str, Any] = {
                "url": _safe_str(getattr(response, "url", "")),
                "method": _safe_str(getattr(request, "method", "")),
                "resource_type": _safe_str(getattr(request, "resource_type", "")),
                "status": int(getattr(response, "status", 0) or 0),
                "content_type": _safe_str(
                    (getattr(response, "headers", {}) or {}).get("content-type", "")
                ).lower(),
            }

            data = _extrair_json_de_response(response)
            if data is not None:
                item["json"] = data
                item["json_preview"] = _limpar_texto_curto(_serializar_json_seguro(data), 800)

            registros.append(item)
        except Exception:
            pass

    page.on("response", _on_response)


# ==========================================================
# FETCH PRINCIPAL
# ==========================================================
def fetch_url_playwright(
    url: str,
    wait_selector: str | None = None,
    storage_state_path: str | None = None,
    screenshot_on_error: bool = True,
    headless: bool = True,
) -> str | None:
    resultado = fetch_playwright_payload(
        url=url,
        wait_selector=wait_selector,
        storage_state_path=storage_state_path,
        screenshot_on_error=screenshot_on_error,
        headless=headless,
    )
    html = resultado.get("html")
    return html if isinstance(html, str) and html.strip() else None


def fetch_playwright_payload(
    url: str,
    wait_selector: str | None = None,
    storage_state_path: str | None = None,
    screenshot_on_error: bool = True,
    headless: bool = True,
) -> dict[str, Any]:
    url = _normalizar_url(url)

    payload: dict[str, Any] = {
        "ok": False,
        "url": url,
        "final_url": url,
        "html": None,
        "title": "",
        "status_hint": None,
        "blocked_hint": False,
        "network_records": [],
        "screenshot_path": None,
        "storage_state_path": storage_state_path,
        "error": "",
        "engine": "playwright",
    }

    if not url:
        payload["error"] = "URL vazia."
        log_debug("[PLAYWRIGHT] URL vazia recebida.", "ERROR")
        return payload

    if not sync_playwright:
        payload["error"] = "Playwright não instalado"
        log_debug("[PLAYWRIGHT] Biblioteca Playwright indisponível.", "ERROR")
        return payload

    browser = None
    context = None
    page = None

    try:
        log_debug(f"[PLAYWRIGHT] Iniciando | url={url}")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )

            context = browser.new_context(**_contexto_opcoes(storage_state_path))
            context.set_default_timeout(PLAYWRIGHT_DEFAULT_TIMEOUT_MS)
            context.set_default_navigation_timeout(PLAYWRIGHT_NAV_TIMEOUT_MS)

            page = context.new_page()

            try:
                page.add_init_script(
                    """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });

                    window.chrome = { runtime: {} };

                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3]
                    });

                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['pt-BR', 'pt', 'en-US']
                    });
                    """
                )
            except Exception:
                pass

            registros: list[dict[str, Any]] = []
            _preparar_captura_network(page, registros)

            response = page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=PLAYWRIGHT_NAV_TIMEOUT_MS,
            )

            if response is not None:
                try:
                    payload["status_hint"] = int(response.status)
                except Exception:
                    pass

            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=10000)
                    log_debug(f"[PLAYWRIGHT] wait_selector OK | {wait_selector}")
                except Exception as exc:
                    log_debug(
                        f"[PLAYWRIGHT] wait_selector falhou | seletor={wait_selector} | {type(exc).__name__}: {exc}",
                        "WARNING",
                    )

            _esperar_estabilidade_basica(page)
            _auto_scroll(page)

            try:
                html = page.content()
            except Exception:
                html = ""

            html = _normalizar_html(html)

            try:
                payload["title"] = _safe_str(page.title())
            except Exception:
                pass

            try:
                payload["final_url"] = _safe_str(page.url) or url
            except Exception:
                pass

            payload["html"] = html or None
            payload["network_records"] = registros
            payload["blocked_hint"] = _parece_bloqueio(html)

            if storage_state_path:
                try:
                    context.storage_state(path=storage_state_path)
                    payload["storage_state_path"] = storage_state_path
                except Exception:
                    pass

            if html and len(html) > 500 and not payload["blocked_hint"]:
                payload["ok"] = True
                log_debug(
                    f"[PLAYWRIGHT] Sucesso | final_url={payload['final_url']} | "
                    f"html_len={len(html)} | network_records={len(registros)}"
                )
            elif html:
                payload["error"] = "HTML retornado com indício de bloqueio ou insuficiente."
                log_debug(
                    f"[PLAYWRIGHT] HTML insuficiente/bloqueado | "
                    f"html_len={len(html)} | blocked={payload['blocked_hint']}",
                    "WARNING",
                )
            else:
                payload["error"] = "Página carregada sem HTML útil."
                log_debug("[PLAYWRIGHT] HTML vazio.", "WARNING")

    except PlaywrightTimeoutError as exc:
        payload["error"] = f"Timeout Playwright: {type(exc).__name__}: {exc}"
        log_debug(f"[PLAYWRIGHT] Timeout | url={url} | detalhe={payload['error']}", "ERROR")

        if screenshot_on_error and page is not None:
            try:
                screenshot_path = _arquivo_temp("playwright_timeout", ".png")
                page.screenshot(path=screenshot_path, full_page=True)
                payload["screenshot_path"] = screenshot_path
            except Exception:
                pass

    except Exception as exc:
        payload["error"] = f"{type(exc).__name__}: {exc}"
        log_debug(f"[PLAYWRIGHT] Erro geral | url={url} | detalhe={payload['error']}", "ERROR")

        if screenshot_on_error and page is not None:
            try:
                screenshot_path = _arquivo_temp("playwright_error", ".png")
                page.screenshot(path=screenshot_path, full_page=True)
                payload["screenshot_path"] = screenshot_path
            except Exception:
                pass

    finally:
        try:
            if context is not None and storage_state_path:
                try:
                    context.storage_state(path=storage_state_path)
                    payload["storage_state_path"] = storage_state_path
                except Exception:
                    pass
        except Exception:
            pass

        try:
            if page is not None:
                page.close()
        except Exception:
            pass

        try:
            if context is not None:
                context.close()
        except Exception:
            pass

        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass

    return payload


# ==========================================================
# FALLBACK
# ==========================================================
def tentar_fetch_com_fallback_js(
    url: str,
    html_requests: str | None = None,
    wait_selector: str | None = None,
    storage_state_path: str | None = None,
):
    html_requests = html_requests or ""

    if html_requests and len(html_requests) > 1500:
        return {
            "ok": True,
            "engine": "requests",
            "url": _normalizar_url(url),
            "final_url": _normalizar_url(url),
            "html": html_requests,
            "network_records": [],
            "error": "",
        }

    log_debug(f"[PLAYWRIGHT] fallback ativado | {url}")
    return fetch_playwright_payload(
        url=url,
        wait_selector=wait_selector,
        storage_state_path=storage_state_path,
        screenshot_on_error=True,
        headless=True,
    )


def storage_state_path_por_dominio(url: str) -> str:
    dominio = _dominio(url) or "site"
    pasta = Path(tempfile.gettempdir()) / "pw_state"
    pasta.mkdir(parents=True, exist_ok=True)
    return str(pasta / f"{dominio}.json")
