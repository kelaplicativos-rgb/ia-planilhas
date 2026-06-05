from __future__ import annotations

import json
import re
from html import unescape
from typing import Any, Callable
from urllib.parse import urljoin

import pandas as pd
import requests

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.core.text import clean_cell, normalize_key
from bling_app_zero.engines.fast_site_scraper.constants import (
    DEEP_CAPTURE_MAX_PAGES,
    DEEP_CAPTURE_MAX_PRODUCTS,
    SAFE_CAPTURE_MAX_PAGES,
    SAFE_CAPTURE_MAX_PRODUCTS,
    normalize_capture_limits,
)
from bling_app_zero.engines.fast_site_scraper.text_cleaner import clean_product_description
from bling_app_zero.engines.site_operations import run_site_operation_engine
from bling_app_zero.universal.model_contract_detector import normalize_contract_operation

RESPONSIBLE_FILE = 'bling_app_zero/pipelines/site_pipeline.py'
VALID_OPERATIONS = {'cadastro', 'estoque', 'universal', 'atualizacao_preco'}
UNIVERSAL_ALIASES = {'universal', 'modelo', 'modelo_destino', 'planilha', 'wizard_cadastro_estoque'}
ALL_PAGES_LIMIT = DEEP_CAPTURE_MAX_PAGES
ALL_PRODUCTS_LIMIT = DEEP_CAPTURE_MAX_PRODUCTS
PAGE_ENRICH_TIMEOUT = 12
PAGE_ENRICH_MAX_ROWS = 160

ESTOQUE_COLUMN_SIGNALS = (
    'estoque',
    'saldo',
    'quantidade',
    'balanco',
    'balanço',
    'deposito',
    'depósito',
)
PRICE_UPDATE_COLUMN_SIGNALS = (
    'preco',
    'preço',
    'preco_unitario',
    'preço_unitário',
    'preco unitario',
    'preço unitário',
    'valor',
    'valor_unitario',
    'valor unitario',
    'custo',
)
ID_COLUMN_SIGNALS = (
    'id',
    'id_produto',
    'id produto',
    'codigo',
    'código',
    'sku',
    'gtin',
    'ean',
)
CADASTRO_ONLY_COLUMN_SIGNALS = (
    'imagem',
    'imagens',
    'url_imagens',
    'marca',
    'categoria',
    'ncm',
    'descricao_complementar',
    'descrição_complementar',
    'caracteristicas',
    'características',
    'ficha_tecnica',
    'ficha_técnica',
)
DESCRIPTION_COLUMN_SIGNALS = (
    'descricao_complementar',
    'descrição_complementar',
    'descricao_completa',
    'descrição_completa',
    'descricao_detalhada',
    'descrição_detalhada',
    'descricao_do_produto',
    'descrição_do_produto',
    'ficha_tecnica',
    'ficha_técnica',
    'caracteristicas',
    'características',
    'detalhes',
)
PLAIN_DESCRIPTION_COLUMN_SIGNALS = (
    'descricao',
    'descrição',
)
TITLE_COLUMN_SIGNALS = (
    'nome',
    'produto',
    'titulo',
    'título',
)
FALLBACK_TITLE_COLUMN_SIGNALS = (
    'descricao',
    'descrição',
)
URL_COLUMN_SIGNALS = (
    'url',
    'link',
    'produto_url',
    'url_produto',
)
IMAGE_COLUMN_SIGNALS = (
    'imagem',
    'imagens',
    'url_imagens',
    'url imagem',
    'foto',
    'fotos',
)
DESCRIPTION_NOISE_SIGNALS = (
    'ainda nao ha para este produto',
    'ainda não há para este produto',
    'ainda nao ha avaliacoes para este produto',
    'ainda não há avaliações para este produto',
    'avaliacoes',
    'avaliações',
    'seja o primeiro a avaliar',
    'entre para avaliar',
    'calcule o frete',
    'compartilhar produto',
    'continuar comprando',
    'adicionar',
    'comprar',
    'veja como pagar',
)
LONG_DESCRIPTION_MIN_CHARS = 90
LONG_DESCRIPTION_MIN_WORDS = 14


def _normalize_operation(operation: str | None) -> str:
    normalized = normalize_contract_operation(operation)
    if normalized in VALID_OPERATIONS:
        return normalized
    value = str(operation or 'universal').strip().lower()
    if value in {'estoque', 'stock', 'atualizacao_estoque', 'atualização de estoque', 'estoque_site'}:
        return 'estoque'
    if value in {'cadastro', 'cadastro_site', 'produtos', 'produto'}:
        return 'cadastro'
    if value in UNIVERSAL_ALIASES:
        return 'universal'
    return 'universal'


