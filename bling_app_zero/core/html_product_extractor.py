from __future__ import annotations

import csv
import re
from email import message_from_bytes
from email.message import Message
from email.policy import default as email_default_policy
from typing import Iterable

import pandas as pd
from bs4 import BeautifulSoup

PRODUCT_CARD_SELECTORS = [
    '[data-sku]',
    '[data-id].item',
    '.item[data-id]',
    '.produto',
    '.product',
    '.product-item',
    '.product-card',
    '.card-produto',
    '.card-product',
    'li[class*=product]',
    'div[class*=product]',
    'div[class*=produto]',
]

NAME_ALIASES = (
    'descricao produto',
    'descricao',
    'descrição produto',
    'descrição',
    'titulo',
    'título',
    'nome',
    'produto',
    'product name',
    'name',
)
CODE_ALIASES = (
    'codigo produto',
    'código produto',
    'codigo',
    'código',
    'sku',
    'referencia',
    'referência',
    'modelo',
    'id produto',
)
PRICE_ALIASES = ('preco unitario', 'preço unitário', 'preco', 'preço', 'valor', 'price')
STOCK_ALIASES = ('balanco', 'balanço', 'estoque', 'saldo', 'quantidade', 'qtd', 'stock')
BRAND_ALIASES = ('marca', 'brand')
GTIN_ALIASES = ('gtin', 'ean', 'codigo de barras', 'código de barras')
URL_ALIASES = ('url', 'link', 'href')
IMAGE_ALIASES = ('imagem', 'image', 'foto', 'src')

CANONICAL_COLUMNS = [
    'Codigo produto *',
    'Código produto',
    'SKU',
    'ID Produto',
    'Descrição Produto',
    'Título',
    'Nome',
    'Produto',
    'Balanço (OBRIGATÓRIO)',
    'Estoque',
    'Quantidade extraída do estoque',
    'Preço unitário (OBRIGATÓRIO)',
    'Preço',
    'Preço antigo',
    'Marca',
    'GTIN **',
    'GTIN',
    'URL',
    'Imagem',
    'Texto bruto',
]


def clean_text(value: object) -> str:
    text = str(value or '')
    text = text.replace('\ufeff', '').replace('\xa0', ' ').replace('�', '')
    return ' '.join(text.split()).strip()


def normalize_key(value: object) -> str:
    text = clean_text(value).lower()
    replacements = str.maketrans({
        'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a', 'ä': 'a',
        'é': 'e', 'ê': 'e', 'è': 'e', 'ë': 'e',
        'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
        'ó': 'o', 'ò': 'o', 'õ': 'o', 'ô': 'o', 'ö': 'o',
        'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
        'ç': 'c', 'ñ': 'n',
    })
    text = text.translate(replacements)
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return ' '.join(text.split()).strip()


def _decode_score(text: str) -> int:
    bad = text.count('�') * 12
    bad += len(re.findall(r'Ã.|Â.|Descri..o|T..tulo|Pre..o', text)) * 8
    good = len(re.findall(r'[áàãâéêíóôõúçÁÀÃÂÉÊÍÓÔÕÚÇ]', text))
    product_bonus = len(re.findall(r'produto|sku|estoque|preço|preco|título|titulo|balanço|balanco', text, re.I))
    html_bonus = 20 if '<html' in text.lower() or '<table' in text.lower() else 0
    return html_bonus + product_bonus + good - bad


def decode_html_bytes(data: bytes, preferred_charset: str | None = None) -> str:
    encodings: list[str] = []
    if preferred_charset:
        encodings.append(preferred_charset)
    encodings.extend(['utf-8-sig', 'utf-8', 'cp1252', 'latin1'])

    candidates: list[str] = []
    seen: set[str] = set()
    for encoding in encodings:
        enc = str(encoding or '').strip().lower()
        if not enc or enc in seen:
            continue
        seen.add(enc)
        try:
            candidates.append(data.decode(enc, errors='replace'))
        except Exception:
            continue
    return max(candidates, key=_decode_score) if candidates else data.decode('utf-8', errors='ignore')


