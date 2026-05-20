from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from io import BytesIO

import pandas as pd
from bs4 import BeautifulSoup

from bling_app_zero.core.text import clean_cell, normalize_key

PRICE_RE = re.compile(r'(?:R\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}|(?:R\$\s*)?\d+\.\d{2}')
SKU_RE = re.compile(r'\b(?:SKU|C[ÓO]D(?:IGO)?|REF(?:ER[ÊE]NCIA)?|ID|CÓD)\s*[:#-]?\s*([A-Za-z0-9._/-]{2,})', re.IGNORECASE)
GTIN_RE = re.compile(r'\b(\d{8}|\d{12}|\d{13}|\d{14})\b')
STOCK_RE = re.compile(r'\b(?:estoque|saldo|qtd|quantidade)\s*[:#-]?\s*(-?\d+(?:[,.]\d+)?)', re.IGNORECASE)
NCM_RE = re.compile(r'\bNCM\s*[:#-]?\s*(\d{7,8})\b', re.IGNORECASE)
URL_RE = re.compile(r'https?://\S+', re.IGNORECASE)


@dataclass(frozen=True)
class RecoveryResult:
    df: pd.DataFrame
    source_type: str
    message: str


def _clean(value: object) -> str:
    return ' '.join(clean_cell(value).replace('\xa0', ' ').split()).strip()


def _key(value: object) -> str:
    return normalize_key(str(value or '')).replace(' ', '_')


def _requested(requested_columns: list[str] | None) -> list[str]:
    return [str(column).strip() for column in (requested_columns or []) if str(column).strip()]


def _target(requested_columns: list[str] | None, signals: tuple[str, ...], default: str) -> str:
    for column in _requested(requested_columns):
        key = _key(column)
        if any(signal in key for signal in signals):
            return column
    return default


def _map_row(row: dict[str, str], requested_columns: list[str] | None) -> dict[str, str]:
    requested = _requested(requested_columns)
    if not requested:
        return row
    out = {column: '' for column in requested}
    pairs = {
        _target(requested, ('nome', 'produto', 'titulo', 'título', 'descricao', 'descrição'), 'Descrição'): row.get('Descrição', ''),
        _target(requested, ('preco', 'preço', 'valor'), 'Preço'): row.get('Preço', ''),
        _target(requested, ('sku', 'codigo', 'código', 'referencia', 'referência'), 'Código/SKU'): row.get('Código/SKU', ''),
        _target(requested, ('gtin', 'ean', 'codigo_de_barras', 'código_de_barras'), 'GTIN/EAN'): row.get('GTIN/EAN', ''),
        _target(requested, ('estoque', 'saldo', 'quantidade', 'qtd'), 'Estoque'): row.get('Estoque', ''),
        _target(requested, ('imagem', 'foto', 'image'), 'Imagem URL'): row.get('Imagem URL', ''),
        _target(requested, ('ncm',), 'NCM'): row.get('NCM', ''),
    }
    for column, value in pairs.items():
        if column in out and value:
            out[column] = value
    return out


def recover_from_plain_text(text: str, requested_columns: list[str] | None = None) -> pd.DataFrame:
    lines = [_clean(line) for line in str(text or '').splitlines() if _clean(line)]
    blocks: list[str] = []
    current: list[str] = []
    for line in lines:
        current.append(line)
        if PRICE_RE.search(line) or len(' '.join(current)) > 420:
            blocks.append(' '.join(current))
            current = []
    if current:
        blocks.append(' '.join(current))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for block in blocks:
        text_block = _clean(block)
        if len(text_block) < 8:
            continue
        price = PRICE_RE.search(text_block)
        sku = SKU_RE.search(text_block)
        gtin = GTIN_RE.search(text_block)
        stock = STOCK_RE.search(text_block)
        ncm = NCM_RE.search(text_block)
        urls = URL_RE.findall(text_block)
        if not any([price, sku, gtin, stock, ncm, urls]) and len(text_block) < 30:
            continue
        name = _clean(text_block[: price.start()]) if price else text_block[:220]
        key = normalize_key(name + '|' + (price.group(0) if price else '') + '|' + (sku.group(1) if sku else ''))
        if key in seen:
            continue
        seen.add(key)
        row = {
            'Descrição': name[:220],
            'Preço': price.group(0) if price else '',
            'Código/SKU': sku.group(1) if sku else '',
            'GTIN/EAN': gtin.group(1) if gtin else '',
            'Estoque': stock.group(1) if stock else '',
            'Imagem URL': '|'.join(urls[:8]),
            'NCM': ncm.group(1) if ncm else '',
            'Texto capturado': text_block[:900],
        }
        rows.append(_map_row(row, requested_columns))
    return pd.DataFrame(rows).fillna('').astype(str) if rows else pd.DataFrame()


