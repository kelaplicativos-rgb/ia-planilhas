from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable

import pandas as pd

from bling_app_zero.core.column_contract import RequestedField, build_contract
from bling_app_zero.engines.fast_site_scraper.extractors import (
    extract_brand,
    extract_category,
    extract_code,
    extract_description,
    extract_gtin,
    extract_images,
    extract_price,
    extract_stock,
    extract_url,
)
from bling_app_zero.engines.fast_site_scraper.http_client import fetch_live
from bling_app_zero.engines.fast_site_scraper.models import FastProductData
from bling_app_zero.engines.fast_site_scraper.page_parser import parse_product_page
from bling_app_zero.engines.fast_site_scraper.url_discovery import discover_product_urls

MAX_WORKERS = 48
SLOW_LINK_SECONDS = 6.0


def _emit(progress_callback: Callable[[dict], None] | None, payload: dict) -> None:
    if not progress_callback:
        return
    try:
        progress_callback(payload)
    except Exception:
        pass


def _default_columns(operation: str) -> list[str]:
    if operation == 'estoque':
        return ['Código', 'Descrição', 'Depósito (OBRIGATÓRIO)', 'Balanço (OBRIGATÓRIO)']
    return ['URL', 'Código', 'SKU', 'GTIN', 'Descrição', 'Nome', 'Preço', 'Preço unitário (OBRIGATÓRIO)', 'URL Imagens', 'Imagens', 'Marca', 'Categoria']


def _needed_kinds(contract: list[RequestedField]) -> set[str]:
    kinds = {field.kind for field in contract}
    if 'codigo' in kinds or 'id_produto' in kinds:
        kinds.add('gtin')
    return kinds


def _url_only_row(url: str) -> FastProductData:
    return FastProductData(url=url)


def _scrape_one(url: str, needed: set[str]) -> tuple[FastProductData, float, bool]:
    started = time.perf_counter()
    if needed <= {'url'}:
        return _url_only_row(url), time.perf_counter() - started, False

    html = fetch_live(url, timeout=8)
    elapsed = time.perf_counter() - started
    if not html:
        return FastProductData(url=url), elapsed, True

    page = parse_product_page(url, html)

    data = {
        'url': url,
        'codigo': '',
        'gtin': '',
        'descricao': '',
        'preco': '',
        'estoque': '',
        'imagem': '',
        'marca': '',
        'categoria': '',
    }

    if 'url' in needed:
        data['url'] = extract_url(page)
    if 'codigo' in needed or 'id_produto' in needed:
        data['codigo'] = extract_code(page)
    if 'gtin' in needed:
        data['gtin'] = extract_gtin(page)
    if 'descricao' in needed or 'nome_apoio' in needed:
        data['descricao'] = extract_description(page)
    if 'preco_unitario' in needed or 'preco_custo' in needed:
        data['preco'] = extract_price(page)
    if 'estoque' in needed:
        data['estoque'] = extract_stock(page)
    if 'imagem' in needed:
        data['imagem'] = extract_images(page)
    if 'marca' in needed:
        data['marca'] = extract_brand(page)
    if 'categoria' in needed:
        data['categoria'] = extract_category(page)

    if not data['codigo'] and data['gtin']:
        data['codigo'] = data['gtin']

    return FastProductData(**data), elapsed, False


def _to_contract_row(product: FastProductData, contract: list[RequestedField]) -> dict[str, str]:
    row: dict[str, str] = {}
    for field in contract:
        kind = field.kind
        if kind == 'url':
            row[field.original] = product.url
        elif kind in {'codigo', 'id_produto'}:
            row[field.original] = product.codigo or product.gtin
        elif kind == 'gtin':
            row[field.original] = product.gtin
        elif kind in {'descricao', 'nome_apoio'}:
            row[field.original] = product.descricao
        elif kind in {'preco_unitario', 'preco_custo'}:
            row[field.original] = product.preco
        elif kind == 'estoque':
            row[field.original] = product.estoque
        elif kind == 'imagem':
            row[field.original] = product.imagem
        elif kind == 'marca':
            row[field.original] = product.marca
        elif kind == 'categoria':
            row[field.original] = product.categoria
        else:
            row[field.original] = ''
    return row


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    for column in columns:
        if column not in out.columns:
            out[column] = ''
    return out.loc[:, columns].fillna('')


