from __future__ import annotations

import time

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.debug import add_debug
from bling_app_zero.engines.fast_site_scraper.constants import DESCRIPTION_TRIGGER_KINDS, RESPONSIBLE_FILE
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
from bling_app_zero.engines.fast_site_scraper.progress import inside_executor_thread


def url_only_row(url: str) -> FastProductData:
    return FastProductData(url=url)


def has_useful_data(product: FastProductData, needed: set[str]) -> bool:
    if any([
        product.id_produto, product.codigo, product.gtin, product.descricao, product.descricao_complementar,
        product.ficha_tecnica, product.caracteristicas, product.preco, product.estoque,
        product.imagem, product.marca, product.categoria,
    ]):
        return True
    return 'url' in needed and bool(product.url)


def log_rich_description_result(url: str, product: FastProductData, needed: set[str]) -> None:
    if inside_executor_thread():
        return
    if 'descricao_complementar' not in needed:
        return
    length = len(str(product.descricao_complementar or '').strip())
    status = 'vazia' if length == 0 else 'curta' if length < 80 else 'ok'
    details = {
        'url': url,
        'descricao_len': len(str(product.descricao or '').strip()),
        'descricao_complementar_len': length,
        'ficha_tecnica_len': len(str(product.ficha_tecnica or '').strip()),
        'caracteristicas_len': len(str(product.caracteristicas or '').strip()),
        'status': status,
        'responsible_file': RESPONSIBLE_FILE,
    }
    add_audit_event('site_rich_description_extracted', area='SITE', status='OK' if status == 'ok' else 'INFO', details=details)
    if status != 'ok':
        add_debug(
            f'Descrição complementar {status} na captura por site.',
            origin='SITE_DESCRICAO_RICA',
            level='WARN' if status == 'vazia' else 'INFO',
            file_name=RESPONSIBLE_FILE,
            details=details,
        )


def scrape_one(url: str, needed: set[str]) -> tuple[str, FastProductData, float, bool]:
    started = time.perf_counter()
    if needed <= {'url'}:
        return url, url_only_row(url), time.perf_counter() - started, False

    html = fetch_live(url, timeout=4)
    if not html:
        return url, FastProductData(url=url), time.perf_counter() - started, True

    page = parse_product_page(url, html)
    data = {
        'url': url,
        'id_produto': '',
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
        data['id_produto'] = data['codigo']
    if 'gtin' in needed:
        data['gtin'] = extract_gtin(page)
    if needed.intersection(DESCRIPTION_TRIGGER_KINDS):
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

    product = FastProductData(**data)
    log_rich_description_result(url, product, needed)
    return url, product, time.perf_counter() - started, False


__all__ = ['has_useful_data', 'log_rich_description_result', 'scrape_one', 'url_only_row']
