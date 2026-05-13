from __future__ import annotations

import re
from io import BytesIO
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup

NOISE_COLUMNS = {'', 'ações', 'acao', 'ação', 'editar', 'excluir', 'selecionar', '#'}
PRICE_RE = re.compile(r'(?:R\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}|(?:R\$\s*)?\d+\.\d{2}')
SKU_RE = re.compile(r'\b(?:SKU|C[ÓO]D(?:IGO)?|REF(?:ER[ÊE]NCIA)?|ID)\s*[:#-]?\s*([A-Za-z0-9._/-]{2,})', re.IGNORECASE)
GTIN_RE = re.compile(r'\b(\d{8}|\d{12}|\d{13}|\d{14})\b')
STOCK_RE = re.compile(r'\b(?:estoque|saldo|qtd|quantidade)\s*[:#-]?\s*(-?\d+(?:[,.]\d+)?)', re.IGNORECASE)


def _clean_text(value: Any) -> str:
    text = ' '.join(str(value or '').replace('\xa0', ' ').split())
    return text.strip()


def _normalize_header(value: str, index: int) -> str:
    text = _clean_text(value)
    if not text or text.lower() in NOISE_COLUMNS:
        return f'Coluna {index + 1}'
    return text


def _dedupe_columns(columns: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out: list[str] = []
    for column in columns:
        base = _clean_text(column) or 'Coluna'
        count = seen.get(base, 0)
        seen[base] = count + 1
        out.append(base if count == 0 else f'{base} {count + 1}')
    return out


def _read_uploaded_table(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    name = str(file_name or '').lower()
    buffer = BytesIO(file_bytes)
    if name.endswith('.csv'):
        try:
            return pd.read_csv(buffer, sep=';', dtype=str).fillna('')
        except Exception:
            buffer.seek(0)
            return pd.read_csv(buffer, dtype=str).fillna('')
    if name.endswith(('.xlsx', '.xls', '.xlsm', '.xlsb')):
        return pd.read_excel(buffer, dtype=str).fillna('')
    return pd.DataFrame()


def _extract_tables_from_html(html: str) -> list[pd.DataFrame]:
    soup = BeautifulSoup(html or '', 'html.parser')
    frames: list[pd.DataFrame] = []
    for table in soup.find_all('table'):
        rows: list[list[str]] = []
        for tr in table.find_all('tr'):
            cells = tr.find_all(['th', 'td'])
            row = [_clean_text(cell.get_text(' ', strip=True)) for cell in cells]
            if any(row):
                rows.append(row)
        if len(rows) < 2:
            continue
        width = max(len(row) for row in rows)
        normalized_rows = [row + [''] * (width - len(row)) for row in rows]
        header_candidates = normalized_rows[0]
        has_header = any(cell for cell in header_candidates)
        if has_header:
            columns = [_normalize_header(cell, idx) for idx, cell in enumerate(header_candidates)]
            data = normalized_rows[1:]
        else:
            columns = [f'Coluna {idx + 1}' for idx in range(width)]
            data = normalized_rows
        frame = pd.DataFrame(data, columns=_dedupe_columns(columns)).fillna('')
        frame = frame.loc[:, [col for col in frame.columns if str(col).strip().lower() not in NOISE_COLUMNS]]
        if not frame.empty:
            frames.append(frame)
    return frames


def _candidate_product_nodes(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html or '', 'html.parser')
    selectors = [
        '[class*=product]', '[class*=produto]', '[class*=item]', '[class*=card]',
        '[data-product]', '[data-produto]', '[data-sku]', '[data-id]'
    ]
    nodes = []
    seen_ids: set[int] = set()
    for selector in selectors:
        for node in soup.select(selector):
            ident = id(node)
            if ident in seen_ids:
                continue
            seen_ids.add(ident)
            text = _clean_text(node.get_text(' ', strip=True))
            if len(text) < 8:
                continue
            has_price = bool(PRICE_RE.search(text))
            has_product_signal = any(word in text.lower() for word in ('preço', 'preco', 'estoque', 'sku', 'cód', 'codigo', 'produto'))
            if not has_price and not has_product_signal:
                continue
            image = ''
            img = node.find('img')
            if img:
                image = _clean_text(img.get('src') or img.get('data-src') or '')
            link = ''
            a = node.find('a')
            if a:
                link = _clean_text(a.get('href') or '')
            price_match = PRICE_RE.search(text)
            sku_match = SKU_RE.search(text)
            gtin_match = GTIN_RE.search(text)
            stock_match = STOCK_RE.search(text)
            name = text
            if price_match:
                name = _clean_text(text[:price_match.start()]) or text
            nodes.append({
                'Descrição': name[:260],
                'Preço': price_match.group(0) if price_match else '',
                'Código/SKU': sku_match.group(1) if sku_match else _clean_text(node.get('data-sku') or node.get('data-id') or ''),
                'GTIN/EAN': gtin_match.group(1) if gtin_match else '',
                'Estoque': stock_match.group(1) if stock_match else '',
                'Imagem URL': image,
                'URL': link,
                'Texto capturado': text[:900],
            })
    return nodes


def _best_table(frames: list[pd.DataFrame]) -> pd.DataFrame:
    if not frames:
        return pd.DataFrame()
    scored: list[tuple[int, pd.DataFrame]] = []
    for frame in frames:
        columns_text = ' '.join(map(str, frame.columns)).lower()
        score = len(frame) * max(1, len(frame.columns))
        for token in ('produto', 'descri', 'nome', 'preço', 'preco', 'sku', 'código', 'codigo', 'estoque', 'saldo'):
            if token in columns_text:
                score += 50
        scored.append((score, frame))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1].copy().fillna('')


def capture_authenticated_source_from_html(html: str, *, operation: str = 'cadastro', requested_columns: list[str] | None = None) -> pd.DataFrame:
    frames = _extract_tables_from_html(html)
    table_df = _best_table(frames)
    if isinstance(table_df, pd.DataFrame) and not table_df.empty:
        return table_df.fillna('').astype(str)

    nodes = _candidate_product_nodes(html)
    if nodes:
        return pd.DataFrame(nodes).fillna('').astype(str)

    _ = operation
    _ = requested_columns
    return pd.DataFrame()


def capture_authenticated_source_from_upload(file_bytes: bytes, file_name: str, *, operation: str = 'cadastro', requested_columns: list[str] | None = None) -> pd.DataFrame:
    name = str(file_name or '').lower()
    if name.endswith(('.csv', '.xlsx', '.xls', '.xlsm', '.xlsb')):
        return _read_uploaded_table(file_bytes, file_name).fillna('').astype(str)
    text = file_bytes.decode('utf-8', errors='ignore')
    return capture_authenticated_source_from_html(text, operation=operation, requested_columns=requested_columns)


__all__ = [
    'capture_authenticated_source_from_html',
    'capture_authenticated_source_from_upload',
]
