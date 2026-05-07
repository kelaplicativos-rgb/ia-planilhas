from __future__ import annotations

import re
from typing import Iterable

import pandas as pd
import requests
from bs4 import BeautifulSoup

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


def _text(soup: BeautifulSoup) -> str:
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
    for url in urls:
        u = url.strip()
        low = u.lower()
        if not u or any(bad in low for bad in ['logo', 'sprite', 'placeholder', 'whatsapp', 'facebook']):
            continue
        if u not in cleaned:
            cleaned.append(u)
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
    patterns = [r'(?:SKU|COD|CÓD|REF|REFERÊNCIA)[:\s#-]+([A-Za-z0-9._/-]+)']
    for pattern in patterns:
        match = re.search(pattern, page_text, flags=re.I)
        if match:
            return clean_cell(match.group(1))
    return ''


def scrape_product(url: str, requested_columns: Iterable[str] | None = None) -> dict[str, str]:
    html = _safe_get(url)
    soup = BeautifulSoup(html, 'lxml') if html else BeautifulSoup('', 'lxml')
    page_text = _text(soup)

    base = {
        'URL': url,
        'Código': _sku(page_text),
        'SKU': _sku(page_text),
        'Descrição': _title(soup),
        'Nome': _title(soup),
        'Preço': _price(soup, page_text),
        'Preço unitário (OBRIGATÓRIO)': _price(soup, page_text),
        'Estoque': _stock(page_text),
        'Balanço (OBRIGATÓRIO)': _stock(page_text),
        'URL Imagens': _images(soup),
        'Imagens': _images(soup),
    }

    if requested_columns:
        result: dict[str, str] = {}
        for column in requested_columns:
            col = str(column)
            key = normalize_key(col)
            value = ''
            for base_col, base_value in base.items():
                base_key = normalize_key(base_col)
                if key == base_key or key in base_key or base_key in key:
                    value = base_value
                    break
            result[col] = value
        if 'URL' not in result:
            result['URL'] = url
        if 'Nome apoio' not in result and 'Descrição' not in result and 'Nome' not in result:
            result['Nome apoio'] = base.get('Nome', '')
        return result

    return base


def scrape_urls(urls: list[str], requested_columns: Iterable[str] | None = None) -> pd.DataFrame:
    rows = [scrape_product(url, requested_columns=requested_columns) for url in urls]
    return pd.DataFrame(rows).fillna('')
