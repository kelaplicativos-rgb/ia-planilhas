from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable

import pandas as pd

from bling_app_zero.core.column_contract import RequestedField, build_contract
from bling_app_zero.engines.devtools_scraper.enhancer import enhance_with_rendered_page, needs_rendered_fallback
from bling_app_zero.engines.fast_site_scraper.extractors import (
    extract_brand,
    extract_caracteristicas,
    extract_category,
    extract_code,
    extract_description,
    extract_description_complementar,
    extract_ficha_tecnica,
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

MAX_WORKERS = 12
BATCH_SIZE = 24
FETCH_TIMEOUT_SECONDS = 6
RUN_TIME_BUDGET_SECONDS = 210
SLOW_LINK_SECONDS = 6.0
SMART_COMPLETE_TARGET = 220
SMART_STOP_MIN_PROCESSED = 160
SMART_STOP_COMPLETE_RATIO = 0.78
SMART_STOP_NO_GAIN_WINDOW = 90
SMART_STOP_MIN_FOUND = 80
DEVTOOLS_FALLBACK_MAX_PER_RUN = 2


def _emit(progress_callback: Callable[[dict], None] | None, payload: dict) -> None:
    if not progress_callback:
        return
    try:
        progress_callback(payload)
    except Exception:
        pass


def _time_left(started_at: float) -> float:
    return RUN_TIME_BUDGET_SECONDS - (time.perf_counter() - started_at)


def _budget_exceeded(started_at: float, safety_margin: float = 12.0) -> bool:
    return _time_left(started_at) <= safety_margin


def _chunks(items: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _default_columns(operation: str) -> list[str]:
    if operation == 'estoque':
        return ['Código', 'Descrição', 'Depósito (OBRIGATÓRIO)', 'Balanço (OBRIGATÓRIO)']
    return [
        'URL',
        'Código',
        'SKU',
        'GTIN',
        'Descrição',
        'Descrição complementar',
        'Características',
        'Ficha técnica',
        'Nome',
        'Preço',
        'Preço unitário (OBRIGATÓRIO)',
        'URL Imagens',
        'Imagens',
        'Marca',
        'Categoria',
    ]


def _needed_kinds(contract: list[RequestedField]) -> set[str]:
    kinds = {field.kind for field in contract}
    if 'codigo' in kinds or 'id_produto' in kinds:
        kinds.add('gtin')
    return kinds


def _important_kinds(contract: list[RequestedField]) -> set[str]:
    kinds = {field.kind for field in contract if field.kind != 'custom'}
    if 'codigo' in kinds or 'id_produto' in kinds:
        kinds.add('gtin')
    kinds -= {'deposito', 'data', 'observacao'}
    return kinds or {'url'}


def _value_for_kind(product: FastProductData, kind: str) -> str:
    if kind == 'url':
        return product.url
    if kind in {'codigo', 'id_produto'}:
        return product.codigo or product.gtin
    if kind == 'gtin':
        return product.gtin
    if kind in {'descricao', 'descricao_curta', 'nome_apoio'}:
        return product.descricao
    if kind == 'descricao_complementar':
        return product.descricao_complementar
    if kind == 'ficha_tecnica':
        return product.ficha_tecnica
    if kind == 'caracteristicas':
        return product.caracteristicas
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
    if any([
        product.codigo,
        product.gtin,
        product.descricao,
        product.descricao_complementar,
        product.ficha_tecnica,
        product.caracteristicas,
        product.preco,
        product.estoque,
        product.imagem,
        product.marca,
        product.categoria,
    ]):
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


def _scrape_one(url: str, needed: set[str]) -> tuple[str, FastProductData, float, bool]:
    started = time.perf_counter()
    if needed <= {'url'}:
        return url, _url_only_row(url), time.perf_counter() - started, False

    html = fetch_live(url, timeout=FETCH_TIMEOUT_SECONDS)
    if not html:
        product = FastProductData(url=url)
        return url, product, time.perf_counter() - started, True

    page = parse_product_page(url, html)

    data = {
        'url': url,
        'codigo': '',
        'gtin': '',
        'descricao': '',
        'descricao_complementar': '',
        'ficha_tecnica': '',
        'caracteristicas': '',
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
    if 'descricao' in needed or 'descricao_curta' in needed or 'nome_apoio' in needed:
        data['descricao'] = extract_description(page)
    if 'descricao_complementar' in needed:
        data['descricao_complementar'] = extract_description_complementar(page)
    if 'ficha_tecnica' in needed:
        data['ficha_tecnica'] = extract_ficha_tecnica(page)
    if 'caracteristicas' in needed:
        data['caracteristicas'] = extract_caracteristicas(page)
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

    return url, FastProductData(**data), time.perf_counter() - started, False


def _enhance_products_sequentially(
    products_by_url: list[tuple[str, FastProductData]],
    needed: set[str],
    progress_callback: Callable[[dict], None] | None,
    started_at: float,
) -> tuple[list[FastProductData], int]:
    """Aplica DevTools em fila, com limite baixo, nunca dentro das threads HTTP."""
    if not needed.intersection({'descricao_complementar', 'ficha_tecnica', 'caracteristicas'}):
        return [product for _, product in products_by_url], 0

    enhanced_products: list[FastProductData] = []
    used = 0
    total_candidates = sum(1 for _, product in products_by_url if needs_rendered_fallback(product, needed))

    for url, product in products_by_url:
        if _budget_exceeded(started_at, safety_margin=18.0):
            enhanced_products.append(product)
            continue
        if used < DEVTOOLS_FALLBACK_MAX_PER_RUN and needs_rendered_fallback(product, needed):
            _emit(progress_callback, {
                'stage': 'Reforço DevTools',
                'message': f'Reforçando descrição rica {used + 1}/{min(total_candidates, DEVTOOLS_FALLBACK_MAX_PER_RUN)} sem paralelo.',
                'progress': 0.89,
                'devtools': used,
            })
            enhanced = enhance_with_rendered_page(url, product, needed)
            if enhanced != product:
                product = enhanced
                used += 1
            else:
                used += 1
        enhanced_products.append(product)

    return enhanced_products, used


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


def _run_http_batches(
    *,
    urls: list[str],
    needed: set[str],
    important: set[str],
    progress_callback: Callable[[dict], None] | None,
    started_at: float,
) -> tuple[list[tuple[str, FastProductData]], int, int, int, str, list[dict[str, object]]]:
    products_by_url: list[tuple[str, FastProductData]] = []
    errors = 0
    complete_count = 0
    last_gain_at = 0
    stop_reason = ''
    slow_links: list[dict[str, object]] = []
    total = len(urls)
    processed = 0
    last_emit = time.perf_counter()

    for batch_index, batch_urls in enumerate(_chunks(urls, BATCH_SIZE), start=1):
        if _budget_exceeded(started_at):
            stop_reason = 'Tempo seguro da execução atingido. A origem foi montada com os produtos coletados antes de o Streamlit reiniciar.'
            break

        workers = max(1, min(MAX_WORKERS, len(batch_urls)))
        _emit(progress_callback, {
            'stage': 'Lendo produtos',
            'message': f'Lote {batch_index}: lendo {len(batch_urls)} produto(s). Total lido: {processed}/{total}.',
            'progress': 0.28 + (0.58 * (processed / max(total, 1))),
            'processed': processed,
            'total': total,
            'found': len(products_by_url),
            'complete': complete_count,
            'errors': errors,
            'workers': workers,
        })

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_scrape_one, url, needed): url for url in batch_urls}
            for future in as_completed(futures):
                processed += 1
                try:
                    url, product, elapsed, failed = future.result()
                    if failed:
                        errors += 1
                    if elapsed >= SLOW_LINK_SECONDS:
                        slow_links.append({'url': url, 'seconds': round(elapsed, 2)})
                    if _has_useful_data(product, needed):
                        products_by_url.append((url, product))
                        last_gain_at = processed
                        if _is_complete_product(product, important):
                            complete_count += 1
                except Exception:
                    errors += 1

                should_stop, reason = _should_stop_early(
                    processed=processed,
                    products=[product for _, product in products_by_url],
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
                        'progress': 0.86,
                        'processed': processed,
                        'total': total,
                        'found': len(products_by_url),
                        'complete': complete_count,
                        'errors': errors,
                        'devtools': 0,
                        'slow_links': slow_links[-5:],
                    })
                    break

                now = time.perf_counter()
                if now - last_emit >= 0.5 or processed == total:
                    ratio = processed / max(total, 1)
                    _emit(progress_callback, {
                        'stage': 'Lendo produtos',
                        'message': f'{processed}/{total} produto(s) lido(s).',
                        'progress': 0.28 + (0.58 * ratio),
                        'processed': processed,
                        'total': total,
                        'found': len(products_by_url),
                        'complete': complete_count,
                        'errors': errors,
                        'devtools': 0,
                        'slow_links': slow_links[-5:],
                    })
                    last_emit = now

                if _budget_exceeded(started_at):
                    stop_reason = 'Tempo seguro da execução atingido. A origem foi montada com os produtos coletados antes de o Streamlit reiniciar.'
                    for pending in futures:
                        if not pending.done():
                            pending.cancel()
                    break

        if stop_reason:
            break

    return products_by_url, processed, complete_count, errors, stop_reason, slow_links


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

    urls = urls[:max_products]
    if needed <= {'url'}:
        rows = [_to_contract_row(_url_only_row(url), contract) for url in urls]
        _emit(progress_callback, {
            'stage': 'Pronto',
            'message': f'{len(rows)} link(s) preparados para a origem.',
            'progress': 0.92,
            'processed': len(rows),
            'urls_found': len(urls),
            'total_seconds': round(time.perf_counter() - total_started, 2),
        })
        return _ensure_columns(pd.DataFrame(rows).fillna(''), columns)

    _emit(progress_callback, {
        'stage': 'Lendo produtos',
        'message': f'Lendo até {len(urls)} produto(s) em lotes seguros de {BATCH_SIZE}.',
        'progress': 0.28,
        'processed': 0,
        'total': len(urls),
        'workers': MAX_WORKERS,
    })

    products_by_url, processed, complete_count, errors, stop_reason, slow_links = _run_http_batches(
        urls=urls,
        needed=needed,
        important=important,
        progress_callback=progress_callback,
        started_at=total_started,
    )

    products, rendered_fallbacks = _enhance_products_sequentially(products_by_url, needed, progress_callback, total_started)

    rows = [_to_contract_row(product, contract) for product in products]
    final_message = f'Montando origem com {len(rows)} produto(s).'
    if rendered_fallbacks:
        final_message = f'{final_message} DevTools reforçou {rendered_fallbacks} página(s), em fila.'
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
        'devtools': rendered_fallbacks,
        'slow_links': slow_links[-10:],
        'total_seconds': round(time.perf_counter() - total_started, 2),
    })
    return _ensure_columns(pd.DataFrame(rows).fillna(''), columns)
