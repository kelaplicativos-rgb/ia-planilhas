from __future__ import annotations

import json
import re
import zipfile
from io import BytesIO
from typing import Any

import pandas as pd

from bling_app_zero.core.html_product_extractor import (
    clean_columns,
    clean_text,
    read_html_product_bytes,
    read_mhtml_product_bytes,
)

RESPONSIBLE_FILE = 'bling_app_zero/core/protected_supplier_zip_reader.py'
IMAGE_RE = re.compile(r'\.(?:jpg|jpeg|png|webp|gif)(?:\?|$)', re.I)
NUMERIC_RE = re.compile(r'^-?\d+(?:[,.]\d+)?$')

FIELD_MAP = {
    'product_id': 'product_id',
    'sku': 'SKU',
    'imagens': 'Imagem URL',
    'titulo': 'Título',
    'descricao': 'Descrição complementar',
    'modelo': 'Modelo',
    'marca': 'Marca',
    'categoria': 'Categoria',
    'preco_de': 'Preço De',
    'preco_final': 'Preço Final',
    'disponibilidade': 'Disponibilidade',
    'estoque': 'Estoque',
    'ean': 'EAN',
    'ncm': 'NCM',
    'peso': 'Peso kg',
    'medidas': 'Medidas cm',
    'palavras_chave': 'Palavras-Chave',
    'titulos_sugeridos': 'Títulos Sugeridos',
    'badges': 'Badges',
    'integracao': 'Integração',
    'anatel': 'Anatel',
    'inmetro': 'Inmetro',
    'video_url': 'Vídeo URL',
    'detalhe_url': 'Detalhe URL',
}


def _clean(value: object) -> str:
    return clean_text(value)


def _norm(value: object) -> str:
    return re.sub(r'[^a-z0-9]+', '', _clean(value).casefold())


def _is_numeric_stock(value: object) -> bool:
    text = _clean(value).replace(',', '.')
    return bool(NUMERIC_RE.match(text))


def _clean_stock(value: object) -> str:
    text = _clean(value).replace(',', '.')
    return text if _is_numeric_stock(text) else ''


def _clean_images(value: object) -> str:
    urls: list[str] = []
    seen: set[str] = set()
    for part in re.split(r'[|,]\s*|\s{2,}', _clean(value)):
        url = part.strip()
        if not url or '#' in url or not IMAGE_RE.search(url):
            continue
        lowered = url.casefold()
        if any(token in lowered for token in ('logo', 'favicon', 'sprite', 'placeholder', 'mercado-livre', 'whatsapp', 'facebook', 'instagram', 'youtube')):
            continue
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return '|'.join(urls)


def _candidate_keys(row: dict[str, object]) -> list[str]:
    keys: list[str] = []
    for name in ('product_id', 'sku', 'SKU', 'Código produto', 'Codigo produto *', 'Modelo', 'modelo'):
        value = _clean(row.get(name, ''))
        if value:
            keys.append(_norm(value))
    return [key for key in keys if key]


def _frame_stock_lookup(frame: pd.DataFrame) -> dict[str, str]:
    lookup: dict[str, str] = {}
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return lookup
    clean = clean_columns(frame).fillna('').astype(str)
    columns = {str(col).strip(): str(col).strip() for col in clean.columns}
    stock_cols = [col for col in clean.columns if 'estoque' in _norm(col) or 'stock' in _norm(col)]
    key_cols = [col for col in clean.columns if _norm(col) in {'sku', 'productid', 'produtoid', 'idproduto', 'modelo'} or 'codigo' in _norm(col)]
    if not stock_cols or not key_cols:
        return lookup
    for _, record in clean.iterrows():
        stock = ''
        for col in stock_cols:
            stock = _clean_stock(record.get(col, ''))
            if stock:
                break
        if not stock:
            continue
        for col in key_cols:
            key = _norm(record.get(col, ''))
            if key:
                lookup.setdefault(key, stock)
    return lookup


def _read_table_frame_from_zip_entry(name: str, data: bytes) -> pd.DataFrame:
    lower = str(name or '').lower()
    try:
        if lower.endswith(('.mht', '.mhtml')):
            return read_mhtml_product_bytes(data)
        if lower.endswith(('.html', '.htm')):
            return read_html_product_bytes(data)
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame()


def _load_complete_records(archive: zipfile.ZipFile) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for info in archive.infolist():
        if info.is_dir() or not info.filename.lower().endswith('_mapeiaai_completo.json'):
            continue
        try:
            payload = json.loads(archive.read(info).decode('utf-8'))
        except Exception:
            continue
        if isinstance(payload, list):
            records.extend([item for item in payload if isinstance(item, dict)])
        elif isinstance(payload, dict):
            inner = payload.get('records') or payload.get('data') or []
            if isinstance(inner, list):
                records.extend([item for item in inner if isinstance(item, dict)])
    return records


def _build_stock_lookup(archive: zipfile.ZipFile) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for info in archive.infolist():
        if info.is_dir():
            continue
        lower = info.filename.lower()
        if '_mapeiaai_completo' in lower:
            continue
        if not lower.endswith(('.html', '.htm', '.mht', '.mhtml')):
            continue
        frame = _read_table_frame_from_zip_entry(info.filename, archive.read(info))
        lookup.update(_frame_stock_lookup(frame))
    return lookup


def _normalize_complete_row(row: dict[str, object], stock_lookup: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for source, target in FIELD_MAP.items():
        normalized[target] = _clean(row.get(source, ''))

    numeric_stock = ''
    for key in _candidate_keys(row):
        numeric_stock = stock_lookup.get(key, '')
        if numeric_stock:
            break
    if numeric_stock:
        normalized['Estoque'] = numeric_stock
    elif _is_numeric_stock(normalized.get('Estoque', '')):
        normalized['Estoque'] = _clean_stock(normalized.get('Estoque', ''))

    normalized['Imagem URL'] = _clean_images(normalized.get('Imagem URL', ''))
    if normalized['Imagem URL']:
        normalized.setdefault('Imagens', normalized['Imagem URL'])
        normalized.setdefault('Imagem', normalized['Imagem URL'].split('|')[0])
        normalized.setdefault('URL Imagem', normalized['Imagem URL'].split('|')[0])
    return normalized


def read_protected_supplier_zip_bytes(data: bytes) -> pd.DataFrame:
    """Lê ZIP completo do coletor desktop e corrige estoque/imagens antes do mapeamento."""
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            records = _load_complete_records(archive)
            if not records:
                return pd.DataFrame()
            stock_lookup = _build_stock_lookup(archive)
            rows = [_normalize_complete_row(row, stock_lookup) for row in records]
            return clean_columns(pd.DataFrame(rows).fillna(''))
    except Exception:
        return pd.DataFrame()


__all__ = ['read_protected_supplier_zip_bytes']
