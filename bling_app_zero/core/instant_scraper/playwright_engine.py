from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

import pandas as pd

from .instant_dom_engine import instant_extract


@dataclass
class BrowserExtractResult:
    dataframe: pd.DataFrame
    html: str = ""
    status: str = ""


def _normalizar_url(url: str) -> str:
    valor = str(url or "").strip()
    if not valor:
        return ""
    if not valor.startswith(("http://", "https://")):
        valor = "https://" + valor
    return valor


def _safe_progress(progress_callback: Callable[[int, str, int], None] | None, percent: int, msg: str, total: int = 0) -> None:
    if progress_callback:
        try:
            progress_callback(percent, msg, total)
        except Exception:
            pass


def browser_extract(
    url: str,
    *,
    max_clicks: int = 5,
    timeout_ms: int = 25000,
    progress_callback: Callable[[int, str, int], None] | None = None,
) -> BrowserExtractResult:
    """
    Motor opcional estilo Instant Data Scraper.

    Usa Playwright quando disponível para renderizar páginas com JavaScript,
    tentar botões de carregar mais e extrair blocos/tabelas repetidas do DOM final.
    Em ambiente sem browser instalado, falha silenciosamente e permite fallback HTTP.
    """
    url = _normalizar_url(url)
    if not url:
        return BrowserExtractResult(pd.DataFrame(), "", "url_vazia")

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return BrowserExtractResult(pd.DataFrame(), "", f"playwright_indisponivel: {exc}")

    html = ""
    try:
        _safe_progress(progress_callback, 5, "Abrindo browser real...", 0)
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-setuid-sandbox",
                ],
            )
            context = browser.new_context(
                viewport={"width": 1366, "height": 768},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="pt-BR",
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(1500)

            _safe_progress(progress_callback, 25, "Renderização inicial concluída.", 0)

            selectors = [
                "button:has-text('Carregar mais')",
                "button:has-text('Ver mais')",
                "button:has-text('Mostrar mais')",
                "a:has-text('Carregar mais')",
                "a:has-text('Ver mais')",
                "a:has-text('Mostrar mais')",
                "button[class*='more']",
                "a[class*='more']",
            ]

            clicks = 0
            for _ in range(max(0, int(max_clicks))):
                clicked = False
                for selector in selectors:
                    try:
                        loc = page.locator(selector).first
                        if loc.count() > 0 and loc.is_visible(timeout=1000):
                            loc.click(timeout=2500)
                            page.wait_for_timeout(1200)
                            clicks += 1
                            clicked = True
                            _safe_progress(progress_callback, 35 + min(clicks * 8, 35), f"Clique automático em carregar mais: {clicks}", clicks)
                            break
                    except Exception:
                        continue
                if not clicked:
                    break

            for pos in [500, 1200, 2200, 3600, 5200, 7600]:
                try:
                    page.mouse.wheel(0, pos)
                    page.wait_for_timeout(350)
                except Exception:
                    pass

            html = page.content()
            context.close()
            browser.close()

        _safe_progress(progress_callback, 80, "DOM renderizado. Detectando tabelas e cards...", 0)
        df = instant_extract(html, url, min_score=35)
        if isinstance(df, pd.DataFrame) and not df.empty:
            df = df.copy().fillna("")
            df["agente_estrategia"] = "browser_instant_dom"
            return BrowserExtractResult(df.reset_index(drop=True), html, "ok")
        return BrowserExtractResult(pd.DataFrame(), html, "sem_blocos_detectados")
    except Exception as exc:
        return BrowserExtractResult(pd.DataFrame(), html, f"erro_browser: {exc}")


def run_browser_scraper(url: str) -> pd.DataFrame:
    return browser_extract(url).dataframe
