from __future__ import annotations

import json
import re
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import urldefrag, urljoin, urlparse

ProgressCallback = Callable[[dict], None]

DEFAULT_TIMEOUT_MS = 45_000
DEFAULT_WAIT_AFTER_ACTION_MS = 1_800
DEFAULT_MAX_PAGES = 80
DEFAULT_MAX_SITE_PAGES = 1_500
DEFAULT_STATE_DIR = Path('.bling_browser_state')

NEXT_RE = re.compile(
    r'(carregar\s*mais|ver\s*mais|mostrar\s*mais|mais\s*produtos|pr[oó]xima|proxima|next|avan[cç]ar|load\s*more|show\s*more)',
    re.IGNORECASE,
)
BAD_RE = re.compile(r'(voltar|anterior|previous|prev|cancelar|excluir|remover|delete|logout|sair)', re.IGNORECASE)
PRODUCT_HINT_RE = re.compile(r'(produto|produtos|product|products|catalog|catalogo|cat[aá]logo|estoque|inventory|sku|admin/products)', re.IGNORECASE)
BLOCKED_URL_RE = re.compile(r'(logout|sair|delete|destroy|remove|remover|excluir|cancel|cancelar|password|senha|token|revoke)', re.IGNORECASE)
STATIC_ASSET_RE = re.compile(r'\.(?:jpg|jpeg|png|webp|gif|svg|ico|css|js|map|woff|woff2|ttf|eot|pdf|zip|rar|7z|mp4|mp3)(?:\?|$)', re.IGNORECASE)


@dataclass(frozen=True)
class BrowserCaptureConfig:
    supplier_url: str
    supplier_key: str = 'fornecedor'
    state_dir: Path = DEFAULT_STATE_DIR
    headless: bool = True
    max_pages: int = DEFAULT_MAX_PAGES
    max_site_pages: int = DEFAULT_MAX_SITE_PAGES
    wait_after_action_ms: int = DEFAULT_WAIT_AFTER_ACTION_MS
    timeout_ms: int = DEFAULT_TIMEOUT_MS
    same_domain_only: bool = True
    prefer_product_links: bool = True


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


def _html_path(config: BrowserCaptureConfig, suffix: str = '') -> Path:
    ts = time.strftime('%Y%m%d_%H%M%S')
    extra = f'_{_safe_key(suffix)}' if suffix else ''
    return Path(config.state_dir) / f'{_safe_key(config.supplier_key)}{extra}_{ts}.html'


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


def _normalize_url(base_url: str, href: str) -> str:
    href = str(href or '').strip()
    if not href or href.startswith(('javascript:', 'mailto:', 'tel:', 'data:', '#')):
        return ''
    absolute = urljoin(base_url, href)
    absolute, _ = urldefrag(absolute)
    parsed = urlparse(absolute)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        return ''
    return absolute


def _url_allowed(url: str, root_netloc: str, *, same_domain_only: bool = True) -> bool:
    if not url:
        return False
    if STATIC_ASSET_RE.search(url) or BLOCKED_URL_RE.search(url):
        return False
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'}:
        return False
    if same_domain_only and parsed.netloc.lower() != root_netloc.lower():
        return False
    return True


def _url_priority(url: str) -> int:
    score = 0
    lower = url.lower()
    if PRODUCT_HINT_RE.search(lower):
        score += 100
    if '/admin/products' in lower:
        score += 200
    if any(token in lower for token in ('page=', 'draw=', 'start=', 'offset=', 'pagina=')):
        score += 35
    if any(token in lower for token in ('edit', 'create', 'new')):
        score -= 50
    return score


def _escape_attr(value: str) -> str:
    return str(value or '').replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')


def manual_login_and_save_session(config: BrowserCaptureConfig, progress_callback: ProgressCallback | None = None) -> BrowserCaptureResult:
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
                locator.inner_text(timeout=500) if locator.evaluate('el => !!el.innerText') else '',
                locator.get_attribute('value') or '',
                locator.get_attribute('aria-label') or '',
                locator.get_attribute('title') or '',
            ]).strip()
            if label and NEXT_RE.search(label) and not BAD_RE.search(label):
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


