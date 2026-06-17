from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.text import clean_cell
from bling_app_zero.engines.fast_site_scraper.constants import (
    SITE_ENRICH_MAX_ROWS,
    SITE_ENRICH_WORKERS,
    SITE_PLAYWRIGHT_FALLBACK_MAX,
)
from bling_app_zero.pipelines.site_pipeline import run_pipeline as _base_run_pipeline

RESPONSIBLE_FILE = 'bling_app_zero/pipelines/site_pipeline_blingfix.py'
PAGE_TIMEOUT = 12
PLAYWRIGHT_TIMEOUT_MS = 18_000
PLAYWRIGHT_WAIT_MS = 1_500
# BLINGFIX SITE 2026-06-16:
# Antes o reforco parava em 180 linhas. Em capturas reais o motor pode achar
# 300, 600 ou 1200 produtos; portanto o reforco agora acompanha o limite do
# fluxo e trabalha em lote, sem abrir Playwright para todos os itens.
MAX_ROWS = SITE_ENRICH_MAX_ROWS
MAX_WORKERS = SITE_ENRICH_WORKERS
PLAYWRIGHT_FALLBACK_MAX = SITE_PLAYWRIGHT_FALLBACK_MAX
IMAGE_COLUMNS = ('imagens', 'imagem', 'url_imagens', 'url imagem', 'fotos', 'foto')
TITLE_COLUMNS = ('nome', 'produto', 'titulo', 'título', 'descricao produto', 'descrição produto')
DESC_COLUMNS = ('descricao', 'descrição', 'descricao curta', 'descrição curta', 'descricao_complementar', 'descrição_complementar', 'detalhes')
URL_COLUMNS = ('url', 'link', 'produto_url', 'url_produto', 'origem url', 'link produto')
BLOCKED_IMAGE_TERMS = ('logo', 'favicon', 'placeholder', 'sem-imagem', 'semimagem', 'no-image', 'sprite', 'icon', 'whatsapp', 'instagram', 'facebook')


def _key(value: object) -> str:
    text = str(value or '').strip().lower()
    text = text.replace('ã', 'a').replace('á', 'a').replace('à', 'a').replace('â', 'a')
    text = text.replace('é', 'e').replace('ê', 'e').replace('í', 'i')
    text = text.replace('ó', 'o').replace('ô', 'o').replace('õ', 'o').replace('ú', 'u').replace('ç', 'c')
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _find_col(df: pd.DataFrame, aliases: tuple[str, ...]) -> str:
    alias_keys = [_key(alias) for alias in aliases]
    for column in df.columns:
        col_key = _key(column)
        if any(alias == col_key or alias in col_key for alias in alias_keys):
            return str(column)
    return ''


def _ensure_col(df: pd.DataFrame, preferred: str, aliases: tuple[str, ...]) -> str:
    existing = _find_col(df, aliases)
    if existing:
        return existing
    df[preferred] = ''
    return preferred


def _domain(value: str) -> str:
    try:
        return urlparse(str(value or '')).netloc.lower().replace('www.', '')
    except Exception:
        return ''


def _input_public_domains(raw_urls: str) -> set[str]:
    domains: set[str] = set()
    for item in re.split(r'[\n,;]+', str(raw_urls or '')):
        item = item.strip()
        if not item.startswith(('http://', 'https://')):
            continue
        host = _domain(item)
        if host:
            domains.add(host)
    return domains


def _same_public_domain(url: str, allowed_domains: set[str]) -> bool:
    host = _domain(url)
    if not host:
        return False
    return any(host == domain or host.endswith('.' + domain) for domain in allowed_domains)


