from __future__ import annotations

import asyncio
from typing import Optional


class BrowserFetcher:
    """
    Fallback com Playwright:
    - abre a página como navegador real
    - faz scroll automático
    - retorna HTML renderizado
    """

    def __init__(
        self,
        timeout_ms: int = 30000,
        scroll_rounds: int = 8,
        wait_after_scroll_ms: int = 800,
    ):
        self.timeout_ms = timeout_ms
        self.scroll_rounds = scroll_rounds
        self.wait_after_scroll_ms = wait_after_scroll_ms

    def fetch(self, url: str) -> str:
        try:
            return asyncio.run(self._fetch_async(url))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self._fetch_async(url))
            finally:
                loop.close()

    async def _fetch_async(self, url: str) -> str:
        try:
            from playwright.async_api import async_playwright
        except Exception:
            return ""

        browser = None

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--disable-setuid-sandbox",
                    ],
                )

                page = await browser.new_page(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1366, "height": 768},
                    locale="pt-BR",
                )

                await page.goto(
                    self._normalize_url(url),
                    wait_until="domcontentloaded",
                    timeout=self.timeout_ms,
                )

                await self._auto_scroll(page)

                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass

                html = await page.content()
                return html or ""

        except Exception:
            return ""

        finally:
            try:
                if browser is not None:
                    await browser.close()
            except Exception:
                pass

    async def _auto_scroll(self, page) -> None:
        previous_height: Optional[int] = None

        for _ in range(self.scroll_rounds):
            try:
                current_height = await page.evaluate("document.body.scrollHeight")

                if previous_height is not None and current_height == previous_height:
                    break

                previous_height = current_height

                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(self.wait_after_scroll_ms)

            except Exception:
                break

    def _normalize_url(self, url: str) -> str:
        url = str(url or "").strip()

        if not url:
            return ""

        if url.startswith("//"):
            url = "https:" + url

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        return url


def fetch_html_browser(url: str) -> str:
    return BrowserFetcher().fetch(url)
