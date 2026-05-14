from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ProgressCallback = Callable[[dict], None]

DEFAULT_TIMEOUT_MS = 45_000
DEFAULT_WAIT_AFTER_ACTION_MS = 1_800
DEFAULT_MAX_PAGES = 80
DEFAULT_STATE_DIR = Path('.bling_browser_state')

NEXT_RE = re.compile(
    r'(carregar\s*mais|ver\s*mais|mostrar\s*mais|mais\s*produtos|pr[oó]xima|proxima|next|avan[cç]ar|load\s*more|show\s*more)',
    re.IGNORECASE,
)
BAD_RE = re.compile(r'(voltar|anterior|previous|prev|cancelar|excluir|remover|delete|logout|sair)', re.IGNORECASE)


@dataclass(frozen=True)
class BrowserCaptureConfig:
    supplier_url: str
    supplier_key: str = 'fornecedor'
    state_dir: Path = DEFAULT_STATE_DIR
    headless: bool = True
    max_pages: int = DEFAULT_MAX_PAGES
    wait_after_action_ms: int = DEFAULT_WAIT_AFTER_ACTION_MS
    timeout_ms: int = DEFAULT_TIMEOUT_MS


@dataclass
class BrowserCaptureResult:
    ok: bool
    html: str = ''
    file_path: str = ''
    pages_captured: int = 0
    final_url: str = ''
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _safe_key(value: str) -> str:
    text = re.sub(r'[^a-zA-Z0-9_.-]+', '_', str(value or 'fornecedor')).strip('._-')
    return text[:80] or 'fornecedor'


def _state_path(config: BrowserCaptureConfig) -> Path:
    return Path(config.state_dir) / f'{_safe_key(config.supplier_key)}.json'


def _html_path(config: BrowserCaptureConfig) -> Path:
    ts = time.strftime('%Y%m%d_%H%M%S')
    return Path(config.state_dir) / f'{_safe_key(config.supplier_key)}_{ts}.html'


def _emit(callback: ProgressCallback | None, **payload: object) -> None:
    if callback is not None:
        try:
            callback(dict(payload))
        except Exception:
            pass


def is_playwright_available() -> tuple[bool, str]:
    try:
        import playwright  # noqa: F401
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True, ''
    except Exception as exc:
        return False, str(exc) or exc.__class__.__name__


def has_saved_session(config: BrowserCaptureConfig) -> bool:
    path = _state_path(config)
    return path.exists() and path.stat().st_size > 20


def manual_login_and_save_session(config: BrowserCaptureConfig, progress_callback: ProgressCallback | None = None) -> BrowserCaptureResult:
    """Abre navegador visível para login manual e salva storage_state.

    Uso recomendado em máquina local/VPS com interface gráfica. Em Streamlit Cloud,
    navegador headed pode não estar disponível. Esta função não burla CAPTCHA: o usuário
    precisa resolver manualmente no navegador aberto.
    """
    available, error = is_playwright_available()
    if not available:
        return BrowserCaptureResult(ok=False, errors=[f'Playwright indisponível: {error}'])

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return BrowserCaptureResult(ok=False, errors=[str(exc) or exc.__class__.__name__])

    state_path = _state_path(config)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        _emit(progress_callback, stage='starting_browser', message='Abrindo navegador para login manual...')
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
            context = browser.new_context(viewport={'width': 1366, 'height': 900})
            page = context.new_page()
            page.goto(config.supplier_url, wait_until='domcontentloaded', timeout=config.timeout_ms)
            _emit(progress_callback, stage='manual_login', message='Faça login manualmente no navegador aberto. Resolva CAPTCHA se aparecer.')
            input('Depois de fazer login e abrir a página de produtos, pressione ENTER aqui para salvar a sessão...')
            context.storage_state(path=str(state_path))
            final_url = page.url
            browser.close()
        return BrowserCaptureResult(ok=True, file_path=str(state_path), final_url=final_url)
    except Exception as exc:
        return BrowserCaptureResult(ok=False, errors=[str(exc) or exc.__class__.__name__])


def _find_next_locator(page):
    candidates = page.locator('button, a, [role="button"], input[type="button"], input[type="submit"]')
    count = min(candidates.count(), 300)
    for idx in range(count):
        locator = candidates.nth(idx)
        try:
            if not locator.is_visible() or not locator.is_enabled():
                continue
            label = ' '.join([
                locator.inner_text(timeout=500) if locator.evaluate("el => !!el.innerText") else '',
                locator.get_attribute('value') or '',
                locator.get_attribute('aria-label') or '',
                locator.get_attribute('title') or '',
            ]).strip()
            if not label:
                continue
            if NEXT_RE.search(label) and not BAD_RE.search(label):
                return locator
        except Exception:
            continue
    try:
        rel_next = page.locator('a[rel="next"]').first
        if rel_next.is_visible() and rel_next.is_enabled():
            return rel_next
    except Exception:
        pass
    return None


