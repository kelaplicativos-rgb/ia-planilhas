from __future__ import annotations

import csv
import re
import xml.etree.ElementTree as ET
from email import message_from_bytes
from email.message import Message
from email.policy import default as email_default_policy
from io import BytesIO, StringIO
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None

SPREADSHEET_EXTENSIONS = ('.xlsx', '.xls', '.xlsm', '.xlsb')
TEXT_EXTENSIONS = ('.txt', '.tsv')
HTML_EXTENSIONS = ('.html', '.htm')
MHTML_EXTENSIONS = ('.mht', '.mhtml')
SUPPORTED_SUPPLIER_EXTENSIONS = SPREADSHEET_EXTENSIONS + ('.csv', '.xml', '.pdf') + TEXT_EXTENSIONS + HTML_EXTENSIONS + MHTML_EXTENSIONS

NFE_ITEM_TAGS = {'det'}
NFE_PRODUCT_TAGS = {'prod'}
COMMON_ITEM_TAGS = {'item', 'produto', 'product', 'det', 'row', 'linha'}


def _decode_bytes(data: bytes) -> str:
    for encoding in ('utf-8-sig', 'utf-8', 'latin1', 'cp1252'):
        try:
            return data.decode(encoding)
        except Exception:
            continue
    return data.decode('utf-8', errors='ignore')


def _detect_separator(text: str) -> str:
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
        return dialect.delimiter
    except Exception:
        candidates = [',', ';', '\t', '|']
        return max(candidates, key=lambda sep: sample.count(sep))


def _clean(value: object) -> str:
    return ' '.join(str(value or '').replace('\ufeff', '').replace('\xa0', ' ').split()).strip()


def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy().fillna('')
    out.columns = [_clean(c) or f'Coluna {idx + 1}' for idx, c in enumerate(out.columns)]
    unnamed = [c for c in out.columns if not c or c.lower().startswith('unnamed')]
    if unnamed:
        out = out.drop(columns=unnamed, errors='ignore')
    return out.fillna('').astype(str)


def _best_frame(frames: list[pd.DataFrame]) -> pd.DataFrame:
    valid = [_clean_columns(frame) for frame in frames if isinstance(frame, pd.DataFrame) and not frame.empty and len(frame.columns)]
    if not valid:
        return pd.DataFrame()
    valid.sort(key=lambda df: len(df) * max(1, len(df.columns)), reverse=True)
    return valid[0].fillna('').astype(str)


def _read_csv_bytes(data: bytes) -> pd.DataFrame:
    text = _decode_bytes(data)
    sep = _detect_separator(text)
    return _clean_columns(pd.read_csv(StringIO(text), sep=sep, dtype=str).fillna(''))


def _read_text_bytes(data: bytes) -> pd.DataFrame:
    text = _decode_bytes(data)
    if '\t' in text[:8192]:
        return _clean_columns(pd.read_csv(StringIO(text), sep='\t', dtype=str).fillna(''))
    rows = [[_clean(part) for part in re.split(r'\s{2,}|;|\|', line) if _clean(part)] for line in text.splitlines() if _clean(line)]
    rows = [row for row in rows if row]
    if len(rows) < 2:
        return pd.DataFrame([{'Arquivo TXT': 'texto', 'Conteúdo': text[:20000]}]) if text.strip() else pd.DataFrame()
    width = max(len(row) for row in rows)
    normalized = [row + [''] * (width - len(row)) for row in rows]
    columns = [_clean(value) or f'Coluna {idx + 1}' for idx, value in enumerate(normalized[0])]
    return _clean_columns(pd.DataFrame(normalized[1:], columns=columns))


def _read_excel_bytes(data: bytes, file_name: str) -> pd.DataFrame:
    buffer = BytesIO(data)
    try:
        sheets = pd.read_excel(buffer, sheet_name=None, dtype=str).values()
        return _best_frame([sheet.fillna('') for sheet in sheets])
    except Exception:
        buffer.seek(0)
        df = pd.read_excel(buffer, dtype=str).fillna('')
        return _clean_columns(df)


