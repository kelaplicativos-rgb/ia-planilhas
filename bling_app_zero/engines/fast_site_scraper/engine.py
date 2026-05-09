from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable

import pandas as pd

from bling_app_zero.core.column_contract import RequestedField, build_contract
from bling_app_zero.core.text import normalize_key
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
SMART_COMPLETE_TARGET = 180
SMART_STOP_MIN_PROCESSED = 120
SMART_STOP_COMPLETE_RATIO = 0.72
SMART_STOP_NO_GAIN_WINDOW = 80
SMART_STOP_MIN_FOUND = 60


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


def _important_kinds(contract: list[RequestedField]) -> set[str]:
    kinds = {field.kind for field in contract if field.kind != 'custom'}
    if 'codigo' in kinds or 'id_produto' in kinds:
        kinds.add('gtin')
    # Campos de preenchimento padrão não devem travar parada inteligente.
    kinds -= {'deposito', 'data', 'observacao'}
    return kinds or {'url'}


def _value_for_kind(product: FastProductData, kind: str) -> str:
    if kind == 'url':
        return product.url
    if kind in {'codigo', 'id_produto'}:
        return product.codigo or product.gtin
    if kind == 'gtin':
        return product.gtin
    if kind in {'descricao', 'nome_apoio'}:
        return product.descricao
    if kind in {'preco_unitario', 'preco_custo'}:
        return product.preco
    if kind == 'estoque':
        return product.estoque
    if kind == 'imagem':
        return product.imagem
    if kind == 'marca':
        return product.marca
    if kind == 'categoria':
        return product.categoria
    return ''


def _has_useful_data(product: FastProductData, needed: set[str]) -> bool:
    """Evita linhas vazias quando a página falha e o modelo não pediu URL."""
    if any([product.codigo, product.gtin, product.descricao, product.preco, product.estoque, product.imagem, product.marca, product.categoria]):
        return True
    return 'url' in needed and bool(product.url)


def _is_complete_product(product: FastProductData, important_kinds: set[str]) -> bool:
    for kind in important_kinds:
        value = str(_value_for_kind(product, kind) or '').strip()
        if not value:
            return False
    return True


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
        row[field.original] = _value_for_kind(product, field.kind)
    return row


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    for column in columns:
        if column not in out.columns:
            out[column] = ''
    return out.loc[:, columns].fillna('')


def _should_stop_early(
    *,
    processed: int,
    products: list[FastProductData],
    complete_count: int,
    last_gain_at: int,
) -> tuple[bool, str]:
    found = len(products)
    if complete_count >= SMART_COMPLETE_TARGET:
        return True, f'{complete_count} produto(s) completos encontrados.'

    if processed >= SMART_STOP_MIN_PROCESSED and found >= SMART_STOP_MIN_FOUND:
        ratio = complete_count / max(found, 1)
        if ratio >= SMART_STOP_COMPLETE_RATIO:
            return True, f'{complete_count}/{found} produto(s) com os principais campos preenchidos.'

    if processed - last_gain_at >= SMART_STOP_NO_GAIN_WINDOW and found >= SMART_STOP_MIN_FOUND:
        return True, 'A busca parou porque os últimos links não trouxeram novos produtos úteis.'

    return False, ''


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
    important = _important_kinds(contract)

    _emit(progress_callback, {
        'stage': 'Procurando links',
        'message': 'Procurando produtos nos links informados...',
        'progress': 0.08,
        'columns': len(columns),
    })
    discovery_started = time.perf_counter()
    urls = discover_product_urls(raw_urls, max_pages=max_pages, max_products=max_products)
    discovery_seconds = time.perf_counter() - discovery_started

    _emit(progress_callback, {
        'stage': 'Links encontrados',
        'message': f'{len(urls)} link(s) de produto separados para leitura.',
        'progress': 0.22,
        'urls_found': len(urls),
        'discovery_seconds': round(discovery_seconds, 2),
    })

    if not urls:
        _emit(progress_callback, {
            'stage': 'Nada encontrado',
            'message': 'Não encontrei produtos nos links informados. Confira se o link abre produtos ou categorias.',
            'progress': 1.0,
            'urls_found': 0,
        })
        return pd.DataFrame(columns=columns)

    if needed <= {'url'}:
        rows = [_to_contract_row(_url_only_row(url), contract) for url in urls[:max_products]]
        _emit(progress_callback, {
            'stage': 'Pronto',
            'message': f'{len(rows)} link(s) preparados para a origem.',
            'progress': 0.92,
            'processed': len(rows),
            'urls_found': len(urls),
            'total_seconds': round(time.perf_counter() - total_started, 2),
        })
        return _ensure_columns(pd.DataFrame(rows).fillna(''), columns)

    products: list[FastProductData] = []
    errors = 0
    complete_count = 0
    last_gain_at = 0
    stop_reason = ''
    slow_links: list[dict[str, object]] = []
    workers = max(1, min(MAX_WORKERS, len(urls)))
    total = len(urls[:max_products])
    processed = 0
    last_emit = time.perf_counter()

    _emit(progress_callback, {
        'stage': 'Lendo produtos',
        'message': f'Lendo até {total} produto(s). A busca para sozinha quando já tiver resultado suficiente.',
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
                if _has_useful_data(product, needed):
                    products.append(product)
                    last_gain_at = processed
                    if _is_complete_product(product, important):
                        complete_count += 1
            except Exception:
                errors += 1

            should_stop, reason = _should_stop_early(
                processed=processed,
                products=products,
                complete_count=complete_count,
                last_gain_at=last_gain_at,
            )
            if should_stop:
                stop_reason = reason
                for pending in futures:
                    if not pending.done():
                        pending.cancel()
                _emit(progress_callback, {
                    'stage': 'Busca suficiente',
                    'message': stop_reason,
                    'progress': 0.88,
                    'processed': processed,
                    'total': total,
                    'found': len(products),
                    'complete': complete_count,
                    'errors': errors,
                    'slow_links': slow_links[-5:],
                })
                break

            now = time.perf_counter()
            if now - last_emit >= 0.5 or processed == total:
                ratio = processed / max(total, 1)
                _emit(progress_callback, {
                    'stage': 'Lendo produtos',
                    'message': f'{processed}/{total} produto(s) lido(s).',
                    'progress': 0.28 + (0.60 * ratio),
                    'processed': processed,
                    'total': total,
                    'found': len(products),
                    'complete': complete_count,
                    'errors': errors,
                    'slow_links': slow_links[-5:],
                })
                last_emit = now

    rows = [_to_contract_row(product, contract) for product in products]
    final_message = f'Montando origem com {len(rows)} produto(s).'
    if stop_reason:
        final_message = f'{final_message} {stop_reason}'
    _emit(progress_callback, {
        'stage': 'Montando origem',
        'message': final_message,
        'progress': 0.91,
        'processed': processed,
        'found': len(products),
        'complete': complete_count,
        'errors': errors,
        'slow_links': slow_links[-10:],
        'total_seconds': round(time.perf_counter() - total_started, 2),
    })
    return _ensure_columns(pd.DataFrame(rows).fillna(''), columns)