def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    out = df.copy().fillna('')
    out.columns = [clean_text(column) or f'Coluna {idx + 1}' for idx, column in enumerate(out.columns)]
    unnamed = [column for column in out.columns if normalize_key(column).startswith('unnamed')]
    if unnamed:
        out = out.drop(columns=unnamed, errors='ignore')
    return out.fillna('').astype(str)


def _best_frame(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    valid = [clean_columns(frame) for frame in frames if isinstance(frame, pd.DataFrame) and not frame.empty and len(frame.columns)]
    if not valid:
        return pd.DataFrame()
    valid.sort(key=lambda df: len(df) * max(1, len(df.columns)), reverse=True)
    return valid[0].reset_index(drop=True)


def _first_column(df: pd.DataFrame, aliases: Iterable[str]) -> str:
    wanted = [normalize_key(alias) for alias in aliases]
    for column in df.columns:
        key = normalize_key(column)
        if key in wanted or any(alias and alias in key for alias in wanted):
            return str(column)
    return ''


def _first_value(row: pd.Series, columns: Iterable[str]) -> str:
    for column in columns:
        if column and column in row.index:
            value = clean_text(row.get(column))
            if value:
                return value
    return ''


def _money_values(text: str) -> list[str]:
    return [clean_text(value) for value in re.findall(r'R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}|R\$\s*\d+,\d{2}', text or '')]


def _money_after_word(text: str, word: str) -> str:
    pattern = rf'{re.escape(word)}\s*(R\$\s*\d{{1,3}}(?:\.\d{{3}})*,\d{{2}}|R\$\s*\d+,\d{{2}})'
    match = re.search(pattern, text or '', flags=re.I)
    return clean_text(match.group(1)) if match else ''


def _choose_price(text: str) -> tuple[str, str]:
    values = _money_values(text)
    if not values:
        return '', ''
    old_price = values[0] if len(values) > 1 and re.search(r'\bde\b', text, re.I) else ''
    preferred = _money_after_word(text, 'por')
    if preferred:
        return preferred, old_price if old_price != preferred else ''
    if len(values) > 1 and old_price:
        return values[1], old_price
    return values[-1], old_price if old_price != values[-1] else ''


def _clean_title(title: str) -> str:
    title = clean_text(title)
    title = re.split(r'\s+R\$\s*\d', title, maxsplit=1)[0]
    title = re.sub(r'\b(olhar|comprar|no boleto|com pix|com picpay|ver produto)\b.*$', '', title, flags=re.I)
    return clean_text(title)


def _stock_quantity(value: str) -> str:
    text = clean_text(value)
    match = re.search(r'(\d+(?:[\.,]\d+)?)\s*(?:unidades?|unds?|pcs?|peças?)', text, flags=re.I)
    return clean_text(match.group(1)) if match else ''


def normalize_product_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = clean_columns(df)
    if out.empty:
        return out

    name_col = _first_column(out, NAME_ALIASES)
    code_col = _first_column(out, CODE_ALIASES)
    price_col = _first_column(out, PRICE_ALIASES)
    stock_col = _first_column(out, STOCK_ALIASES)
    brand_col = _first_column(out, BRAND_ALIASES)
    gtin_col = _first_column(out, GTIN_ALIASES)
    url_col = _first_column(out, URL_ALIASES)
    image_col = _first_column(out, IMAGE_ALIASES)

    original_columns = [str(column) for column in out.columns]
    rows: list[dict[str, str]] = []
    for _, row in out.iterrows():
        name = _first_value(row, [name_col, 'Descrição Produto', 'Título', 'Titulo', 'Nome', 'Produto', 'Descrição', 'Descricao'])
        code = _first_value(row, [code_col, 'Codigo produto *', 'Código produto', 'Codigo produto', 'SKU', 'Código', 'Codigo'])
        price = _first_value(row, [price_col, 'Preço unitário (OBRIGATÓRIO)', 'Preço unitário', 'Preco unitario', 'Preço', 'Preco'])
        stock = _first_value(row, [stock_col, 'Balanço (OBRIGATÓRIO)', 'Balanço', 'Balanco', 'Estoque', 'Saldo', 'Quantidade'])
        brand = _first_value(row, [brand_col, 'Marca'])
        gtin = _first_value(row, [gtin_col, 'GTIN', 'GTIN **', 'EAN'])
        url = _first_value(row, [url_col, 'URL', 'Link'])
        image = _first_value(row, [image_col, 'Imagem', 'Foto'])

        normalized: dict[str, str] = {
            'Codigo produto *': code,
            'Código produto': code,
            'SKU': code,
            'Descrição Produto': name,
            'Título': name,
            'Nome': name,
            'Produto': name,
            'Balanço (OBRIGATÓRIO)': stock,
            'Estoque': stock,
            'Quantidade extraída do estoque': _stock_quantity(stock),
            'Preço unitário (OBRIGATÓRIO)': price,
            'Preço': price,
            'Marca': brand,
            'GTIN **': gtin,
            'GTIN': gtin,
            'URL': url,
            'Imagem': image,
        }
        for column in original_columns:
            normalized[column] = clean_text(row.get(column))
        rows.append(normalized)

    normalized_df = pd.DataFrame(rows).fillna('').astype(str)
    ordered = [column for column in CANONICAL_COLUMNS if column in normalized_df.columns]
    ordered.extend([column for column in normalized_df.columns if column not in ordered])
    return normalized_df[ordered].reset_index(drop=True)


def extract_tables_from_html(html_text: str) -> list[pd.DataFrame]:
    soup = BeautifulSoup(html_text or '', 'html.parser')
    frames: list[pd.DataFrame] = []
    for table in soup.find_all('table'):
        rows: list[list[str]] = []
        for tr in table.find_all('tr'):
            cells = tr.find_all(['th', 'td'])
            row = [clean_text(cell.get_text(' ', strip=True)) for cell in cells]
            if any(row):
                rows.append(row)
        if len(rows) < 2:
            continue
        width = max(len(row) for row in rows)
        normalized_rows = [row + [''] * (width - len(row)) for row in rows]
        columns = [clean_text(value) or f'Coluna {idx + 1}' for idx, value in enumerate(normalized_rows[0])]
        frame = pd.DataFrame(normalized_rows[1:], columns=columns).fillna('').astype(str)
        if not frame.empty:
            frames.append(normalize_product_frame(frame))
    return frames


def extract_product_cards_from_html(html_text: str) -> pd.DataFrame:
    soup = BeautifulSoup(html_text or '', 'html.parser')
    candidates = []
    for selector in PRODUCT_CARD_SELECTORS:
        candidates.extend(soup.select(selector))

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in candidates:
        text = clean_text(card.get_text(' ', strip=True))
        if len(text) < 10:
            continue

        link = card.find('a', href=True)
        img = card.find('img')
        title_node = card.select_one('h1, h2, h3.produto, h3[title], h3, .title, .titulo, .nome, [class*=title], [class*=titulo]')

        title = ''
        if title_node:
            title = clean_text(title_node.get('title') or title_node.get_text(' ', strip=True))
        if not title and img:
            title = clean_text(img.get('alt') or img.get('title'))
        if not title and link:
            title = clean_text(link.get('title') or link.get_text(' ', strip=True))
        if not title:
            title = text.split(' R$')[0]
        title = _clean_title(title)

        price, old_price = _choose_price(text)
        sku = clean_text(card.get('data-sku')) or clean_text(card.get('data-id'))
        product_id = clean_text(card.get('data-id'))
        url = clean_text(link.get('href')) if link else ''
        image_url = clean_text(img.get('src') or img.get('data-src') or '') if img else ''

        if not title and not sku:
            continue
        key = f'{sku}|{title}|{url}'
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            'Codigo produto *': sku,
            'Código produto': sku,
            'SKU': sku,
            'ID Produto': product_id,
            'Descrição Produto': title,
            'Título': title,
            'Nome': title,
            'Produto': title,
            'Preço unitário (OBRIGATÓRIO)': price,
            'Preço': price,
            'Preço antigo': old_price,
            'URL': url,
            'Imagem': image_url,
            'Texto bruto': text[:1200],
        })
    return normalize_product_frame(pd.DataFrame(rows).fillna('')) if rows else pd.DataFrame()