def _extract_tables_from_html(html_text: str) -> list[pd.DataFrame]:
    soup = BeautifulSoup(html_text or '', 'html.parser')
    frames: list[pd.DataFrame] = []

    for table in soup.find_all('table'):
        rows: list[list[str]] = []
        for tr in table.find_all('tr'):
            cells = tr.find_all(['th', 'td'])
            row = [_clean(cell.get_text(' ', strip=True)) for cell in cells]
            if any(row):
                rows.append(row)

        if len(rows) < 2:
            continue

        width = max(len(row) for row in rows)
        normalized_rows = [row + [''] * (width - len(row)) for row in rows]
        columns = [_clean(value) or f'Coluna {idx + 1}' for idx, value in enumerate(normalized_rows[0])]
        frame = pd.DataFrame(normalized_rows[1:], columns=columns).fillna('').astype(str)
        if not frame.empty:
            frames.append(frame)

    return frames


def _read_html_bytes(data: bytes) -> pd.DataFrame:
    html_text = _decode_bytes(data)
    frames = _extract_tables_from_html(html_text)
    if frames:
        return _best_frame(frames)

    text = BeautifulSoup(html_text or '', 'html.parser').get_text('\n')
    rows = []
    for line in text.splitlines():
        if '\t' in line:
            rows.append([_clean(part) for part in line.split('\t')])
    if len(rows) < 2:
        return pd.DataFrame()

    width = max(len(row) for row in rows)
    rows = [row + [''] * (width - len(row)) for row in rows]
    columns = [_clean(value) or f'Coluna {idx + 1}' for idx, value in enumerate(rows[0])]
    return _clean_columns(pd.DataFrame(rows[1:], columns=columns))


