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


# 🔥 CORRIGIDO
def _normalizar_url(url: str) -> str:
    url = _safe_str(url)

    if not url:
        return ""

    if not url.startswith("http"):
        url = "https://" + url

    return url


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
    }

    if storage_state_path and os.path.exists(storage_state_path):
        opcoes["storage_state"] = storage_state_path

    return opcoes


# ==========================================================
# FETCH PRINCIPAL
# ==========================================================
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

    if sync_playwright is None:
        payload["error"] = "Playwright não instalado."
        return payload

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )

            context = browser.new_context(**_contexto_opcoes(storage_state_path))
            page = context.new_page()

            # 🔥 STEALTH REAL
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });

                window.chrome = { runtime: {} };

                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1,2,3]
                });

                Object.defineProperty(navigator, 'languages', {
                    get: () => ['pt-BR','pt','en-US']
                });
            """)

            response = page.goto(url, wait_until="domcontentloaded")

            if response:
                payload["status_hint"] = response.status

            page.wait_for_timeout(2000)

            html = page.content()
            payload["html"] = html
            payload["title"] = page.title()
            payload["final_url"] = page.url

            if html:
                payload["ok"] = True

            browser.close()

    except Exception as e:
        payload["error"] = str(e)

    return payload
