from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from shutil import which
from typing import Any, Literal


@dataclass
class RemoteBrowserConfig:
    url: str
    state_namespace: str = 'supplier_remote_browser'
    headless: bool = True
    timeout_ms: int = 45_000
    width: int = 1366
    height: int = 900


@dataclass
class RemoteBrowserCommand:
    action: Literal['open', 'click_selector', 'click_text', 'type_selector', 'press', 'scroll_down', 'scroll_up', 'snapshot']
    value: str = ''
    text: str = ''


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


def _state_path(namespace: str) -> str:
    safe = ''.join(ch if ch.isalnum() or ch in {'-', '_'} else '_' for ch in str(namespace or 'supplier_remote_browser'))[:80]
    return f'/tmp/{safe}_state.json'


def _launch_browser(p, config: RemoteBrowserConfig):
    executable = _chromium_executable()
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
    return p.chromium.launch(**launch_kwargs)


def _new_context(browser, config: RemoteBrowserConfig):
    state_file = _state_path(config.state_namespace)
    kwargs: dict[str, Any] = {
        'viewport': {'width': int(config.width), 'height': int(config.height)},
        'user_agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36',
        'locale': 'pt-BR',
    }
    if Path(state_file).exists():
        kwargs['storage_state'] = state_file
    return browser.new_context(**kwargs)


def _snapshot_from_page(page, *, config: RemoteBrowserConfig, url: str, warnings: list[str], meta: dict[str, Any] | None = None) -> RemoteBrowserSnapshot:
    final_url = page.url
    title = page.title()
    screenshot = page.screenshot(full_page=False, type='png')
    html = page.content()
    state_saved = False
    try:
        page.context.storage_state(path=_state_path(config.state_namespace))
        state_saved = True
    except Exception:
        pass
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
        meta=meta or {'width': config.width, 'height': config.height},
    )


def open_remote_browser_snapshot(config: RemoteBrowserConfig) -> RemoteBrowserSnapshot:
    return run_remote_browser_command(config, RemoteBrowserCommand(action='open', value=config.url))


def run_remote_browser_command(config: RemoteBrowserConfig, command: RemoteBrowserCommand) -> RemoteBrowserSnapshot:
    """Executa um comando no Chromium real do servidor e devolve novo snapshot.

    Não é noVNC: cada comando abre Chromium, reaplica storage_state, executa a ação,
    salva cookies/localStorage e fecha. Isso permite controle operacional seguro no
    Streamlit: navegar, clicar, digitar, pressionar tecla e rolar a página.
    """
    url = _clean_url(config.url)
    if not url:
        return RemoteBrowserSnapshot(ok=False, url=str(config.url or ''), errors=['URL inválida. Informe uma URL começando com http:// ou https://.'])

    warnings: list[str] = []
    if not _chromium_executable():
        warnings.append('Chromium do sistema não foi encontrado; tentando navegador instalado pelo Playwright.')

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return RemoteBrowserSnapshot(ok=False, url=url, warnings=warnings, errors=[f'Playwright indisponível: {exc}'])

    try:
        with sync_playwright() as p:
            browser = _launch_browser(p, config)
            context = _new_context(browser, config)
            page = context.new_page()
            page.goto(url, wait_until='domcontentloaded', timeout=config.timeout_ms)
            try:
                page.wait_for_load_state('networkidle', timeout=min(config.timeout_ms, 12_000))
            except Exception:
                warnings.append('A página não ficou totalmente ociosa; usei o DOM disponível.')

            action = command.action
            value = str(command.value or '').strip()
            text = str(command.text or '')

            if action == 'click_selector' and value:
                page.locator(value).first.click(timeout=10_000)
            elif action == 'click_text' and value:
                page.get_by_text(value, exact=False).first.click(timeout=10_000)
            elif action == 'type_selector' and value:
                page.locator(value).first.fill(text, timeout=10_000)
            elif action == 'press':
                page.keyboard.press(value or 'Enter')
            elif action == 'scroll_down':
                page.evaluate('window.scrollBy(0, Math.max(600, window.innerHeight * 0.8))')
            elif action == 'scroll_up':
                page.evaluate('window.scrollBy(0, -Math.max(600, window.innerHeight * 0.8))')
            elif action in {'open', 'snapshot'}:
                pass

            try:
                page.wait_for_load_state('networkidle', timeout=8_000)
            except Exception:
                pass
            page.wait_for_timeout(500)
            snapshot = _snapshot_from_page(page, config=config, url=url, warnings=warnings, meta={'action': action, 'value': value, 'width': config.width, 'height': config.height})
            browser.close()
            return snapshot
    except Exception as exc:
        return RemoteBrowserSnapshot(ok=False, url=url, warnings=warnings, errors=[str(exc) or exc.__class__.__name__])


__all__ = [
    'RemoteBrowserCommand',
    'RemoteBrowserConfig',
    'RemoteBrowserSnapshot',
    'open_remote_browser_snapshot',
    'run_remote_browser_command',
]