def _filter_live_origin_rows(df: pd.DataFrame, raw_urls: str) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df

    allowed_domains = _input_public_domains(raw_urls)
    if not allowed_domains:
        return df.iloc[0:0].copy()

    out = df.copy().fillna('')
    url_col = _find_col(out, URL_COLUMNS)
    if not url_col:
        add_audit_event(
            'site_pipeline_live_origin_blocked_without_url',
            area='SITE',
            status='BLOQUEADO',
            details={
                'rows_before': len(out),
                'reason': 'Resultado de busca por site sem coluna de URL pública.',
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return out.iloc[0:0].copy()

    before = len(out)
    out = out[out[url_col].map(lambda value: _same_public_domain(clean_cell(value), allowed_domains))].copy()
    removed = before - len(out)
    if removed:
        add_audit_event(
            'site_pipeline_live_origin_rows_removed',
            area='SITE',
            status='AVISO',
            details={
                'rows_before': before,
                'rows_after': len(out),
                'removed': removed,
                'url_column': url_col,
                'allowed_domains': sorted(allowed_domains),
                'reason': 'Linhas removidas por não pertencerem ao domínio público informado.',
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
    return out.fillna('')


def _jsonld_objects(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        out = [value]
        graph = value.get('@graph')
        if isinstance(graph, list):
            for item in graph:
                out.extend(_jsonld_objects(item))
        return out
    if isinstance(value, list):
        out: list[dict[str, Any]] = []
        for item in value:
            out.extend(_jsonld_objects(item))
        return out
    return []


def _extract_jsonld_product(html: str) -> dict[str, Any]:
    for script in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', str(html or ''), flags=re.I | re.S):
        try:
            data = json.loads(unescape(script).strip())
        except Exception:
            continue
        for item in _jsonld_objects(data):
            item_type = item.get('@type') or item.get('type')
            types = [str(t).lower() for t in item_type] if isinstance(item_type, list) else [str(item_type or '').lower()]
            if 'product' in types:
                return item
    return {}


def _meta(html: str, names: tuple[str, ...]) -> str:
    raw = str(html or '')
    for name in names:
        patterns = (
            rf'<meta[^>]+(?:property|name)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']',
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(name)}["\']',
        )
        for pattern in patterns:
            match = re.search(pattern, raw, flags=re.I | re.S)
            if match:
                return unescape(match.group(1)).strip()
    return ''


def _first_h1(html: str) -> str:
    match = re.search(r'<h1[^>]*>(.*?)</h1>', str(html or ''), flags=re.I | re.S)
    if not match:
        return ''
    text = re.sub(r'<[^>]+>', ' ', match.group(1))
    return clean_cell(unescape(text))


def _as_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item or '').strip() for item in value if str(item or '').strip()]
    if isinstance(value, dict):
        return [str(value.get('url') or value.get('@id') or '').strip()]
    return []


def _img_candidates_from_html(html: str) -> list[str]:
    raw = str(html or '')
    urls: list[str] = []
    attr_names = ('src', 'data-src', 'data-original', 'data-lazy', 'data-zoom-image', 'data-large_image', 'srcset')
    for tag in re.findall(r'<img\b[^>]*>', raw, flags=re.I | re.S):
        for attr in attr_names:
            for match in re.findall(rf'{attr}=["\']([^"\']+)["\']', tag, flags=re.I):
                if attr == 'srcset':
                    parts = [part.strip().split(' ')[0] for part in match.split(',')]
                    urls.extend(parts)
                else:
                    urls.append(match.strip())
    for pattern in (
        r'["\'](?:image|images|thumbnail|thumbnailUrl|foto|fotos)["\']\s*:\s*["\']([^"\']+)["\']',
        r'["\'](?:url)["\']\s*:\s*["\']([^"\']+\.(?:jpg|jpeg|png|webp))(?:\?[^"\']*)?["\']',
    ):
        urls.extend(re.findall(pattern, raw, flags=re.I))
    return urls


def _normalize_images(urls: list[str], base_url: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for url in urls:
        value = str(url or '').strip()
        if not value:
            continue
        if value.startswith('//'):
            value = 'https:' + value
        if value.startswith('/'):
            value = urljoin(base_url, value)
        if not value.startswith(('http://', 'https://')):
            continue
        low = value.lower()
        if not re.search(r'\.(jpg|jpeg|png|webp)(\?|$)', low) and 'image' not in low and 'produto' not in low:
            continue
        if any(term in low for term in BLOCKED_IMAGE_TERMS):
            continue
        value = re.sub(r'([?&])(width|height|w|h|resize|quality|cache|v)=[^&]+', '', value, flags=re.I).rstrip('?&')
        key = value.lower()
        if key not in seen:
            out.append(value)
            seen.add(key)
    return out[:10]


def _rendered_html_with_playwright(url: str) -> str:
    clean_url = clean_cell(url)
    if not clean_url.startswith(('http://', 'https://')):
        return ''
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        add_audit_event(
            'site_pipeline_blingfix_playwright_unavailable',
            area='SITE',
            status='AVISO',
            details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE},
        )
        return ''

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled', '--no-sandbox'])
            context = browser.new_context(
                viewport={'width': 1366, 'height': 900},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
                locale='pt-BR',
            )
            page = context.new_page()
            page.goto(clean_url, wait_until='domcontentloaded', timeout=PLAYWRIGHT_TIMEOUT_MS)
            page.wait_for_timeout(PLAYWRIGHT_WAIT_MS)
            try:
                page.evaluate('window.scrollTo(0, Math.max(document.body.scrollHeight, document.documentElement.scrollHeight));')
                page.wait_for_timeout(500)
                page.evaluate('window.scrollTo(0, 0);')
                page.wait_for_timeout(250)
            except Exception:
                pass
            html = page.content()
            browser.close()
            add_audit_event(
                'site_pipeline_blingfix_playwright_rendered',
                area='SITE',
                status='OK',
                details={'url': clean_url, 'html_size': len(html or ''), 'responsible_file': RESPONSIBLE_FILE},
            )
            return html or ''
    except Exception as exc:
        add_audit_event(
            'site_pipeline_blingfix_playwright_failed',
            area='SITE',
            status='AVISO',
            details={'url': clean_url, 'error': str(exc)[:260], 'responsible_file': RESPONSIBLE_FILE},
        )
        return ''


def _extract_from_html(html: str, url: str) -> dict[str, str]:
    product = _extract_jsonld_product(html)
    name = clean_cell(product.get('name') if product else '') or _meta(html, ('og:title', 'twitter:title')) or _first_h1(html)
    description = clean_cell(product.get('description') if product else '') or _meta(html, ('description', 'og:description', 'twitter:description'))
    image_urls = _as_list(product.get('image') or product.get('images')) if product else []
    if not image_urls:
        meta_image = _meta(html, ('og:image', 'twitter:image', 'image'))
        if meta_image:
            image_urls.append(meta_image)
    image_urls.extend(_img_candidates_from_html(html))
    images = _normalize_images(image_urls, url)
    return {
        'nome': clean_cell(unescape(name)),
        'descricao': clean_cell(unescape(description)),
        'imagens': '|'.join(images),
    }


def _requests_html(url: str) -> str:
    try:
        response = requests.get(
            url,
            timeout=PAGE_TIMEOUT,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            },
        )
        if response.status_code < 400:
            return response.text or ''
    except Exception:
        return ''
    return ''


def _fetch_product_page(url: str, *, allow_playwright: bool = False) -> dict[str, str]:
    clean_url = clean_cell(url)
    if not clean_url.startswith(('http://', 'https://')):
        return {}

    html = _requests_html(clean_url)
    data = _extract_from_html(html, clean_url) if html else {}
    if data and data.get('imagens'):
        return data

    if not allow_playwright:
        return data or {}

    rendered_html = _rendered_html_with_playwright(clean_url)
    rendered_data = _extract_from_html(rendered_html, clean_url) if rendered_html else {}
    if rendered_data:
        merged = dict(data or {})
        for key, value in rendered_data.items():
            if value and not merged.get(key):
                merged[key] = value
        if rendered_data.get('imagens'):
            merged['imagens'] = rendered_data['imagens']
        return merged
    return data or {}


def _needs_text(value: object) -> bool:
    text = clean_cell(value)
    return not text or len(text) < 6


def _needs_enrichment(row: pd.Series, *, title_col: str, desc_col: str, image_col: str) -> bool:
    return bool(
        _needs_text(row.get(title_col, ''))
        or _needs_text(row.get(desc_col, ''))
        or not clean_cell(row.get(image_col, ''))
    )


def _apply_data(out: pd.DataFrame, index: object, *, row: pd.Series, title_col: str, desc_col: str, image_col: str, data: dict[str, str]) -> bool:
    changed = False
    if _needs_text(row.get(title_col, '')) and data.get('nome'):
        out.at[index, title_col] = data['nome'][:180]
        changed = True
    if _needs_text(row.get(desc_col, '')) and data.get('descricao'):
        out.at[index, desc_col] = data['descricao'][:2400]
        changed = True
    if not clean_cell(row.get(image_col, '')) and data.get('imagens'):
        out.at[index, image_col] = data['imagens']
        changed = True
    return changed


def enrich_product_pages_for_bling(df: pd.DataFrame, *, operation: str, progress_callback: Callable[[dict], None] | None = None) -> pd.DataFrame:
    if operation == 'estoque' or not isinstance(df, pd.DataFrame) or df.empty:
        return df

    out = df.copy().fillna('')
    url_col = _find_col(out, URL_COLUMNS)
    if not url_col:
        return out

    title_col = _ensure_col(out, 'nome', TITLE_COLUMNS)
    desc_col = _ensure_col(out, 'descricao', DESC_COLUMNS)
    image_col = _ensure_col(out, 'imagens', IMAGE_COLUMNS)

    candidates: list[tuple[object, str]] = []
    for index, row in out.head(MAX_ROWS).iterrows():
        url = clean_cell(row.get(url_col, ''))
        if url and _needs_enrichment(row, title_col=title_col, desc_col=desc_col, image_col=image_col):
            candidates.append((index, url))

    if not candidates:
        return out.fillna('')

    rows_by_index = {index: out.loc[index].copy() for index, _url in candidates}
    enriched = 0
    checked = 0
    workers = max(1, min(MAX_WORKERS, len(candidates)))

    if progress_callback:
        progress_callback({
            'stage': 'BLINGFIX por lote',
            'message': f'Reforçando dados ausentes em até {len(candidates)} produto(s), sem cortar nos primeiros 180.',
            'progress': 0.955,
            'checked_rows': len(candidates),
            'max_rows': MAX_ROWS,
        })

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_fetch_product_page, url, allow_playwright=False): (index, url) for index, url in candidates}
        for future in as_completed(futures):
            index, _url = futures[future]
            checked += 1
            try:
                data = future.result() or {}
            except Exception:
                data = {}
            row = rows_by_index.get(index, out.loc[index])
            if data and _apply_data(out, index, row=row, title_col=title_col, desc_col=desc_col, image_col=image_col, data=data):
                enriched += 1
            if progress_callback and (checked % 25 == 0 or checked == len(candidates)):
                progress_callback({
                    'stage': 'BLINGFIX por lote',
                    'message': f'{checked}/{len(candidates)} página(s) conferida(s). {enriched} produto(s) reforçado(s).',
                    'progress': 0.955 + min(0.03, 0.03 * checked / max(len(candidates), 1)),
                    'checked_rows': checked,
                    'enriched_rows': enriched,
                })

    # Playwright é caro. Usar só como reforço final nos primeiros casos que ainda
    # ficaram sem imagem, para evitar travar lote grande de 300/600/1200 produtos.
    playwright_used = 0
    if PLAYWRIGHT_FALLBACK_MAX > 0:
        for index, url in candidates:
            if playwright_used >= PLAYWRIGHT_FALLBACK_MAX:
                break
            row = out.loc[index]
            if clean_cell(row.get(image_col, '')):
                continue
            data = _fetch_product_page(url, allow_playwright=True)
            playwright_used += 1
            if data and _apply_data(out, index, row=row, title_col=title_col, desc_col=desc_col, image_col=image_col, data=data):
                enriched += 1

    add_audit_event(
        'site_pipeline_blingfix_product_media_enriched',
        area='SITE',
        status='OK' if enriched else 'INFO',
        details={
            'checked_rows': checked,
            'candidate_rows': len(candidates),
            'enriched_rows': enriched,
            'url_column': url_col,
            'title_column': title_col,
            'description_column': desc_col,
            'image_column': image_col,
            'operation': operation,
            'max_rows': MAX_ROWS,
            'workers': workers,
            'playwright_fallback_max': PLAYWRIGHT_FALLBACK_MAX,
            'playwright_fallback_used': playwright_used,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return out.fillna('')


def run_pipeline(
    raw_urls: str,
    requested_columns: list[str] | None = None,
    all_products: bool = True,
    max_pages: int = 0,
    max_products: int = 0,
    operation: str = 'universal',
    progress_callback: Callable[[dict], None] | None = None,
) -> pd.DataFrame:
    df = _base_run_pipeline(
        raw_urls,
        requested_columns=requested_columns,
        all_products=all_products,
        max_pages=max_pages,
        max_products=max_products,
        operation=operation,
        progress_callback=progress_callback,
    )
    df = _filter_live_origin_rows(df, raw_urls)
    return enrich_product_pages_for_bling(df, operation=str(operation or ''), progress_callback=progress_callback)


__all__ = ['enrich_product_pages_for_bling', 'run_pipeline']