def recover_from_html(text: str, requested_columns: list[str] | None = None) -> pd.DataFrame:
    soup = BeautifulSoup(text or '', 'html.parser')
    return recover_from_plain_text(soup.get_text('\n', strip=True), requested_columns)


def _xml_text(node: ET.Element, names: tuple[str, ...]) -> str:
    allowed = {normalize_key(name) for name in names}
    for child in node.iter():
        tag = normalize_key(str(child.tag).split('}')[-1])
        if tag in allowed and child.text:
            return _clean(child.text)
    return ''


def recover_from_xml(text: str, requested_columns: list[str] | None = None) -> pd.DataFrame:
    try:
        root = ET.fromstring(str(text or '').encode('utf-8', errors='ignore'))
    except Exception:
        return recover_from_plain_text(text, requested_columns)
    product_nodes = [node for node in root.iter() if normalize_key(str(node.tag).split('}')[-1]) in {'det', 'produto', 'product', 'item'}]
    if not product_nodes:
        product_nodes = [root]
    rows: list[dict[str, str]] = []
    for node in product_nodes:
        name = _xml_text(node, ('xProd', 'descricao', 'description', 'nome', 'produto'))
        if not name and node is not root:
            continue
        row = {
            'Descrição': name,
            'Preço': _xml_text(node, ('vUnCom', 'vProd', 'preco', 'price', 'valor')),
            'Código/SKU': _xml_text(node, ('cProd', 'sku', 'codigo', 'referencia')),
            'GTIN/EAN': _xml_text(node, ('cEAN', 'cEANTrib', 'gtin', 'ean')),
            'Estoque': _xml_text(node, ('qCom', 'quantidade', 'estoque', 'saldo')),
            'Imagem URL': _xml_text(node, ('imagem', 'image', 'foto')),
            'NCM': _xml_text(node, ('NCM', 'ncm')),
            'Texto capturado': _clean(' '.join(node.itertext()))[:900],
        }
        rows.append(_map_row(row, requested_columns))
    return pd.DataFrame(rows).fillna('').astype(str) if rows else pd.DataFrame()


def recover_from_pdf(file_bytes: bytes, requested_columns: list[str] | None = None) -> pd.DataFrame:
    text = ''
    try:
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(file_bytes))
        text = '\n'.join(page.extract_text() or '' for page in reader.pages[:30])
    except Exception:
        try:
            from PyPDF2 import PdfReader as LegacyPdfReader
            reader = LegacyPdfReader(BytesIO(file_bytes))
            text = '\n'.join(page.extract_text() or '' for page in reader.pages[:30])
        except Exception:
            text = ''
    return recover_from_plain_text(text, requested_columns)


def recover_from_file(file_bytes: bytes, file_name: str, requested_columns: list[str] | None = None) -> RecoveryResult:
    name = str(file_name or '').lower()
    if name.endswith('.pdf'):
        df = recover_from_pdf(file_bytes, requested_columns)
        return RecoveryResult(df, 'PDF', f'{len(df)} linha(s) recuperada(s) do PDF.')
    text = file_bytes.decode('utf-8', errors='ignore')
    if name.endswith(('.xml', '.nfe')):
        df = recover_from_xml(text, requested_columns)
        return RecoveryResult(df, 'XML', f'{len(df)} linha(s) recuperada(s) do XML.')
    if name.endswith(('.html', '.htm')):
        df = recover_from_html(text, requested_columns)
        return RecoveryResult(df, 'HTML', f'{len(df)} linha(s) recuperada(s) do HTML.')
    df = recover_from_plain_text(text, requested_columns)
    return RecoveryResult(df, 'Texto', f'{len(df)} linha(s) recuperada(s) do texto.')


__all__ = ['RecoveryResult', 'recover_from_file', 'recover_from_html', 'recover_from_plain_text', 'recover_from_xml', 'recover_from_pdf']