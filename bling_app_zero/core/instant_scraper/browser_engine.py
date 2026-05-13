from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd

from .card_detector import detect_cards_from_html
from .pagination_detector import detect_next_links, next_button_locators
from .preview_mapper import align_rows_to_requested_columns
from .table_detector import detect_tables_from_html, flatten_detected_tables

DEFAULT_BROWSER_STATE_DIR = Path('.streamlit') / 'browser_state'


@dataclass
class BrowserScraperConfig:
    operation: str = 'cadastro'
    entry_url: str = ''
    start_urls: list[str] = field(default_factory=list)
    model_columns: list[object] | pd.DataFrame | None = None
    max_pages: int = 25
    max_products: int = 300
    allow_entry_step: bool = False
    security_resolved: bool = False
    user_value: str = ''
    session_value: str = ''
    persist_state: bool = True
    state_namespace: str = 'supplier_browser'


@dataclass
class BrowserScraperResult:
    ok: bool
    df: pd.DataFrame = field(default_factory=pd.DataFrame)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    pages_visited: int = 0
    state_reused: bool = False
    state_saved: bool = False


def _valid_url(value: str) -> bool:
    try:
        parsed = urlparse(str(value or '').strip())
    except Exception:
        return False
    return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)


def _domain_for_state(config: BrowserScraperConfig) -> str:
    for value in [config.entry_url, *(config.start_urls or [])]:
        try:
            parsed = urlparse(str(value or '').strip())
        except Exception:
            continue
        if parsed.netloc:
            return parsed.netloc.lower()
    return 'unknown-domain'


def _state_path(config: BrowserScraperConfig) -> Path:
    domain = _domain_for_state(config)
    namespace = str(config.state_namespace or 'supplier_browser').strip() or 'supplier_browser'
    digest = hashlib.sha256(f'{namespace}:{domain}'.encode('utf-8', errors='ignore')).hexdigest()[:18]
    return DEFAULT_BROWSER_STATE_DIR / f'{namespace}_{digest}.json'


def _safe_error(exc: BaseException | str) -> str:
    text = str(exc or '').strip()
    blocked_terms = ('senha', 'password', 'token', 'secret', 'authorization', 'captcha', '2fa')
    if any(term in text.lower() for term in blocked_terms):
        return 'Erro protegido: a mensagem técnica continha dado sensível e foi ocultada.'
    return text[:500] or 'Erro desconhecido no navegador autenticado.'


def _chromium_executable() -> str | None:
    for command in ('chromium-browser', 'chromium', 'google-chrome', 'google-chrome-stable'):
        path = shutil.which(command)
        if path:
            return path
    return None


def _launch_chromium(playwright):
    executable_path = _chromium_executable()
    launch_args = ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
    if executable_path:
        return playwright.chromium.launch(headless=True, executable_path=executable_path, args=launch_args)
    return playwright.chromium.launch(headless=True, args=launch_args)


def _new_context(browser, config: BrowserScraperConfig) -> tuple[Any, bool]:
    context_kwargs: dict[str, Any] = {
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36',
        'locale': 'pt-BR',
        'viewport': {'width': 1366, 'height': 900},
    }
    state_file = _state_path(config)
    reused = False
    if config.persist_state and state_file.exists():
        context_kwargs['storage_state'] = str(state_file)
        reused = True
    return browser.new_context(**context_kwargs), reused


def _save_context_state(context, config: BrowserScraperConfig) -> bool:
    if not config.persist_state:
        return False
    try:
        state_file = _state_path(config)
        state_file.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(state_file))
        return True
    except Exception:
        return False


def _extract_rows_from_html(html: str, url: str) -> list[dict[str, Any]]:
    table_rows = flatten_detected_tables(detect_tables_from_html(html))
    card_rows = detect_cards_from_html(html, url)
    rows = card_rows or table_rows
    if card_rows and table_rows:
        rows = card_rows + table_rows
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        signature = '|'.join(str(row.get(key, '')) for key in sorted(row.keys()))
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(row)
    return deduped