def _fallback_text_table(html_text: str) -> pd.DataFrame:
    text = BeautifulSoup(html_text or '', 'html.parser').get_text('\n')
    lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
    rows = [[clean_text(part) for part in line.split('\t')] for line in lines if '\t' in line]
    rows = [row for row in rows if len(row) >= 2]
    if len(rows) >= 2:
        width = max(len(row) for row in rows)
        normalized_rows = [row + [''] * (width - len(row)) for row in rows]
        columns = [clean_text(value) or f'Coluna {idx + 1}' for idx, value in enumerate(normalized_rows[0])]
        return normalize_product_frame(pd.DataFrame(normalized_rows[1:], columns=columns))
    return pd.DataFrame([{'Texto HTML': '\n'.join(lines[:800])}]) if lines else pd.DataFrame()


def read_html_product_text(html_text: str) -> pd.DataFrame:
    table_frames = extract_tables_from_html(html_text)
    if table_frames:
        return _best_frame(table_frames)
    product_cards = extract_product_cards_from_html(html_text)
    if isinstance(product_cards, pd.DataFrame) and not product_cards.empty:
        return product_cards
    return _fallback_text_table(html_text)


def read_html_product_bytes(data: bytes) -> pd.DataFrame:
    return read_html_product_text(decode_html_bytes(data))