def _safe_positive_int(value: int | None, fallback: int) -> int:
    try:
        parsed = int(value or 0)
    except Exception:
        parsed = 0
    return parsed if parsed > 0 else fallback


def _bounded_limit(value: int | None, fallback: int, hard_limit: int) -> int:
    return min(_safe_positive_int(value, fallback), hard_limit)


def _column_key(column: object) -> str:
    return normalize_key(str(column or '').replace('\n', ' ').replace('\r', ' ')).replace(' ', '_')


def _has_any_signal(key: str, signals: tuple[str, ...]) -> bool:
    return any(normalize_key(signal).replace(' ', '_') in key for signal in signals)


def _infer_operation_from_columns(operation: str, requested_columns: list[str] | None) -> str:
    """Preserva o fluxo universal, mas escolhe o motor correto pelo modelo anexado."""
    normalized = _normalize_operation(operation)
    if normalized != 'universal':
        return normalized

    keys = [_column_key(column) for column in (requested_columns or [])]
    has_estoque_signal = any(_has_any_signal(key, ESTOQUE_COLUMN_SIGNALS) for key in keys)
    has_cadastro_only_signal = any(_has_any_signal(key, CADASTRO_ONLY_COLUMN_SIGNALS) for key in keys)
    has_price_signal = any(_has_any_signal(key, PRICE_UPDATE_COLUMN_SIGNALS) for key in keys)
    has_id_signal = any(_has_any_signal(key, ID_COLUMN_SIGNALS) for key in keys)

    if has_estoque_signal and not has_cadastro_only_signal:
        return 'estoque'
    if has_price_signal and has_id_signal and not has_estoque_signal and not has_cadastro_only_signal:
        return 'atualizacao_preco'
    return normalized


def _value_key(value: object) -> str:
    return normalize_key(clean_cell(value))


def _word_count(value: object) -> int:
    return len(re.findall(r'\w+', clean_cell(value), flags=re.UNICODE))


def _is_description_column(column: object) -> bool:
    key = _column_key(column)
    if not key:
        return False
    return any(signal in key for signal in DESCRIPTION_COLUMN_SIGNALS)


def _is_plain_description_column(column: object) -> bool:
    key = _column_key(column)
    return key in {_column_key(signal) for signal in PLAIN_DESCRIPTION_COLUMN_SIGNALS}


def _is_title_column(column: object) -> bool:
    key = _column_key(column)
    if not key:
        return False
    return any(signal == key or key.startswith(f'{signal}_') for signal in TITLE_COLUMN_SIGNALS)


def _is_fallback_title_column(column: object) -> bool:
    key = _column_key(column)
    if not key:
        return False
    return any(signal == key or key.startswith(f'{signal}_') for signal in FALLBACK_TITLE_COLUMN_SIGNALS)


def _best_title_column(df: pd.DataFrame, *, exclude: str = '') -> str:
    excluded = _column_key(exclude)
    for column in df.columns:
        if _column_key(column) == excluded:
            continue
        if _is_title_column(column) and not _is_description_column(column):
            return str(column)
    for column in df.columns:
        if _column_key(column) == excluded:
            continue
        if _is_fallback_title_column(column) and not _is_description_column(column):
            return str(column)
    return ''


def _looks_like_dirty_description(value: object) -> bool:
    text = clean_cell(value)
    if not text:
        return False

    key = _value_key(text)
    if any(normalize_key(signal) in key for signal in DESCRIPTION_NOISE_SIGNALS):
        return True

    return len(text) >= LONG_DESCRIPTION_MIN_CHARS and _word_count(text) >= LONG_DESCRIPTION_MIN_WORDS


def _description_columns_to_clean(df: pd.DataFrame) -> list[str]:
    columns: list[str] = []
    for column in df.columns:
        column_text = str(column)
        if _is_description_column(column_text):
            columns.append(column_text)
            continue

        if not _is_plain_description_column(column_text):
            continue

        series = df[column]
        try:
            should_clean = any(_looks_like_dirty_description(value) for value in series.tolist())
        except Exception:
            should_clean = False
        if should_clean:
            columns.append(column_text)
    return columns