def _capture_current_page(page, captured: list[dict[str, str]], seen: set[str], warnings: list[str], config: BrowserCaptureConfig, reason: str) -> bool:
    try:
        page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        page.wait_for_timeout(config.wait_after_action_ms)
        text = page.locator('body').inner_text(timeout=5_000)[:1_200]
        key = f'{page.url}|{text}'
        if key in seen:
            return False
        seen.add(key)
        captured.append({'url': page.url, 'title': page.title(), 'reason': reason, 'html': page.content()})
        return True
    except Exception as exc:
        warnings.append(f'Falha ao capturar página {page.url}: {exc}')
        return False


def _discover_links(page, root_netloc: str, config: BrowserCaptureConfig) -> list[str]:
    try:
        raw_links = page.eval_on_selector_all('a[href]', 'els => els.map(a => a.getAttribute("href") || "").filter(Boolean)')
    except Exception:
        raw_links = []

    links: list[str] = []
    seen: set[str] = set()
    for href in raw_links or []:
        url = _normalize_url(page.url, href)
        if not _url_allowed(url, root_netloc, same_domain_only=config.same_domain_only):
            continue
        if url in seen:
            continue
        seen.add(url)
        links.append(url)
    links.sort(key=_url_priority, reverse=True)
    return links


def _build_combined_html(captured: list[dict[str, str]], title: str) -> str:
    body = [f'<!doctype html><html><head><meta charset="utf-8"><title>{_escape_attr(title)}</title></head><body>']
    body.append(f'<h1>{_escape_attr(title)}</h1><p>Total de páginas/blocos: {len(captured)}</p>')
    for idx, item in enumerate(captured, start=1):
        url = _escape_attr(item.get('url', ''))
        item_title = _escape_attr(item.get('title', ''))
        reason = _escape_attr(item.get('reason', ''))
        html_text = item.get('html', '')
        body.append(f'<section class="bling-captured-page" data-url="{url}" data-reason="{reason}"><h2>Página {idx} - {item_title}</h2><p>URL: {url}</p>{html_text}</section>')
    body.append('</body></html>')
    return '\n'.join(body)


def _open_context(config: BrowserCaptureConfig):
    # Mantido separado apenas para clareza; o contexto ainda é criado dentro do sync_playwright.
    return config


def capture_html_with_saved_session(config: BrowserCaptureConfig, progress_callback: ProgressCallback | None = None) -> BrowserCaptureResult:
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

    html_file = _html_path(config, 'pagina_atual')
    html_file.parent.mkdir(parents=True, exist_ok=True)
    captured: list[dict[str, str]] = []
    seen: set[str] = set()
    warnings: list[str] = []

    try:
        _emit(progress_callback, stage='starting_browser', message='Abrindo navegador Playwright em modo servidor...')
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=config.headless, args=['--disable-blink-features=AutomationControlled'])
            context = browser.new_context(storage_state=str(state_path), viewport={'width': 1366, 'height': 900})
            page = context.new_page()
            page.goto(config.supplier_url, wait_until='domcontentloaded', timeout=config.timeout_ms)
            page.wait_for_timeout(config.wait_after_action_ms)
            _capture_current_page(page, captured, seen, warnings, config, 'inicial')
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
                _capture_current_page(page, captured, seen, warnings, config, 'apos_clique')
                if len(captured) == before_count and page.url == before_url:
                    warnings.append('Clique em próxima/carregar mais não mudou a página. Encerrando captura.')
                    break
            final_url = page.url
            browser.close()

        html_text = _build_combined_html(captured, 'BLING captura Playwright - página atual/paginação')
        html_file.write_text(html_text, encoding='utf-8')
        return BrowserCaptureResult(ok=bool(captured), html=html_text, file_path=str(html_file), pages_captured=len(captured), final_url=final_url, warnings=warnings)
    except Exception as exc:
        return BrowserCaptureResult(ok=False, errors=[str(exc) or exc.__class__.__name__], warnings=warnings)


