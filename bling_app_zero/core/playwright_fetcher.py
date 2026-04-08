from __future__ import annotations

import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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
    from playwright.sync_api import (
        TimeoutError as PlaywrightTimeoutError,
        sync_playwright,
    )
except Exception:  # pragma: no cover
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
    return _safe_str(url)


def _dominio(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
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


def _limpar_texto_curto(texto: Any, limite: int = 280) -> str:
    s = re.sub(r"\s+", " ", _safe_str(texto))
    if len(s) > limite:
        return s[:limite]
    return s


def _serializar_json_seguro(valor: Any) -> str:
    try:
        return json.dumps(valor, ensure_ascii=False)
    except Exception:
        try:
            return str(valor)
        except Exception:
            return ""


def _extrair_json_de_response(response: Any) -> Any:
    try:
        request = response.request
        resource_type = _safe_str(getattr(request, "resource_type", ""))
        url = _safe_str(getattr(response, "url", ""))
        headers = getattr(response, "headers", {}) or {}
        content_type = _safe_str(headers.get("content-type", "")).lower()

        if "json" in content_type or resource_type in {"xhr", "fetch"}:
            try:
                return response.json()
            except Exception:
                try:
                    return response.text()
                except Exception:
                    return None

        if url.lower().endswith(".json"):
            try:
                return response.json()
            except Exception:
                return None
    except Exception:
        return None

    return None


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


def _preparar_captura_network(page: Any, registros: list[dict[str, Any]]) -> None:
    def _on_response(response: Any) -> None:
        if len(registros) >= PLAYWRIGHT_MAX_NETWORK_RECORDS:
            return

        try:
            request = response.request
            url = _safe_str(getattr(response, "url", ""))
            status = int(getattr(response, "status", 0) or 0)
            method = _safe_str(getattr(request, "method", ""))
            resource_type = _safe_str(getattr(request, "resource_type", ""))
            headers = getattr(response, "headers", {}) or {}
            content_type = _safe_str(headers.get("content-type", "")).lower()

            item: dict[str, Any] = {
                "url": url,
                "status": status,
                "method": method,
                "resource_type": resource_type,
                "content_type": content_type,
            }

            json_payload = _extrair_json_de_response(response)
            if json_payload is not None:
                item["json"] = json_payload
                item["json_preview"] = _limpar_texto_curto(
                    _serializar_json_seguro(json_payload),
                    800,
                )
            else:
                try:
                    if (
                        "text" in content_type
                        or "html" in content_type
                        or "javascript" in content_type
                    ):
                        texto = response.text()
                        item["text_preview"] = _limpar_texto_curto(texto, 800)
                except Exception:
                    pass

            registros.append(item)
        except Exception as exc:
            log_debug(
                f"[PLAYWRIGHT] Falha capturando response de rede: "
                f"{type(exc).__name__}: {exc}",
                "WARNING",
            )

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
    return resultado.get("html") if isinstance(resultado, dict) else None


def fetch_playwright_payload(
    url: str,
    wait_selector: str | None = None,
    storage_state_path: str | None = None,
    screenshot_on_error: bool = True,
    headless: bool = True,
) -> dict[str, Any]:
    """
    Browser real para páginas com JS pesado.

    Retorno:
    {
      "ok": bool,
      "url": str,
      "final_url": str,
      "html": str | None,
      "title": str,
      "status_hint": int | None,
      "blocked_hint": bool,
      "network_records": list[dict],
      "screenshot_path": str | None,
      "storage_state_path": str | None,
      "error": str,
      "engine": "playwright"
    }
    """
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

    if sync_playwright is None:
        payload["error"] = (
            "Playwright não está instalado no ambiente. "
            "Adicione 'playwright' nas dependências e instale os browsers."
        )
        log_debug("[PLAYWRIGHT] Biblioteca Playwright indisponível.", "ERROR")
        return payload

    dominio = _dominio(url)
    log_debug(
        f"[PLAYWRIGHT] Iniciando fetch browser real | dominio={dominio} | url={url}"
    )

    browser = None
    context = None
    page = None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )

            context = browser.new_context(**_contexto_opcoes(storage_state_path))
            context.set_default_timeout(PLAYWRIGHT_DEFAULT_TIMEOUT_MS)
            context.set_default_navigation_timeout(PLAYWRIGHT_NAV_TIMEOUT_MS)

            page = context.new_page()
            network_records: list[dict[str, Any]] = []
            _preparar_captura_network(page, network_records)

            status_hint: dict[str, Any] = {"status": None}

            def _on_main_response(response: Any) -> None:
                try:
                    if _safe_str(response.url).rstrip("/") == url.rstrip("/"):
                        status_hint["status"] = int(getattr(response, "status", 0) or 0)
                except Exception:
                    return None

            page.on("response", _on_main_response)

            response = page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=PLAYWRIGHT_NAV_TIMEOUT_MS,
            )

            if response is not None:
                try:
                    payload["status_hint"] = int(response.status)
                except Exception:
                    payload["status_hint"] = None

            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=10000)
                    log_debug(f"[PLAYWRIGHT] wait_selector OK | {wait_selector}")
                except Exception as exc:
                    log_debug(
                        f"[PLAYWRIGHT] wait_selector falhou | seletor={wait_selector} | "
                        f"{type(exc).__name__}: {exc}",
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
                titulo = _safe_str(page.title())
            except Exception:
                titulo = ""

            try:
                final_url = _safe_str(page.url) or url
            except Exception:
                final_url = url

            payload["html"] = html or None
            payload["title"] = titulo
            payload["final_url"] = final_url
            payload["network_records"] = network_records
            payload["blocked_hint"] = _parece_bloqueio(html)

            if payload["status_hint"] is None:
                payload["status_hint"] = status_hint.get("status")

            if storage_state_path:
                try:
                    context.storage_state(path=storage_state_path)
                    payload["storage_state_path"] = storage_state_path
                    log_debug(f"[PLAYWRIGHT] storage_state salvo em {storage_state_path}")
                except Exception as exc:
                    log_debug(
                        f"[PLAYWRIGHT] Falha salvando storage_state: "
                        f"{type(exc).__name__}: {exc}",
                        "WARNING",
                    )

            if html and not payload["blocked_hint"]:
                payload["ok"] = True
                log_debug(
                    f"[PLAYWRIGHT] Sucesso | status={payload['status_hint']} | "
                    f"titulo={titulo or '(sem título)'} | final_url={final_url}"
                )
            elif html:
                payload["error"] = (
                    "Página retornou conteúdo com indício de bloqueio/challenge."
                )
                log_debug(
                    f"[PLAYWRIGHT] Conteúdo carregado, mas com indício de bloqueio | "
                    f"final_url={final_url}",
                    "WARNING",
                )
            else:
                payload["error"] = "Página carregada sem HTML útil."
                log_debug(
                    f"[PLAYWRIGHT] HTML vazio/inútil | "
                    f"status={payload['status_hint']} | final_url={final_url}",
                    "WARNING",
                )

    except PlaywrightTimeoutError as exc:
        payload["error"] = f"Timeout Playwright: {type(exc).__name__}: {exc}"
        log_debug(
            f"[PLAYWRIGHT] Timeout | url={url} | detalhe={payload['error']}",
            "ERROR",
        )

        if screenshot_on_error and page is not None:
            try:
                screenshot_path = _arquivo_temp("playwright_timeout", ".png")
                page.screenshot(path=screenshot_path, full_page=True)
                payload["screenshot_path"] = screenshot_path
                log_debug(
                    f"[PLAYWRIGHT] Screenshot de timeout salvo em {screenshot_path}",
                    "INFO",
                )
            except Exception:
                pass

    except Exception as exc:
        payload["error"] = f"{type(exc).__name__}: {exc}"
        log_debug(
            f"[PLAYWRIGHT] Erro geral | url={url} | detalhe={payload['error']}",
            "ERROR",
        )

        if screenshot_on_error and page is not None:
            try:
                screenshot_path = _arquivo_temp("playwright_error", ".png")
                page.screenshot(path=screenshot_path, full_page=True)
                payload["screenshot_path"] = screenshot_path
                log_debug(
                    f"[PLAYWRIGHT] Screenshot de erro salvo em {screenshot_path}",
                    "INFO",
                )
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
# FERRAMENTAS AUXILIARES
# ==========================================================
def tentar_fetch_com_fallback_js(
    url: str,
    html_requests: str | None = None,
    wait_selector: str | None = None,
    storage_state_path: str | None = None,
) -> dict[str, Any]:
    """
    Decide quando vale subir browser real.
    """
    html_requests = html_requests or ""
    html_baixo = html_requests.lower()

    precisa_js = False

    if not html_requests.strip():
        precisa_js = True
    elif len(html_requests.strip()) < 1200:
        precisa_js = True
    elif 'id="__next"' in html_baixo or 'id="app"' in html_baixo:
        precisa_js = True
    elif "__nuxt" in html_baixo or "window.__initial_state__" in html_baixo:
        precisa_js = True
    elif _parece_bloqueio(html_requests):
        precisa_js = True

    if not precisa_js:
        return {
            "ok": True,
            "engine": "requests",
            "url": url,
            "final_url": url,
            "html": html_requests,
            "title": "",
            "status_hint": None,
            "blocked_hint": False,
            "network_records": [],
            "screenshot_path": None,
            "storage_state_path": storage_state_path,
            "error": "",
        }

    log_debug(f"[PLAYWRIGHT] Acionando fallback JS | url={url}")
    return fetch_playwright_payload(
        url=url,
        wait_selector=wait_selector,
        storage_state_path=storage_state_path,
        screenshot_on_error=True,
        headless=True,
    )


def storage_state_path_por_dominio(url: str) -> str:
    dominio = _dominio(url) or "site"
    pasta = Path(tempfile.gettempdir()) / "ia_planilhas_playwright_states"
    pasta.mkdir(parents=True, exist_ok=True)
    return str(pasta / f"{dominio}.json")
