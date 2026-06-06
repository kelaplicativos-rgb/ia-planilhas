from __future__ import annotations

import json
import re
from html import unescape
from typing import Any, Callable
from urllib.parse import urljoin

import pandas as pd
import requests

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.text import clean_cell
from bling_app_zero.pipelines.site_pipeline import run_pipeline as _base_run_pipeline

RESPONSIBLE_FILE = 'bling_app_zero/pipelines/site_pipeline_blingfix.py'
PAGE_TIMEOUT = 14
MAX_ROWS = 180
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


def _fetch_product_page(url: str) -> dict[str, str]:
    clean_url = clean_cell(url)
    if not clean_url.startswith(('http://', 'https://')):
        return {}
    try:
        response = requests.get(
            clean_url,
            timeout=PAGE_TIMEOUT,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            },
        )
        if response.status_code >= 400:
            return {}
        html = response.text or ''
    except Exception:
        return {}

    product = _extract_jsonld_product(html)
    name = clean_cell(product.get('name') if product else '') or _meta(html, ('og:title', 'twitter:title')) or _first_h1(html)
    description = clean_cell(product.get('description') if product else '') or _meta(html, ('description', 'og:description', 'twitter:description'))
    image_urls = _as_list(product.get('image') or product.get('images')) if product else []
    if not image_urls:
        meta_image = _meta(html, ('og:image', 'twitter:image', 'image'))
        if meta_image:
            image_urls.append(meta_image)
    image_urls.extend(_img_candidates_from_html(html))
    images = _normalize_images(image_urls, clean_url)
    return {
        'nome': clean_cell(unescape(name)),
        'descricao': clean_cell(unescape(description)),
        'imagens': '|'.join(images),
    }


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

    enriched = 0
    checked = 0
    for index, row in out.head(MAX_ROWS).iterrows():
        url = clean_cell(row.get(url_col, ''))
        if not url:
            continue
        needs_title = not clean_cell(row.get(title_col, ''))
        needs_desc = not clean_cell(row.get(desc_col, ''))
        needs_images = not clean_cell(row.get(image_col, ''))
        if not (needs_title or needs_desc or needs_images):
            continue
        checked += 1
        data = _fetch_product_page(url)
        if not data:
            continue
        if needs_title and data.get('nome'):
            out.at[index, title_col] = data['nome'][:160]
        if needs_desc and data.get('descricao'):
            out.at[index, desc_col] = data['descricao'][:2200]
        if needs_images and data.get('imagens'):
            out.at[index, image_col] = data['imagens']
        enriched += 1
        if progress_callback and enriched % 5 == 0:
            progress_callback({'stage': 'BLINGFIX imagens', 'message': f'{enriched} produto(s) com nome/descrição/imagem reforçados pela página.', 'progress': 0.975})

    if enriched:
        add_audit_event(
            'site_pipeline_blingfix_product_media_enriched',
            area='SITE',
            status='OK',
            details={
                'checked_rows': checked,
                'enriched_rows': enriched,
                'url_column': url_col,
                'title_column': title_col,
                'description_column': desc_col,
                'image_column': image_col,
                'operation': operation,
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
    return enrich_product_pages_for_bling(df, operation=str(operation or ''), progress_callback=progress_callback)


__all__ = ['enrich_product_pages_for_bling', 'run_pipeline']
