from __future__ import annotations

import re
from datetime import date
from typing import Iterable

import pandas as pd
import requests
from bs4 import BeautifulSoup

from bling_app_zero.core.column_contract import RequestedField, build_contract, kinds_from_contract
from bling_app_zero.core.gtin import clean_gtin
from bling_app_zero.core.text import clean_cell, normalize_key

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; IA-Planilhas-Bling/3.0; +https://github.com/kelaplicativos-rgb/ia-planilhas)'
}


def split_urls(raw: str) -> list[str]:
    lines = re.split(r'[\n,;]+', str(raw or ''))
    return [line.strip() for line in lines if line.strip().startswith(('http://', 'https://'))]


def _safe_get(url: str) -> str:
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        return response.text or ''
    except Exception:
        return ''


def _make_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html or '', 'html.parser')


def _page_text(soup: BeautifulSoup) -> str:
    return clean_cell(soup.get_text(' ', strip=True))


def _title(soup: BeautifulSoup) -> str:
    og = soup.find('meta', property='og:title')
    if og and og.get('content'):
        return clean_cell(og.get('content'))
    if soup.title and soup.title.string:
        return clean_cell(soup.title.string)
    h1 = soup.find('h1')
    return clean_cell(h1.get_text(' ', strip=True)) if h1 else ''


def _price(soup: BeautifulSoup, page_text: str) -> str:
    meta = soup.find('meta', property='product:price:amount')
    if meta and meta.get('content'):
        return clean_cell(meta.get('content'))
    match = re.search(r'R\$\s*([0-9\.]+,[0-9]{2})', page_text)
    return match.group(1) if match else ''


def _images(soup: BeautifulSoup) -> str:
    urls: list[str] = []
    for meta in soup.find_all('meta'):
        prop = str(meta.get('property') or meta.get('name') or '').lower()
        if 'image' in prop and meta.get('content'):
            urls.append(str(meta.get('content')))
    for img in soup.find_all('img'):
        src = img.get('src') or img.get('data-src') or img.get('data-lazy')
        if src:
            urls.append(str(src))
    cleaned: list[str] = []
    for raw_url in urls:
        image_url = raw_url.strip()
        low = image_url.lower()
        if not image_url or any(bad in low for bad in ['logo', 'sprite', 'placeholder', 'whatsapp', 'facebook']):
            continue
        if image_url not in cleaned:
            cleaned.append(image_url)
        if len(cleaned) >= 12:
            break
    return '|'.join(cleaned)


def _stock(page_text: str) -> str:
    key = normalize_key(page_text)
    if any(term in key for term in ['sem estoque', 'indisponivel', 'esgotado', 'fora de estoque']):
        return '0'
    if any(term in key for term in ['comprar', 'adicionar ao carrinho', 'em estoque', 'disponivel']):
        return '1'
    return ''


def _sku(page_text: str) -> str:
    patterns = [
        r'(?:SKU|COD|CÓD|REF|REFERÊNCIA)[:\s#-]+([A-Za-z0-9._/-]+)',
        r'(?:Código|Codigo)[:\s#-]+([A-Za-z0-9._/-]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, page_text, flags=re.I)
        if match:
            return clean_cell(match.group(1))
    return ''


def _gtin(page_text: str) -> str:
    patterns = [
        r'(?:GTIN|EAN|Código de barras|Codigo de barras|Barcode)[:\s#-]+([0-9 .-]{8,20})',
        r'\b(\d{8}|\d{12}|\d{13}|\d{14})\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, page_text, flags=re.I)
        if match:
            value = clean_gtin(match.group(1))
            if value:
                return value
    return ''


def _brand(soup: BeautifulSoup, page_text: str) -> str:
    meta = soup.find('meta', property='product:brand') or soup.find('meta', attrs={'name': 'brand'})
    if meta and meta.get('content'):
        return clean_cell(meta.get('content'))
    match = re.search(r'(?:Marca|Brand)[:\s-]+([A-Za-z0-9 Á-ú._/-]{2,40})', page_text, flags=re.I)
    return clean_cell(match.group(1)) if match else ''


def _category(soup: BeautifulSoup, page_text: str) -> str:
    crumbs: list[str] = []
    for selector in ['breadcrumb', 'breadcrumbs']:
        for item in soup.find_all(class_=lambda value: value and selector in str(value).lower()):
            text = clean_cell(item.get_text(' > ', strip=True))
            if text:
                crumbs.append(text)
    if crumbs:
        return crumbs[0]
    meta = soup.find('meta', property='product:category')
    if meta and meta.get('content'):
        return clean_cell(meta.get('content'))
    return ''


def _build_cache(url: str, contract: list[RequestedField], soup: BeautifulSoup, page_text: str) -> dict[str, str]:
    kinds = kinds_from_contract(contract)
    cache: dict[str, str] = {'url': url}

    if {'codigo', 'id_produto', 'nome_apoio'} & kinds:
        cache['codigo'] = _sku(page_text)
        cache['id_produto'] = _sku(page_text)

    if {'descricao', 'nome_apoio'} & kinds:
        cache['descricao'] = _title(soup)
        cache['nome_apoio'] = cache['descricao']

    if {'preco_unitario', 'preco_custo'} & kinds:
        price = _price(soup, page_text)
        cache['preco_unitario'] = price
        cache['preco_custo'] = price

    if 'estoque' in kinds:
        cache['estoque'] = _stock(page_text)

    if 'gtin' in kinds:
        cache['gtin'] = _gtin(page_text)

    if 'imagem' in kinds:
        cache['imagem'] = _images(soup)

    if 'marca' in kinds:
        cache['marca'] = _brand(soup, page_text)

    if 'categoria' in kinds:
        cache['categoria'] = _category(soup, page_text)

    if 'data' in kinds:
        cache['data'] = date.today().isoformat()

    if 'observacao' in kinds:
        cache['observacao'] = ''

    return cache


def _value_for_field(field: RequestedField, cache: dict[str, str]) -> str:
    if field.kind == 'custom':
        return ''
    return cache.get(field.kind, '')


def scrape_product(url: str, requested_columns: Iterable[str] | None = None) -> dict[str, str]:
    contract = build_contract(requested_columns or [])

    html = _safe_get(url)
    soup = _make_soup(html)
    page_text = _page_text(soup)

    if contract:
        cache = _build_cache(url=url, contract=contract, soup=soup, page_text=page_text)
        row = {field.original: _value_for_field(field, cache) for field in contract}
        if 'URL' not in row and not any(normalize_key(col) == 'url' for col in row):
            row['URL'] = url
        if not any(normalize_key(col) in {'nome apoio', 'descricao produto', 'descricao', 'nome'} for col in row):
            row['Nome apoio'] = cache.get('nome_apoio') or _title(soup)
        return row

    title = _title(soup)
    price = _price(soup, page_text)
    stock = _stock(page_text)
    sku = _sku(page_text)
    images = _images(soup)

    return {
        'URL': url,
        'Código': sku,
        'SKU': sku,
        'GTIN': _gtin(page_text),
        'Descrição': title,
        'Nome': title,
        'Preço': price,
        'Preço unitário (OBRIGATÓRIO)': price,
        'Estoque': stock,
        'Balanço (OBRIGATÓRIO)': stock,
        'URL Imagens': images,
        'Imagens': images,
        'Marca': _brand(soup, page_text),
        'Categoria': _category(soup, page_text),
    }


def scrape_urls(urls: list[str], requested_columns: Iterable[str] | None = None) -> pd.DataFrame:
    rows = [scrape_product(url, requested_columns=requested_columns) for url in urls]
    return pd.DataFrame(rows).fillna('')
