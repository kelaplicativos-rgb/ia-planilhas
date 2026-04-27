from __future__ import annotations

from typing import Any, Dict, Optional


def fetch_playwright_payload(
    url: str,
    auth_config: Optional[Dict[str, Any]] = None,
    headless: bool = True,
    screenshot_on_error: bool = False,
) -> Dict[str, Any]:
    result = {"ok": False, "html": "", "error": "", "status": ""}

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        result["error"] = f"Playwright indisponível: {exc}"
        result["status"] = "playwright_import_error"
        return result

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                ],
            )

            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1366, "height": 768},
                locale="pt-BR",
                timezone_id="America/Sao_Paulo",
            )

            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=70000)

            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                pass

            page.wait_for_timeout(3500)

            try:
                page.mouse.wheel(0, 2500)
                page.wait_for_timeout(1200)
                page.mouse.wheel(0, 2500)
                page.wait_for_timeout(1200)
            except Exception:
                pass

            html = page.content() or ""

            result["ok"] = bool(html)
            result["html"] = html
            result["status"] = "ok" if html else "html_empty"

            context.close()
            browser.close()

    except Exception as exc:
        result["error"] = str(exc)
        result["status"] = "playwright_runtime_error"

    return result