def run_fast_site_scraper(
    raw_urls: str,
    requested_columns: Iterable[str] | None = None,
    operation: str = 'cadastro',
    max_pages: int = 1_000_000,
    max_products: int = 1_000_000,
    progress_callback: Callable[[dict], None] | None = None,
) -> pd.DataFrame:
    total_started = time.perf_counter()
    columns = [str(column).strip() for column in (requested_columns or []) if str(column).strip()] or _default_columns(operation)
    contract = build_contract(columns)
    needed = _needed_kinds(contract)

    _emit(progress_callback, {
        'stage': 'Descobrindo links',
        'message': 'Buscando produtos no site, sitemap e categorias...',
        'progress': 0.08,
        'columns': len(columns),
    })
    discovery_started = time.perf_counter()
    urls = discover_product_urls(raw_urls, max_pages=max_pages, max_products=max_products)
    discovery_seconds = time.perf_counter() - discovery_started

    _emit(progress_callback, {
        'stage': 'Links encontrados',
        'message': f'{len(urls)} link(s) de produto encontrado(s).',
        'progress': 0.22,
        'urls_found': len(urls),
        'discovery_seconds': round(discovery_seconds, 2),
    })

    if not urls:
        _emit(progress_callback, {
            'stage': 'Sem produtos',
            'message': 'Nenhum produto encontrado nos links informados.',
            'progress': 1.0,
            'urls_found': 0,
        })
        return pd.DataFrame(columns=columns)

    if needed <= {'url'}:
        rows = [_to_contract_row(_url_only_row(url), contract) for url in urls[:max_products]]
        _emit(progress_callback, {
            'stage': 'Concluído',
            'message': f'{len(rows)} URL(s) preparada(s) sem baixar páginas de produto.',
            'progress': 0.92,
            'processed': len(rows),
            'urls_found': len(urls),
            'total_seconds': round(time.perf_counter() - total_started, 2),
        })
        return _ensure_columns(pd.DataFrame(rows).fillna(''), columns)

    products: list[FastProductData] = []
    errors = 0
    slow_links: list[dict[str, object]] = []
    workers = max(1, min(MAX_WORKERS, len(urls)))
    total = len(urls[:max_products])
    processed = 0
    last_emit = time.perf_counter()

    _emit(progress_callback, {
        'stage': 'Lendo produtos',
        'message': f'Lendo {total} produto(s) ao vivo...',
        'progress': 0.28,
        'processed': 0,
        'total': total,
        'workers': workers,
    })

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_scrape_one, url, needed): url for url in urls[:max_products]}
        for future in as_completed(futures):
            url = futures[future]
            processed += 1
            try:
                product, elapsed, failed = future.result()
                if failed:
                    errors += 1
                if elapsed >= SLOW_LINK_SECONDS:
                    slow_links.append({'url': url, 'seconds': round(elapsed, 2)})
                if any([product.codigo, product.descricao, product.preco, product.estoque, product.imagem, product.url]):
                    products.append(product)
            except Exception:
                errors += 1

            now = time.perf_counter()
            if now - last_emit >= 0.5 or processed == total:
                ratio = processed / max(total, 1)
                _emit(progress_callback, {
                    'stage': 'Lendo produtos',
                    'message': f'{processed}/{total} produto(s) processado(s).',
                    'progress': 0.28 + (0.60 * ratio),
                    'processed': processed,
                    'total': total,
                    'found': len(products),
                    'errors': errors,
                    'slow_links': slow_links[-5:],
                })
                last_emit = now

    rows = [_to_contract_row(product, contract) for product in products]
    _emit(progress_callback, {
        'stage': 'Montando planilha',
        'message': f'Montando planilha com {len(rows)} produto(s).',
        'progress': 0.91,
        'processed': processed,
        'found': len(products),
        'errors': errors,
        'slow_links': slow_links[-10:],
        'total_seconds': round(time.perf_counter() - total_started, 2),
    })
    return _ensure_columns(pd.DataFrame(rows).fillna(''), columns)