def capture_entire_site_html_with_saved_session(config: BrowserCaptureConfig, progress_callback: ProgressCallback | None = None) -> BrowserCaptureResult:
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

    start_url = config.supplier_url.strip()
    root_netloc = urlparse(start_url).netloc
    if not root_netloc:
        return BrowserCaptureResult(ok=False, errors=['URL inicial inválida para varredura do site inteiro.'])

    html_file = _html_path(config, 'site_inteiro')
    html_file.parent.mkdir(parents=True, exist_ok=True)

    captured: list[dict[str, str]] = []
    seen_content: set[str] = set()
    visited_urls: set[str] = set()
    queued_urls: set[str] = set()
    warnings: list[str] = []
    queue: deque[str] = deque([start_url])
    queued_urls.add(start_url)
    final_url = start_url

    try:
        _emit(progress_callback, stage='starting_browser', message='Abrindo Playwright para varrer site inteiro...')
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=config.headless, args=['--disable-blink-features=AutomationControlled'])
            context = browser.new_context(storage_state=str(state_path), viewport={'width': 1366, 'height': 900})
            page = context.new_page()

            while queue and len(visited_urls) < max(1, config.max_site_pages):
                url = queue.popleft()
                if url in visited_urls:
                    continue
                if not _url_allowed(url, root_netloc, same_domain_only=config.same_domain_only):
                    continue

                visited_urls.add(url)
                _emit(
                    progress_callback,
                    stage='site_scan',
                    visited=len(visited_urls),
                    queued=len(queue),
                    captured=len(captured),
                    total=config.max_site_pages,
                    url=url,
                    message=f'Varrendo site inteiro: {len(visited_urls)}/{config.max_site_pages} páginas visitadas...',
                )
                try:
                    page.goto(url, wait_until='domcontentloaded', timeout=config.timeout_ms)
                    page.wait_for_timeout(config.wait_after_action_ms)
                    final_url = page.url
                    _capture_current_page(page, captured, seen_content, warnings, config, 'site_scan')

                    discovered = _discover_links(page, root_netloc, config)
                    for link in discovered:
                        if link in visited_urls or link in queued_urls:
                            continue
                        queued_urls.add(link)
                        if config.prefer_product_links and _url_priority(link) > 0:
                            queue.appendleft(link)
                        else:
                            queue.append(link)

                    next_locator = _find_next_locator(page)
                    if next_locator is not None and len(visited_urls) < max(1, config.max_site_pages):
                        before_url = page.url
                        before_count = len(captured)
                        try:
                            next_locator.click(timeout=5_000)
                            page.wait_for_load_state('domcontentloaded', timeout=10_000)
                        except Exception:
                            page.wait_for_timeout(config.wait_after_action_ms)
                        page.wait_for_timeout(config.wait_after_action_ms)
                        final_url = page.url
                        changed = _capture_current_page(page, captured, seen_content, warnings, config, 'site_scan_next_click')
                        if changed and page.url not in visited_urls and _url_allowed(page.url, root_netloc, same_domain_only=config.same_domain_only):
                            visited_urls.add(page.url)
                        if len(captured) == before_count and page.url == before_url:
                            warnings.append(f'Botão próxima/carregar mais não alterou conteúdo em {url}.')
                except Exception as exc:
                    warnings.append(f'Falha ao visitar {url}: {exc}')
                    continue

            if queue:
                warnings.append(f'Varredura encerrada pelo limite max_site_pages={config.max_site_pages}. Ainda havia {len(queue)} link(s) na fila.')
            browser.close()

        html_text = _build_combined_html(captured, 'BLING captura Playwright - SITE INTEIRO')
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
        'max_pages': config.max_pages,
        'max_site_pages': config.max_site_pages,
        'same_domain_only': config.same_domain_only,
        'prefer_product_links': config.prefer_product_links,
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
    'capture_entire_site_html_with_saved_session',
    'capture_html_with_saved_session',
    'has_saved_session',
    'is_playwright_available',
    'manual_login_and_save_session',
    'session_debug',
]
