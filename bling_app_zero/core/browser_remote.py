from __future__ import annotations

from dataclasses import dataclass, field
from shutil import which
from typing import Any


@dataclass
class RemoteBrowserConfig:
    url: str
    state_namespace: str = 'supplier_remote_browser'
    headless: bool = True
    timeout_ms: int = 45_000
    width: int = 1366
    height: int = 900


@dataclass
class RemoteBrowserSnapshot:
    ok: bool
    url: str = ''
    final_url: str = ''
    title: str = ''
    screenshot_png: bytes | None = None
    html: str = ''
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    state_saved: bool = False
    meta: dict[str, Any] = field(default_factory=dict)


def _chromium_executable() -> str | None:
    for candidate in ('chromium', 'chromium-browser', 'google-chrome', 'google-chrome-stable'):
        path = which(candidate)
        if path:
            return path
    return None


def _clean_url(value: object) -> str:
    text = str(value or '').strip()
    return text if text.startswith(('http://', 'https://')) else ''


def open_remote_browser_snapshot(config: RemoteBrowserConfig) -> RemoteBrowserSnapshot:
    """Abre Chromium real no servidor e devolve snapshot visual da página.

    Este módulo substitui a ilusão do iframe. Ele não compartilha a aba externa do
    celular; ele executa um navegador do ambiente do app. Para operação 100%
    interativa tipo extensão/noVNC ainda será necessária uma camada de controle
    remoto, mas esta função já permite validar a página renderizada pelo servidor.
    """
    url = _clean_url(config.url)
    if not url:
        return RemoteBrowserSnapshot(ok=False, url=str(config.url or ''), errors=['URL inválida. Informe uma URL começando com http:// ou https://.'])

    warnings: list[str] = []
    executable = _chromium_executable()
    if not executable:
        warnings.append('Chromium do sistema não foi encontrado; tentando navegador instalado pelo Playwright.')

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return RemoteBrowserSnapshot(ok=False, url=url, warnings=warnings, errors=[f'Playwright indisponível: {exc}'])

    try:
        with sync_playwright() as p:
            launch_kwargs: dict[str, Any] = {
                'headless': config.headless,
                'args': [
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-blink-features=AutomationControlled',
                ],
            }
            if executable:
                launch_kwargs['executable_path'] = executable
            browser = p.chromium.launch(**launch_kwargs)
            context = browser.new_context(
                viewport={'width': int(config.width), 'height': int(config.height)},
                user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36',
                locale='pt-BR',
            )
            page = context.new_page()
            page.goto(url, wait_until='domcontentloaded', timeout=config.timeout_ms)
            try:
                page.wait_for_load_state('networkidle', timeout=min(config.timeout_ms, 12_000))
            except Exception:
                warnings.append('A página não ficou totalmente ociosa; snapshot feito com o DOM disponível.')
            final_url = page.url
            title = page.title()
            screenshot = page.screenshot(full_page=False, type='png')
            html = page.content()
            state_saved = False
            try:
                context.storage_state(path=f'/tmp/{config.state_namespace}_state.json')
                state_saved = True
            except Exception:
                pass
            browser.close()
            return RemoteBrowserSnapshot(
                ok=True,
                url=url,
                final_url=final_url,
                title=title,
                screenshot_png=screenshot,
                html=html,
                warnings=warnings,
                errors=[],
                state_saved=state_saved,
                meta={'width': config.width, 'height': config.height},
            )
    except Exception as exc:
        return RemoteBrowserSnapshot(ok=False, url=url, warnings=warnings, errors=[str(exc) or exc.__class__.__name__])


__all__ = ['RemoteBrowserConfig', 'RemoteBrowserSnapshot', 'open_remote_browser_snapshot']
