from __future__ import annotations

import asyncio
from typing import Any, Optional


LAST_BROWSER_FETCH_INFO = {
    "habilitado": False,
    "executado": False,
    "ok": False,
    "erro": "",
    "motivo": "",
    "html_chars": 0,
    "url_final": "",
}


def _registrar_browser_info(**kwargs: Any) -> None:
    for chave in list(LAST_BROWSER_FETCH_INFO.keys()):
        if chave in kwargs:
            LAST_BROWSER_FETCH_INFO[chave] = kwargs[chave]


def obter_ultimo_browser_fetch_info() -> dict[str, Any]:
    return dict(LAST_BROWSER_FETCH_INFO)


def playwright_disponivel() -> bool:
    try:
        import playwright.async_api  # noqa: F401
        return True
    except Exception:
        return False


class BrowserFetcher:
    """
    Fallback opcional com Playwright.

    Regras:
    - não quebra o app se Playwright não estiver instalado;
    - tenta abrir a página como navegador real;
    - faz scroll automático;
    - retorna HTML renderizado;
    - registra diagnóstico para a UI.
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
        url = self._normalize_url(url)
        _registrar_browser_info(
            habilitado=playwright_disponivel(),
            executado=True,
            ok=False,
            erro="",
            motivo="inicio",
            html_chars=0,
            url_final=url,
        )

        if not url:
            _registrar_browser_info(erro="URL vazia", motivo="url_vazia")
            return ""

        if not playwright_disponivel():
            _registrar_browser_info(
                erro="Playwright não está instalado neste ambiente.",
                motivo="playwright_indisponivel",
            )
            return ""

        try:
            return asyncio.run(self._fetch_async(url))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self._fetch_async(url))
            except Exception as exc:
                _registrar_browser_info(erro=str(exc), motivo="erro_event_loop")
                return ""
            finally:
                loop.close()
        except Exception as exc:
            _registrar_browser_info(erro=str(exc), motivo="erro_browser_fetch")
            return ""

    async def _fetch_async(self, url: str) -> str:
        try:
            from playwright.async_api import async_playwright
        except Exception as exc:
            _registrar_browser_info(
                erro=f"Falha ao importar Playwright: {exc}",
                motivo="falha_import_playwright",
            )
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
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1366, "height": 900},
                    locale="pt-BR",
                )

                await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self.timeout_ms,
                )

                await self._auto_scroll(page)

                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass

                html = await page.content()
                html = html or ""

                _registrar_browser_info(
                    ok=bool(html.strip()),
                    erro="" if html.strip() else "Browser abriu, mas HTML veio vazio.",
                    motivo="ok" if html.strip() else "html_vazio",
                    html_chars=len(html),
                    url_final=page.url or url,
                )
                return html

        except Exception as exc:
            _registrar_browser_info(
                ok=False,
                erro=str(exc),
                motivo="erro_execucao_playwright",
                html_chars=0,
                url_final=url,
            )
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