def _try_entry_step(page, config: BrowserScraperConfig) -> list[str]:
    warnings: list[str] = []
    if not config.allow_entry_step:
        return warnings
    warnings.append('Entrada automática por campos externos está em modo legado. O fluxo recomendado é login no navegador do fornecedor.')
    if not config.entry_url:
        warnings.append('Entrada guiada marcada, mas nenhuma URL foi configurada.')
        return warnings
    page.goto(config.entry_url, wait_until='domcontentloaded', timeout=45000)
    page.wait_for_timeout(1500)
    if config.user_value:
        for selector in ["input[type='email']", "input[name*='email' i]", "input[name*='user' i]", "input[name*='login' i]", "input[type='text']"]:
            try:
                locator = page.locator(selector).first
                if locator.count():
                    locator.fill(config.user_value, timeout=2500)
                    break
            except Exception:
                pass
    if config.session_value:
        try:
            page.locator("input[type='password']").first.fill(config.session_value, timeout=3500)
        except Exception:
            warnings.append('Campo protegido não foi encontrado automaticamente.')
    submitted = False
    for selector in ["button[type='submit']", "input[type='submit']", "button:has-text('Entrar')", "button:has-text('Acessar')", "button:has-text('Login')", "button:has-text('Sign in')"]:
        try:
            locator = page.locator(selector).first
            if locator.count():
                locator.click(timeout=3500)
                submitted = True
                break
        except Exception:
            pass
    if submitted:
        page.wait_for_timeout(3500)
    else:
        warnings.append('Botão de entrada não foi encontrado automaticamente.')
    html = page.content().lower()
    if any(term in html for term in ('captcha', 'recaptcha', 'hcaptcha', 'verification code', 'código de verificação')):
        warnings.append('O site parece exigir verificação humana. Resolva manualmente; o sistema não deve burlar essa proteção.')
    return warnings


def _queue_after_entry(page, config: BrowserScraperConfig, start_urls: list[str]) -> list[str]:
    queue: list[str] = []
    current_url = str(getattr(page, 'url', '') or '').strip()
    entry_url = str(config.entry_url or '').strip()
    if _valid_url(current_url):
        queue.append(current_url)
    for url in start_urls:
        clean = str(url or '').strip()
        if not _valid_url(clean):
            continue
        if config.allow_entry_step and entry_url and clean.rstrip('/') == entry_url.rstrip('/') and current_url and current_url.rstrip('/') != entry_url.rstrip('/'):
            continue
        if clean not in queue:
            queue.append(clean)
    return queue


def _scroll_page(page) -> None:
    for _ in range(8):
        try:
            page.mouse.wheel(0, 1600)
            page.wait_for_timeout(700)
        except Exception:
            break


def _click_next_if_possible(page) -> bool:
    for selector in next_button_locators():
        try:
            locator = page.locator(selector).first
            if locator.count() and locator.is_enabled(timeout=1000):
                locator.click(timeout=2500)
                page.wait_for_timeout(1800)
                return True
        except Exception:
            continue
    return False


def run_browser_scraper(config: BrowserScraperConfig) -> BrowserScraperResult:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return BrowserScraperResult(ok=False, errors=['Playwright não está disponível neste ambiente. Ative o navegador para usar a captura autenticada estilo Instant Scraper.'])
    start_urls = [url for url in config.start_urls if _valid_url(url)]
    if not start_urls and _valid_url(config.entry_url):
        start_urls = [config.entry_url]
    if not start_urls:
        return BrowserScraperResult(ok=False, errors=['Nenhuma URL válida informada para a captura estilo Instant Scraper.'])
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []
    visited: set[str] = set()
    browser = None
    context = None
    state_reused = False
    state_saved = False
    try:
        with sync_playwright() as p:
            browser = _launch_chromium(p)
            context, state_reused = _new_context(browser, config)
            if state_reused:
                warnings.append('Estado anterior do navegador reutilizado para este fornecedor.')
            page = context.new_page()
            if config.allow_entry_step:
                warnings.extend(_try_entry_step(page, config))
            queue = _queue_after_entry(page, config, start_urls)
            while queue and len(visited) < max(1, config.max_pages) and len(rows) < max(1, config.max_products):
                url = queue.pop(0)
                if url in visited:
                    continue
                visited.add(url)
                if str(getattr(page, 'url', '') or '').rstrip('/') != str(url or '').rstrip('/'):
                    page.goto(url, wait_until='domcontentloaded', timeout=60000)
                page.wait_for_timeout(1800)
                _scroll_page(page)
                html = page.content()
                rows.extend(_extract_rows_from_html(html, page.url))
                for next_url in detect_next_links(html, page.url):
                    if next_url not in visited and next_url not in queue:
                        queue.append(next_url)
                if len(rows) < config.max_products and _click_next_if_possible(page):
                    rows.extend(_extract_rows_from_html(page.content(), page.url))
                rows = rows[: config.max_products]
            if context is not None:
                state_saved = _save_context_state(context, config)
                if state_saved:
                    warnings.append('Estado do navegador salvo para reutilização neste fornecedor.')
    except Exception as exc:
        errors.append(_safe_error(exc))
    finally:
        try:
            if context is not None:
                context.close()
        except Exception:
            pass
        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass
    df = align_rows_to_requested_columns(rows, config.model_columns, operation=config.operation)
    return BrowserScraperResult(ok=not df.empty and not errors, df=df, errors=errors, warnings=warnings, pages_visited=len(visited), state_reused=state_reused, state_saved=state_saved)
