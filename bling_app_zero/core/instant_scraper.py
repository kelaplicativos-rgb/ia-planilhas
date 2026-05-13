from __future__ import annotations

from dataclasses import dataclass, field
from shutil import which
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup


@dataclass
class BrowserScraperConfig:
    operation: str = 'cadastro'
    entry_url: str = ''
    start_urls: list[str] = field(default_factory=list)
    model_columns: list[str] | None = None
    max_pages: int = 25
    max_products: int = 300
    allow_entry_step: bool = False
    security_resolved: bool = True
    persist_state: bool = True
    state_namespace: str = 'supplier_browser'
    headless: bool = True
    timeout_ms: int = 45_000


@dataclass
class BrowserScraperResult:
    df: pd.DataFrame
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    pages_visited: int = 0
    state_reused: bool = False
    state_saved: bool = False
    raw_blocks: list[dict[str, Any]] = field(default_factory=list)


def _chromium_executable() -> str | None:
    for candidate in ('chromium', 'chromium-browser', 'google-chrome', 'google-chrome-stable'):
        path = which(candidate)
        if path:
            return path
    return None


def _clean(value: object) -> str:
    return ' '.join(str(value or '').replace('\xa0', ' ').split()).strip()


def _looks_like_product(text: str) -> bool:
    lower = text.lower()
    signals = (
        'r$', 'preço', 'preco', 'valor', 'sku', 'cód', 'cod', 'ref', 'referência',
        'estoque', 'saldo', 'quantidade', 'produto', 'comprar', 'indisponível', 'indisponivel',
    )
    return len(text) >= 12 and any(signal in lower for signal in signals)


