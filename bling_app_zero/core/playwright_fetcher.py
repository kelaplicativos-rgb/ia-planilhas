from __future__ import annotations

import json
import os
import re
import tempfile
import time
import subprocess  # 🔥 ADICIONADO
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
    ]
    return any(s in t for s in sinais)


# ==========================================================
# NETWORK
# ==========================================================
def _preparar_captura_network(page: Any, registros: list[dict[str, Any]]) -> None:
    def _on_response(response: Any) -> None:
        if len(registros) >= PLAYWRIGHT_MAX_NETWORK_RECORDS:
            return
        try:
            content_type = response.headers.get("content-type", "").lower()
            if "json" in content_type:
                try:
                    registros.append({
                        "url": response.url,
                        "json": response.json()
                    })
                except Exception:
                    pass
        except Exception:
            pass

    page.on("response", _on_response)


# ==========================================================
# FETCH PRINCIPAL
# ==========================================================
def fetch_playwright_payload(url: str, headless: bool = True) -> dict:

    url = _normalizar_url(url)

    payload = {
        "ok": False,
        "html": None,
        "network_records": [],
        "error": "",
        "engine": "playwright"
    }

    if not sync_playwright:
        payload["error"] = "Playwright não instalado"
        return payload

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless,
                args=["--no-sandbox"]
            )

            context = browser.new_context()
            page = context.new_page()

            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            registros = []
            _preparar_captura_network(page, registros)

            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            html = page.content()

            payload["html"] = html
            payload["network_records"] = registros

            if html:
                payload["ok"] = True

            browser.close()

    except Exception as e:
        payload["error"] = str(e)

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
            "html": html_requests,
            "network_records": []
        }

    log_debug(f"[PLAYWRIGHT] fallback ativado | {url}")
    return fetch_playwright_payload(url)


def storage_state_path_por_dominio(url: str) -> str:
    dominio = _dominio(url) or "site"
    pasta = Path(tempfile.gettempdir()) / "pw_state"
    pasta.mkdir(parents=True, exist_ok=True)
    return str(pasta / f"{dominio}.json")