def _clean_site_description_columns(df: pd.DataFrame, operation: str) -> pd.DataFrame:
    """Aplica a blindagem de descrição no fluxo unificado de busca por site."""
    _ = operation
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df

    description_columns = _description_columns_to_clean(df)
    if not description_columns:
        return df

    out = df.copy().fillna('')
    for column in description_columns:
        if column not in out.columns:
            continue
        title_column = _best_title_column(out, exclude=column)
        for index, value in out[column].items():
            if _is_plain_description_column(column) and not _looks_like_dirty_description(value):
                continue
            title = str(out.at[index, title_column]) if title_column and title_column in out.columns else ''
            out.at[index, column] = clean_product_description(str(value or ''), title=title, limit=1600)
    return out.fillna('')


def _find_column(df: pd.DataFrame, signals: tuple[str, ...]) -> str:
    if not isinstance(df, pd.DataFrame):
        return ''
    for column in df.columns:
        if _has_any_signal(_column_key(column), signals):
            return str(column)
    return ''


def _is_short_or_empty_description(value: object) -> bool:
    text = clean_cell(value)
    return (not text) or len(text) < 55 or _word_count(text) < 8 or _value_key(text).isdigit()


def _extract_meta_content(html: str, names: tuple[str, ...]) -> str:
    raw = str(html or '')
    for name in names:
        patterns = (
            rf'<meta[^>]+(?:property|name)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']',
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(name)}["\']',
        )
        for pattern in patterns:
            match = re.search(pattern, raw, flags=re.IGNORECASE | re.DOTALL)
            if match:
                return unescape(match.group(1)).strip()
    return ''