def _score_text(text: str) -> int:
    lower = text.lower()
    score = 0
    for token in ('r$', 'preço', 'preco', 'sku', 'cód', 'cod', 'estoque', 'produto'):
        if token in lower:
            score += 3
    score += min(len(text) // 80, 8)
    return score


def _extract_tables(soup: BeautifulSoup) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for table_index, table in enumerate(soup.find_all('table'), start=1):
        rows: list[list[str]] = []
        for tr in table.find_all('tr'):
            cells = tr.find_all(['th', 'td'])
            row = [_clean(cell.get_text(' ', strip=True)) for cell in cells]
            if any(row):
                rows.append(row)
        if len(rows) < 2:
            continue
        header = rows[0]
        width = max(len(row) for row in rows)
        header = header + [f'Coluna {idx + 1}' for idx in range(len(header), width)]
        for row_index, row in enumerate(rows[1:], start=1):
            normalized = row + [''] * (width - len(row))
            data = {str(header[idx] or f'Coluna {idx + 1}'): normalized[idx] for idx in range(width)}
            text = ' | '.join(normalized)
            if _looks_like_product(text):
                data.setdefault('Texto capturado', text)
                data.setdefault('Origem captura', f'tabela_{table_index}_linha_{row_index}')
                blocks.append(data)
    return blocks


def _extract_cards(soup: BeautifulSoup) -> list[dict[str, Any]]:
    selectors = [
        '[class*=produto]', '[class*=product]', '[class*=item]', '[class*=card]',
        '[class*=linha]', '[class*=row]', '[data-product]', '[data-produto]',
        '[data-sku]', '[data-id]', 'article', 'li', '.MuiDataGrid-row', '.ant-table-row',
    ]
    blocks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for selector in selectors:
        for index, node in enumerate(soup.select(selector), start=1):
            text = _clean(node.get_text(' ', strip=True))
            if not _looks_like_product(text):
                continue
            key = text[:500]
            if key in seen:
                continue
            seen.add(key)
            attrs = dict(node.attrs) if hasattr(node, 'attrs') else {}
            image = node.find('img')
            link = node.find('a')
            blocks.append(
                {
                    'Texto capturado': text[:1500],
                    'Origem captura': f'{selector}_{index}',
                    'Código/SKU': _clean(attrs.get('data-sku') or attrs.get('data-id') or attrs.get('id') or ''),
                    'Imagem URL': _clean(image.get('src') or image.get('data-src') or '') if image else '',
                    'URL': _clean(link.get('href') or '') if link else '',
                    '_score': _score_text(text),
                }
            )
    blocks.sort(key=lambda item: int(item.get('_score') or 0), reverse=True)
    for block in blocks:
        block.pop('_score', None)
    return blocks


def _blocks_to_df(blocks: list[dict[str, Any]], max_products: int) -> pd.DataFrame:
    if not blocks:
        return pd.DataFrame()
    df = pd.DataFrame(blocks[:max_products]).fillna('').astype(str)
    useful_cols = [col for col in df.columns if not str(col).startswith('_')]
    return df[useful_cols]


def _extract_blocks_from_html(html: str, max_products: int) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    soup = BeautifulSoup(html or '', 'html.parser')
    for tag in soup(['script', 'style', 'noscript', 'svg']):
        tag.decompose()
    blocks = _extract_tables(soup)
    if not blocks:
        blocks = _extract_cards(soup)
    return _blocks_to_df(blocks, max_products), blocks


def _apply_model_columns(df: pd.DataFrame, model_columns: list[str] | None) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty or not model_columns:
        return df
    requested = [str(col) for col in model_columns if str(col).strip()]
    if not requested:
        return df
    out = pd.DataFrame()
    lower_map = {str(col).strip().lower(): col for col in df.columns}
    for target in requested:
        key = target.strip().lower()
        if key in lower_map:
            out[target] = df[lower_map[key]]
        elif 'descri' in key or 'produto' in key or 'nome' in key:
            out[target] = df.get('Texto capturado', '')
        elif 'código' in key or 'codigo' in key or 'sku' in key or 'ref' in key:
            out[target] = df.get('Código/SKU', '')
        elif 'imagem' in key or 'foto' in key:
            out[target] = df.get('Imagem URL', '')
        elif 'url' in key or 'link' in key:
            out[target] = df.get('URL', '')
        else:
            out[target] = ''
    out['Texto capturado'] = df.get('Texto capturado', '')
    out['Origem captura'] = df.get('Origem captura', '')
    return out.fillna('').astype(str)


def run_browser_scraper(config: BrowserScraperConfig) -> BrowserScraperResult:
    """Executa captura DOM em navegador real Playwright/Chromium.

    Este motor não usa iframe do Streamlit nem a aba externa do celular. Ele abre um
    Chromium no ambiente do app, carrega a URL preparada e extrai tabelas/cards do
    DOM renderizado, em estilo Instant Data Scraper.
    """
    warnings: list[str] = []
    errors: list[str] = []
    entry_url = _clean(config.entry_url or (config.start_urls[0] if config.start_urls else ''))
    if not entry_url.startswith(('http://', 'https://')):
        return BrowserScraperResult(df=pd.DataFrame(), errors=['URL de entrada inválida para o navegador real.'])

    executable = _chromium_executable()
    if not executable:
        warnings.append('Chromium do sistema não foi encontrado. Tentando navegador instalado pelo Playwright.')

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return BrowserScraperResult(df=pd.DataFrame(), errors=[f'Playwright indisponível: {exc}'], warnings=warnings)

    page_html = ''
    pages_visited = 0
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
                viewport={'width': 1366, 'height': 900},
                user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36',
                locale='pt-BR',
            )
            page = context.new_page()
            page.goto(entry_url, wait_until='domcontentloaded', timeout=config.timeout_ms)
            pages_visited = 1
            try:
                page.wait_for_load_state('networkidle', timeout=min(config.timeout_ms, 15_000))
            except Exception:
                warnings.append('A página não ficou totalmente ociosa; capturei o DOM disponível.')
            try:
                page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                page.wait_for_timeout(1200)
                page.evaluate('window.scrollTo(0, 0)')
            except Exception:
                pass
            page_html = page.content()
            try:
                context.storage_state(path=f'/tmp/{config.state_namespace}_state.json')
            except Exception:
                pass
            browser.close()
    except Exception as exc:
        return BrowserScraperResult(df=pd.DataFrame(), errors=[str(exc) or exc.__class__.__name__], warnings=warnings, pages_visited=pages_visited)

    df, blocks = _extract_blocks_from_html(page_html, config.max_products)
    if isinstance(df, pd.DataFrame) and not df.empty:
        df = _apply_model_columns(df, config.model_columns)
    else:
        warnings.append('Nenhum bloco/tabela de produto foi detectado no DOM renderizado.')
    return BrowserScraperResult(
        df=df,
        warnings=warnings,
        errors=[],
        pages_visited=pages_visited,
        state_reused=False,
        state_saved=True,
        raw_blocks=blocks,
    )


__all__ = ['BrowserScraperConfig', 'BrowserScraperResult', 'run_browser_scraper']