def capture_html_with_saved_session(config: BrowserCaptureConfig, progress_callback: ProgressCallback | None = None) -> BrowserCaptureResult:
    """Captura HTML usando storage_state salvo anteriormente.

    Tenta visitar a URL, rolar, capturar HTML, clicar em próxima/carregar mais
    e consolidar as páginas em um único HTML.
    """
    available, error = is_playwright_available()
    if not available:
        return BrowserCaptureResult(ok=False, errors=[f'Playwright indisponível: {error}'])

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return BrowserCaptureResult(ok=False, errors=[str(exc) or exc.__class__.__name__])

    state_path = _state_path(config)
    if not state_path.exists():
        return BrowserCaptureResult(ok=False, errors=['Sessão salva não encontrada. Faça o login manual primeiro.'])

    html_file = _html_path(config)
    html_file.parent.mkdir(parents=True, exist_ok=True)
    captured: list[dict[str, str]] = []
    seen: set[str] = set()
    warnings: list[str] = []

    def capture_page(page, reason: str) -> bool:
        try:
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            page.wait_for_timeout(config.wait_after_action_ms)
            text = page.locator('body').inner_text(timeout=5_000)[:900]
            key = f'{page.url}|{text}'
            if key in seen:
                return False
            seen.add(key)
            captured.append({'url': page.url, 'title': page.title(), 'reason': reason, 'html': page.content()})
            return True
        except Exception as exc:
            warnings.append(f'Falha ao capturar página: {exc}')
            return False

    try:
        _emit(progress_callback, stage='starting_browser', message='Abrindo navegador Playwright em modo servidor...')
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=config.headless, args=['--disable-blink-features=AutomationControlled'])
            context = browser.new_context(storage_state=str(state_path), viewport={'width': 1366, 'height': 900})
            page = context.new_page()
            page.goto(config.supplier_url, wait_until='domcontentloaded', timeout=config.timeout_ms)
            page.wait_for_timeout(config.wait_after_action_ms)
            capture_page(page, 'inicial')
            for idx in range(1, max(1, config.max_pages)):
                _emit(progress_callback, stage='capturing', page=idx, total=config.max_pages, message=f'Capturando página {idx} de até {config.max_pages}...')
                next_locator = _find_next_locator(page)
                if next_locator is None:
                    warnings.append('Não encontrei botão Próxima/Carregar mais. Capturei até a página atual.')
                    break
                before_url = page.url
                before_count = len(captured)
                try:
                    next_locator.click(timeout=5_000)
                    page.wait_for_load_state('domcontentloaded', timeout=10_000)
                except Exception:
                    page.wait_for_timeout(config.wait_after_action_ms)
                page.wait_for_timeout(config.wait_after_action_ms)
                capture_page(page, 'apos_clique')
                if len(captured) == before_count and page.url == before_url:
                    warnings.append('Clique em próxima/carregar mais não mudou a página. Encerrando captura.')
                    break
            final_url = page.url
            browser.close()

        body = ['<!doctype html><html><head><meta charset="utf-8"><title>BLING captura Playwright</title></head><body>']
        body.append(f'<h1>BLING captura Playwright</h1><p>Total de páginas/blocos: {len(captured)}</p>')
        for idx, item in enumerate(captured, start=1):
            body.append(f'<section class="bling-captured-page" data-url="{item["url"]}"><h2>Página {idx} - {item["title"]}</h2><p>URL: {item["url"]}</p>{item["html"]}</section>')
        body.append('</body></html>')
        html_text = '\n'.join(body)
        html_file.write_text(html_text, encoding='utf-8')
        return BrowserCaptureResult(ok=bool(captured), html=html_text, file_path=str(html_file), pages_captured=len(captured), final_url=final_url, warnings=warnings)
    except Exception as exc:
        return BrowserCaptureResult(ok=False, errors=[str(exc) or exc.__class__.__name__], warnings=warnings)


def session_debug(config: BrowserCaptureConfig) -> dict[str, object]:
    state_path = _state_path(config)
    data: dict[str, object] = {
        'supplier_url': config.supplier_url,
        'supplier_key': config.supplier_key,
        'state_path': str(state_path),
        'has_saved_session': state_path.exists(),
    }
    if state_path.exists():
        try:
            parsed = json.loads(state_path.read_text(encoding='utf-8'))
            data['cookies'] = len(parsed.get('cookies', []))
            data['origins'] = len(parsed.get('origins', []))
        except Exception:
            data['cookies'] = 'erro_ao_ler'
    return data


__all__ = [
    'BrowserCaptureConfig',
    'BrowserCaptureResult',
    'capture_html_with_saved_session',
    'has_saved_session',
    'is_playwright_available',
    'manual_login_and_save_session',
    'session_debug',
]
