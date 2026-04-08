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
# VERSION
# ==========================================================
PLAYWRIGHT_VERSION = "V2_MODULAR_OK"


# ==========================================================
# LOG
# ==========================================================
try:
    from bling_app_zero.utils.excel_logs import log_debug
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
PLAYWRIGHT_NAV_TIMEOUT_MS = 45000
PLAYWRIGHT_WAIT_AFTER_LOAD_MS = 2500
PLAYWRIGHT_SCROLL_PAUSE_MS = 800
PLAYWRIGHT_MAX_SCROLLS = 8


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
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url


def _dominio(url: str) -> str:
    try:
        return urlparse(_normalizar_url(url)).netloc
    except Exception:
        return ""


def _parece_bloqueio(html: str) -> bool:
    h = (html or "").lower()
    sinais = ["captcha", "cloudflare", "access denied", "forbidden"]
    return any(s in h for s in sinais)


# ==========================================================
# SCROLL INTELIGENTE
# ==========================================================
def _auto_scroll(page: Any):
    last_height = 0

    for _ in range(PLAYWRIGHT_MAX_SCROLLS):
        try:
            height = page.evaluate("document.body.scrollHeight")
        except Exception:
            break

        if height == last_height:
            break

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(PLAYWRIGHT_SCROLL_PAUSE_MS)

        last_height = height


# ==========================================================
# MAIN
# ==========================================================
def fetch_playwright_payload(url: str) -> dict[str, Any]:

    url = _normalizar_url(url)

    payload = {
        "ok": False,
        "engine": "playwright",
        "url": url,
        "final_url": url,
        "html": "",
        "error": "",
    }

    if not sync_playwright:
        payload["error"] = "playwright_nao_instalado"
        return payload

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            context = browser.new_context(
                user_agent="Mozilla/5.0",
                locale="pt-BR",
                ignore_https_errors=True,
            )

            page = context.new_page()

            page.goto(url, timeout=PLAYWRIGHT_NAV_TIMEOUT_MS)

            page.wait_for_timeout(PLAYWRIGHT_WAIT_AFTER_LOAD_MS)

            _auto_scroll(page)

            html = page.content()

            payload["html"] = html
            payload["final_url"] = page.url

            if html and len(html) > 1200 and not _parece_bloqueio(html):
                payload["ok"] = True
            else:
                payload["error"] = "html_fraco_ou_bloqueado"

            browser.close()

    except Exception as e:
        payload["error"] = str(e)

    return payload
