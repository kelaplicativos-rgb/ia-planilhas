from __future__ import annotations

import csv
from email import message_from_bytes
from email.message import Message
from email.policy import default as email_default_policy
from io import BytesIO, StringIO
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup


def _decode_bytes(data: bytes) -> str:
    for encoding in ('utf-8-sig', 'utf-8', 'latin1'):
        try:
            return data.decode(encoding)
        except Exception:
            continue
    return data.decode('utf-8', errors='ignore')


def _detect_separator(text: str) -> str:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
        return dialect.delimiter
    except Exception:
        candidates = [',', ';', '\t', '|']
        return max(candidates, key=lambda sep: sample.count(sep))


def _clean(value: object) -> str:
    return ' '.join(str(value or '').replace('\xa0', ' ').split()).strip()


def _read_csv_bytes(data: bytes) -> pd.DataFrame:
    text = _decode_bytes(data)
    sep = _detect_separator(text)
    df = pd.read_csv(StringIO(text), sep=sep, dtype=str).fillna('')

    # Blindagem: alguns modelos exportados vêm com uma primeira coluna vazia.
    df.columns = [str(c).strip() for c in df.columns]
    unnamed = [c for c in df.columns if not c or c.lower().startswith('unnamed')]
    if unnamed:
        df = df.drop(columns=unnamed, errors='ignore')
    return df.fillna('')


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
        frames.sort(key=lambda df: len(df) * max(1, len(df.columns)), reverse=True)
        return frames[0].fillna('').astype(str)

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
    return pd.DataFrame(rows[1:], columns=columns).fillna('').astype(str)


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

    if not frames:
        return pd.DataFrame()

    frames.sort(key=lambda df: len(df) * max(1, len(df.columns)), reverse=True)
    return frames[0].fillna('').astype(str)


def read_uploaded_file(uploaded_file: Any) -> pd.DataFrame:
    if uploaded_file is None:
        return pd.DataFrame()

    name = str(getattr(uploaded_file, 'name', '') or '').lower()
    data = uploaded_file.getvalue()
    buffer = BytesIO(data)

    if name.endswith('.csv'):
        return _read_csv_bytes(data)

    if name.endswith(('.xlsx', '.xls', '.xlsm', '.xlsb')):
        df = pd.read_excel(buffer, dtype=str).fillna('')
        df.columns = [str(c).strip() for c in df.columns]
        return df.fillna('')

    if name.endswith(('.html', '.htm')):
        return _read_html_bytes(data)

    if name.endswith(('.mht', '.mhtml')):
        return _read_mhtml_bytes(data)

    if name.endswith('.xml'):
        text = _decode_bytes(data)
        return pd.DataFrame([{'Arquivo XML': getattr(uploaded_file, 'name', 'xml'), 'Conteúdo XML': text}])

    if name.endswith('.pdf'):
        return pd.DataFrame([{'Arquivo PDF': getattr(uploaded_file, 'name', 'pdf'), 'Status': 'PDF recebido. Confira se há dados tabulares disponíveis para extração.'}])

    return pd.DataFrame()


def ensure_dataframe(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy().fillna('')
    return pd.DataFrame()
