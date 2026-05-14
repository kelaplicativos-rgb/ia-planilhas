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
    width: int = 1600
    height: int = 1000


@dataclass
class RemoteBrowserCommand:
    action: Literal[
        'open',
        'click_selector',
        'click_text',
        'click_xy',
        'type_selector',
        'type_smart',
        'click_smart',
        'press',
        'scroll_down',
        'scroll_up',
        'snapshot',
    ]
    value: str = ''
    text: str = ''
    x: int | None = None
    y: int | None = None


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


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value).replace(',', '.')))
    except Exception:
        return default


def _smart_selectors(kind: str) -> list[str]:
    normalized = str(kind or '').strip().lower()
    if normalized in {'user', 'usuario', 'email', 'login'}:
        return [
            'input[type="email"]',
            'input[name*="email" i]',
            'input[id*="email" i]',
            'input[name*="login" i]',
            'input[id*="login" i]',
            'input[name*="user" i]',
            'input[id*="user" i]',
            'input[name*="usuario" i]',
            'input[id*="usuario" i]',
            'input[type="text"]',
        ]
    if normalized in {'password', 'senha'}:
        return [
            'input[type="password"]',
            'input[name*="senha" i]',
            'input[id*="senha" i]',
            'input[name*="password" i]',
            'input[id*="password" i]',
        ]
    if normalized in {'search', 'busca', 'produto', 'products'}:
        return [
            'input[type="search"]',
            'input[name*="search" i]',
            'input[id*="search" i]',
            'input[placeholder*="buscar" i]',
            'input[placeholder*="pesquisar" i]',
            'input[placeholder*="produto" i]',
            'input[name*="busca" i]',
            'input[id*="busca" i]',
            'input[type="text"]',
        ]
    return [
        'input:visible',
        'textarea:visible',
        '[contenteditable="true"]',
    ]


def _smart_click_texts(kind: str) -> list[str]:
    normalized = str(kind or '').strip().lower()
    if normalized in {'login', 'entrar', 'submit'}:
        return ['Entrar', 'Login', 'Acessar', 'Continuar', 'Enviar']
    if normalized in {'produtos', 'products', 'catalogo', 'catálogo'}:
        return ['Produtos', 'Produto', 'Catálogo', 'Catalogo', 'Estoque', 'Itens']
    if normalized in {'next', 'proximo', 'próximo'}:
        return ['Próximo', 'Proximo', 'Avançar', 'Avancar', 'Next', '>']
    if normalized in {'search', 'buscar', 'pesquisar'}:
        return ['Buscar', 'Pesquisar', 'Filtrar', 'Procurar']
    return [kind]


def _fill_first_available(page, selectors: list[str], text: str) -> bool:
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() <= 0:
                continue
            locator.fill(text, timeout=3_000)
            return True
        except Exception:
            continue
    return False


def _click_first_text(page, texts: list[str]) -> bool:
    for text in texts:
        try:
            page.get_by_text(text, exact=False).first.click(timeout=4_000)
            return True
        except Exception:
            continue
    return False


def run_remote_browser_command(config: RemoteBrowserConfig, command: RemoteBrowserCommand) -> RemoteBrowserSnapshot:
    """Executa um comando no Chromium real do servidor e devolve novo snapshot."""
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
            elif action == 'click_xy':
                x = max(0, min(_safe_int(command.x), int(config.width) - 1))
                y = max(0, min(_safe_int(command.y), int(config.height) - 1))
                page.mouse.click(x, y)
            elif action == 'type_selector' and value:
                page.locator(value).first.fill(text, timeout=10_000)
            elif action == 'type_smart':
                if not _fill_first_available(page, _smart_selectors(value), text):
                    warnings.append(f'Não encontrei um campo compatível para preencher: {value}.')
            elif action == 'click_smart':
                if not _click_first_text(page, _smart_click_texts(value)):
                    warnings.append(f'Não encontrei botão/link compatível para clicar: {value}.')
            elif action == 'press':
                page.keyboard.press(value or 'Enter')
            elif action == 'scroll_down':
                page.evaluate('window.scrollBy(0, Math.max(700, window.innerHeight * 0.85))')
            elif action == 'scroll_up':
                page.evaluate('window.scrollBy(0, -Math.max(700, window.innerHeight * 0.85))')
            elif action in {'open', 'snapshot'}:
                pass

            try:
                page.wait_for_load_state('networkidle', timeout=8_000)
            except Exception:
                pass
            page.wait_for_timeout(600)
            snapshot = _snapshot_from_page(
                page,
                config=config,
                url=url,
                warnings=warnings,
                meta={'action': action, 'value': value, 'x': command.x, 'y': command.y, 'width': config.width, 'height': config.height},
            )
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