def _message_part_to_text(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        raw_payload = part.get_payload()
        return raw_payload if isinstance(raw_payload, str) else ''
    return decode_html_bytes(payload, part.get_content_charset())


def extract_html_parts_from_mhtml(data: bytes) -> list[str]:
    html_parts: list[str] = []
    try:
        message = message_from_bytes(data, policy=email_default_policy)
    except Exception:
        text = decode_html_bytes(data)
        return [text] if '<html' in text.lower() or '<table' in text.lower() else []

    if message.is_multipart():
        for part in message.walk():
            content_type = str(part.get_content_type() or '').lower()
            if content_type == 'text/html':
                html_text = _message_part_to_text(part)
                if html_text.strip():
                    html_parts.append(html_text)
    else:
        content_type = str(message.get_content_type() or '').lower()
        text = _message_part_to_text(message)
        if content_type == 'text/html' or '<html' in text.lower() or '<table' in text.lower():
            html_parts.append(text)

    if not html_parts:
        fallback = decode_html_bytes(data)
        if '<html' in fallback.lower() or '<table' in fallback.lower():
            html_parts.append(fallback)
    return html_parts


def read_mhtml_product_bytes(data: bytes) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for html_text in extract_html_parts_from_mhtml(data):
        frame = read_html_product_text(html_text)
        if isinstance(frame, pd.DataFrame) and not frame.empty:
            frames.append(frame)
    return _best_frame(frames)


__all__ = [
    'clean_columns',
    'clean_text',
    'decode_html_bytes',
    'extract_html_parts_from_mhtml',
    'extract_product_cards_from_html',
    'extract_tables_from_html',
    'normalize_key',
    'normalize_product_frame',
    'read_html_product_bytes',
    'read_html_product_text',
    'read_mhtml_product_bytes',
]
