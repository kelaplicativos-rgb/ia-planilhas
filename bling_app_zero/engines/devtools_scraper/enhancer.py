from __future__ import annotations

from bling_app_zero.engines.devtools_scraper.browser_engine import fetch_rendered_product_page
from bling_app_zero.engines.fast_site_scraper.models import FastProductData
from bling_app_zero.engines.fast_site_scraper.page_parser import parse_product_page
from bling_app_zero.engines.fast_site_scraper.extractors import (
    extract_brand,
    extract_caracteristicas,
    extract_category,
    extract_description,
    extract_description_complementar,
    extract_ficha_tecnica,
    extract_gtin,
    extract_images,
    extract_price,
    extract_stock,
)

RICH_KINDS = {'descricao_complementar', 'ficha_tecnica', 'caracteristicas'}


def needs_rendered_fallback(product: FastProductData, needed: set[str]) -> bool:
    if not needed.intersection(RICH_KINDS):
        return False
    if 'descricao_complementar' in needed and not product.descricao_complementar:
        return True
    if 'ficha_tecnica' in needed and not product.ficha_tecnica:
        return True
    if 'caracteristicas' in needed and not product.caracteristicas:
        return True
    return False


def enhance_with_rendered_page(url: str, product: FastProductData, needed: set[str]) -> FastProductData:
    rendered = fetch_rendered_product_page(url)
    if not rendered.ok:
        return product

    network_html = ' '.join(rendered.network_payloads)
    html = rendered.html or network_html
    if network_html:
        html = f'{html}\n<script type="application/json">{network_html}</script>'
    page = parse_product_page(url, html)
    if rendered.text:
        page = type(page)(url=page.url, html=page.html, text=rendered.text, jsonld_products=page.jsonld_products)

    data = {
        'url': product.url or url,
        'codigo': product.codigo,
        'gtin': product.gtin,
        'descricao': product.descricao,
        'descricao_complementar': product.descricao_complementar,
        'ficha_tecnica': product.ficha_tecnica,
        'caracteristicas': product.caracteristicas,
        'preco': product.preco,
        'estoque': product.estoque,
        'imagem': product.imagem,
        'marca': product.marca,
        'categoria': product.categoria,
    }

    if 'descricao' in needed or 'descricao_curta' in needed or 'nome_apoio' in needed:
        data['descricao'] = data['descricao'] or extract_description(page)
    if 'descricao_complementar' in needed:
        data['descricao_complementar'] = data['descricao_complementar'] or extract_description_complementar(page)
    if 'ficha_tecnica' in needed:
        data['ficha_tecnica'] = data['ficha_tecnica'] or extract_ficha_tecnica(page)
    if 'caracteristicas' in needed:
        data['caracteristicas'] = data['caracteristicas'] or extract_caracteristicas(page)
    if 'gtin' in needed:
        data['gtin'] = data['gtin'] or extract_gtin(page)
    if 'preco_unitario' in needed or 'preco_custo' in needed:
        data['preco'] = data['preco'] or extract_price(page)
    if 'estoque' in needed:
        data['estoque'] = data['estoque'] or extract_stock(page)
    if 'imagem' in needed:
        data['imagem'] = data['imagem'] or extract_images(page)
    if 'marca' in needed:
        data['marca'] = data['marca'] or extract_brand(page)
    if 'categoria' in needed:
        data['categoria'] = data['categoria'] or extract_category(page)

    if not data['codigo'] and data['gtin']:
        data['codigo'] = data['gtin']

    return FastProductData(**data)