def _message_part_to_text(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        raw_payload = part.get_payload()
        if isinstance(raw_payload, str):
            return raw_payload
        return ''

    charset = part.get_content_charset() or 'utf-8'
    try:
        return payload.decode(charset, errors='replace')
    except Exception:
        return _decode_bytes(payload)


def _extract_html_parts_from_mhtml(data: bytes) -> list[str]:
    html_parts: list[str] = []
    try:
        message = message_from_bytes(data, policy=email_default_policy)
    except Exception:
        text = _decode_bytes(data)
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
        fallback = _decode_bytes(data)
        if '<html' in fallback.lower() or '<table' in fallback.lower():
            html_parts.append(fallback)

    return html_parts


def _read_mhtml_bytes(data: bytes) -> pd.DataFrame:
    html_parts = _extract_html_parts_from_mhtml(data)
    frames: list[pd.DataFrame] = []
    for html_text in html_parts:
        frames.extend(_extract_tables_from_html(html_text))
    if not frames:
        for html_text in html_parts:
            frame = _read_html_bytes(html_text.encode('utf-8', errors='ignore'))
            if isinstance(frame, pd.DataFrame) and not frame.empty:
                frames.append(frame)
    return _best_frame(frames)


def _xml_tag_name(tag: str) -> str:
    return str(tag or '').split('}', 1)[-1].strip()


def _xml_child_texts(element: ET.Element, prefix: str = '') -> dict[str, str]:
    data: dict[str, str] = {}
    for child in list(element):
        name = _xml_tag_name(child.tag)
        key = f'{prefix}{name}' if not prefix else f'{prefix}.{name}'
        children = list(child)
        text = _clean(child.text)
        if children:
            data.update(_xml_child_texts(child, key))
        elif text:
            data[key] = text
        for attr, value in child.attrib.items():
            data[f'{key}@{attr}'] = _clean(value)
    return data


def _nfe_item_to_row(det: ET.Element) -> dict[str, str]:
    row: dict[str, str] = {}
    n_item = det.attrib.get('nItem')
    if n_item:
        row['nItem'] = _clean(n_item)
    for child in list(det):
        child_name = _xml_tag_name(child.tag)
        if child_name in NFE_PRODUCT_TAGS:
            for product_child in list(child):
                row[_xml_tag_name(product_child.tag)] = _clean(product_child.text)
        else:
            row.update(_xml_child_texts(child, child_name))
    return row


def _read_xml_bytes(data: bytes, file_name: str = 'xml') -> pd.DataFrame:
    text = _decode_bytes(data)
    try:
        root = ET.fromstring(text.encode('utf-8'))
    except Exception:
        try:
            root = ET.fromstring(text)
        except Exception:
            return pd.DataFrame([{'Arquivo XML': file_name, 'Conteúdo XML': text[:50000]}])

    rows: list[dict[str, str]] = []
    for element in root.iter():
        name = _xml_tag_name(element.tag).lower()
        if name in NFE_ITEM_TAGS:
            row = _nfe_item_to_row(element)
            if row:
                rows.append(row)

    if not rows:
        for element in root.iter():
            name = _xml_tag_name(element.tag).lower()
            if name in COMMON_ITEM_TAGS:
                row = _xml_child_texts(element)
                if len(row) >= 2:
                    rows.append(row)

    if not rows:
        flat = _xml_child_texts(root)
        if flat:
            rows.append(flat)

    if not rows:
        return pd.DataFrame([{'Arquivo XML': file_name, 'Conteúdo XML': text[:50000]}])

    return _clean_columns(pd.DataFrame(rows).fillna(''))


def _split_pdf_table_line(line: str) -> list[str]:
    clean = _clean(line)
    if not clean:
        return []
    parts = [part.strip() for part in re.split(r'\s{2,}|\t|;|\|', clean) if part.strip()]
    return parts


def _read_pdf_bytes(data: bytes, file_name: str = 'pdf') -> pd.DataFrame:
    if PdfReader is None:
        return pd.DataFrame([{'Arquivo PDF': file_name, 'Status': 'Leitor de PDF indisponível no ambiente.'}])

    try:
        reader = PdfReader(BytesIO(data))
        page_texts = [page.extract_text() or '' for page in reader.pages]
        text = '\n'.join(page_texts)
    except Exception as exc:
        return pd.DataFrame([{'Arquivo PDF': file_name, 'Status': f'Não foi possível ler o PDF: {exc}'}])

    lines = [_clean(line) for line in text.splitlines() if _clean(line)]
    table_rows = [_split_pdf_table_line(line) for line in lines]
    table_rows = [row for row in table_rows if len(row) >= 2]

    if len(table_rows) >= 2:
        width = max(len(row) for row in table_rows)
        normalized = [row + [''] * (width - len(row)) for row in table_rows]
        header_index = 0
        for idx, row in enumerate(normalized[:10]):
            row_text = ' '.join(row).lower()
            if any(term in row_text for term in ('codigo', 'código', 'sku', 'produto', 'descricao', 'descrição', 'preco', 'preço', 'qtde', 'quantidade')):
                header_index = idx
                break
        columns = [_clean(value) or f'Coluna {idx + 1}' for idx, value in enumerate(normalized[header_index])]
        data_rows = normalized[header_index + 1 :]
        if data_rows:
            return _clean_columns(pd.DataFrame(data_rows, columns=columns))

    if text.strip():
        return pd.DataFrame([{'Arquivo PDF': file_name, 'Texto extraído': text[:50000]}])
    return pd.DataFrame([{'Arquivo PDF': file_name, 'Status': 'PDF sem texto extraível. Pode ser imagem/scan.'}])


def read_uploaded_file(uploaded_file: Any) -> pd.DataFrame:
    if uploaded_file is None:
        return pd.DataFrame()

    name_original = str(getattr(uploaded_file, 'name', '') or 'arquivo')
    name = name_original.lower()
    data = uploaded_file.getvalue()

    if name.endswith('.csv'):
        return _read_csv_bytes(data)
    if name.endswith(TEXT_EXTENSIONS):
        return _read_text_bytes(data)
    if name.endswith(SPREADSHEET_EXTENSIONS):
        return _read_excel_bytes(data, name_original)
    if name.endswith(HTML_EXTENSIONS):
        return _read_html_bytes(data)
    if name.endswith(MHTML_EXTENSIONS):
        return _read_mhtml_bytes(data)
    if name.endswith('.xml'):
        return _read_xml_bytes(data, name_original)
    if name.endswith('.pdf'):
        return _read_pdf_bytes(data, name_original)
    return pd.DataFrame()


def ensure_dataframe(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy().fillna('')
    return pd.DataFrame()


__all__ = [
    'SUPPORTED_SUPPLIER_EXTENSIONS',
    'ensure_dataframe',
    'read_uploaded_file',
]
