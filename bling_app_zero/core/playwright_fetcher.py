from __future__ import annotations

import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    from bling_app_zero.utils.excel_logs import log_debug
except Exception:
    def log_debug(*args, **kwargs): pass

try:
    from playwright.sync_api import sync_playwright
except Exception:
    sync_playwright = None


def _safe_str(valor: Any) -> str:
    try:
        return str(valor or "").strip()
    except:
        return ""


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
    except:
        return ""


# 🔥 CAPTURA DE NETWORK (VOLTOU)
def _preparar_captura_network(page, registros):
    def on_response(response):
        try:
            if len(registros) > 100:
                return

            content_type = response.headers.get("content-type", "").lower()

            if "json" in content_type:
                try:
                    data = response.json()
                except:
                    return

                registros.append({
                    "url": response.url,
                    "json": data
                })
        except:
            pass

    page.on("response", on_response)


def fetch_playwright_payload(url: str, headless: bool = True) -> dict:

    url = _normalizar_url(url)

    payload = {
        "ok": False,
        "html": None,
        "network_records": [],
        "error": "",
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

            # 🔥 STEALTH
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            # 🔥 ATIVA NETWORK
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