def _jsonld_objects(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        items = [value]
        graph = value.get('@graph')
        if isinstance(graph, list):
            for item in graph:
                items.extend(_jsonld_objects(item))
        return items
    if isinstance(value, list):
        out: list[dict[str, Any]] = []
        for item in value:
            out.extend(_jsonld_objects(item))
        return out
    return []


def _extract_jsonld_product(html: str) -> dict[str, Any]:
    for script in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', str(html or ''), flags=re.IGNORECASE | re.DOTALL):
        try:
            data = json.loads(unescape(script).strip())
        except Exception:
            continue
        for item in _jsonld_objects(data):
            item_type = item.get('@type') or item.get('type')
            if isinstance(item_type, list):
                types = [str(t).lower() for t in item_type]
            else:
                types = [str(item_type or '').lower()]
            if 'product' in types:
                return item
    return {}


def _string_or_join(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return ' '.join(str(item).strip() for item in value if str(item).strip())
    return str(value or '').strip()


def _images_from_jsonld(product: dict[str, Any]) -> list[str]:
    value = product.get('image') or product.get('images')
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _page_enrichment(url: str) -> dict[str, str]:
    clean_url = str(url or '').strip()
    if not clean_url.startswith(('http://', 'https://')):
        return {}
    try:
        response = requests.get(
            clean_url,
            timeout=PAGE_ENRICH_TIMEOUT,
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
    name = _string_or_join(product.get('name')) if product else ''
    description = _string_or_join(product.get('description')) if product else ''
    image_urls = _images_from_jsonld(product) if product else []

    if not name:
        name = _extract_meta_content(html, ('og:title', 'twitter:title'))
    if not description:
        description = _extract_meta_content(html, ('description', 'og:description', 'twitter:description'))
    if not image_urls:
        image = _extract_meta_content(html, ('og:image', 'twitter:image'))
        if image:
            image_urls = [image]

    normalized_images: list[str] = []
    for image in image_urls:
        value = str(image or '').strip()
        if not value:
            continue
        if value.startswith('//'):
            value = 'https:' + value
        if value.startswith('/'):
            value = urljoin(clean_url, value)
        if value.startswith(('http://', 'https://')) and value not in normalized_images:
            normalized_images.append(value)

    return {
        'name': clean_cell(unescape(name)),
        'description': clean_cell(unescape(description)),
        'images': '|'.join(normalized_images[:8]),
    }


def _enrich_missing_product_pages(df: pd.DataFrame, operation: str, progress_callback: Callable[[dict], None] | None = None) -> pd.DataFrame:
    if operation == 'estoque' or not isinstance(df, pd.DataFrame) or df.empty:
        return df

    url_col = _find_column(df, URL_COLUMN_SIGNALS)
    if not url_col:
        return df

    title_col = _best_title_column(df)
    desc_cols = [col for col in df.columns if _is_description_column(col)]
    if not desc_cols:
        fallback_desc = _find_column(df, PLAIN_DESCRIPTION_COLUMN_SIGNALS)
        if fallback_desc:
            desc_cols = [fallback_desc]
    image_col = _find_column(df, IMAGE_COLUMN_SIGNALS)

    if not desc_cols and not image_col and not title_col:
        return df

    out = df.copy().fillna('')
    enriched = 0
    checked = 0
    for index, row in out.head(PAGE_ENRICH_MAX_ROWS).iterrows():
        url = clean_cell(row.get(url_col, ''))
        if not url:
            continue
        needs_description = any(_is_short_or_empty_description(row.get(col, '')) for col in desc_cols)
        needs_image = bool(image_col and not clean_cell(row.get(image_col, '')))
        needs_title = bool(title_col and _is_short_or_empty_description(row.get(title_col, '')))
        if not (needs_description or needs_image or needs_title):
            continue
        checked += 1
        data = _page_enrichment(url)
        if not data:
            continue
        title = clean_cell(row.get(title_col, '')) if title_col else ''
        if title_col and needs_title and data.get('name'):
            out.at[index, title_col] = data['name']
            title = data['name']
        if desc_cols and data.get('description'):
            description = clean_product_description(data['description'], title=title or data.get('name', ''), limit=1800)
            if description:
                for col in desc_cols:
                    if _is_short_or_empty_description(out.at[index, col]):
                        out.at[index, col] = description
        if image_col and needs_image and data.get('images'):
            out.at[index, image_col] = data['images']
        enriched += 1
        if progress_callback and enriched % 10 == 0:
            progress_callback({'stage': 'Enriquecendo páginas', 'message': f'{enriched} produto(s) complementado(s) pela página individual.', 'progress': 0.965})

    if enriched:
        add_audit_event(
            'site_pipeline_product_pages_enriched',
            area='SITE',
            status='OK',
            details={
                'checked_rows': checked,
                'enriched_rows': enriched,
                'url_column': url_col,
                'title_column': title_col,
                'description_columns': desc_cols,
                'image_column': image_col,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
    return out.fillna('')


def run_pipeline(
    raw_urls: str,
    requested_columns: list[str] | None = None,
    all_products: bool = True,
    max_pages: int = ALL_PAGES_LIMIT,
    max_products: int = ALL_PRODUCTS_LIMIT,
    operation: str = 'universal',
    progress_callback: Callable[[dict], None] | None = None,
) -> pd.DataFrame:
    selected_operation = _infer_operation_from_columns(operation, requested_columns)
    capture_all = bool(all_products)
    mode = 'deep' if capture_all else 'safe'
    hard_pages = DEEP_CAPTURE_MAX_PAGES if capture_all else SAFE_CAPTURE_MAX_PAGES
    hard_products = DEEP_CAPTURE_MAX_PRODUCTS if capture_all else SAFE_CAPTURE_MAX_PRODUCTS
    limits = normalize_capture_limits(max_pages=max_pages, max_products=max_products, mode=mode)
    selected_max_pages = _bounded_limit(limits['max_pages'], ALL_PAGES_LIMIT if capture_all else SAFE_CAPTURE_MAX_PAGES, hard_pages)
    selected_max_products = _bounded_limit(limits['max_products'], ALL_PRODUCTS_LIMIT if capture_all else SAFE_CAPTURE_MAX_PRODUCTS, hard_products)
    stop_early = not capture_all

    if progress_callback:
        progress_callback({
            'stage': 'Preparando',
            'message': 'Preparando motor por modelo de destino em modo completo...' if capture_all else 'Preparando motor por modelo de destino com limite seguro...',
            'progress': 0.02,
            'operation': selected_operation,
            'max_pages': selected_max_pages,
            'max_products': selected_max_products,
            'all_products': capture_all,
            'stop_early': stop_early,
            'safe_limited': not capture_all,
        })

    df_result = run_site_operation_engine(
        operation=selected_operation,
        raw_urls=raw_urls,
        requested_columns=requested_columns,
        max_pages=selected_max_pages,
        max_products=selected_max_products,
        stop_early=stop_early,
        progress_callback=progress_callback,
    )

    if progress_callback:
        progress_callback({'stage': 'Organizando', 'message': 'Organizando e enriquecendo os dados do site antes do Bling...', 'progress': 0.96})
    enriched_result = _enrich_missing_product_pages(df_result, selected_operation, progress_callback=progress_callback)
    cleaned_result = _clean_site_description_columns(enriched_result, selected_operation)
    safe = sanitize_for_bling(cleaned_result, operation=selected_operation)
    if progress_callback:
        progress_callback({'stage': 'Pronto', 'message': f'{len(safe)} produto(s) preparados na origem.', 'progress': 1.0})
    return safe


__all__ = ['run_pipeline']
