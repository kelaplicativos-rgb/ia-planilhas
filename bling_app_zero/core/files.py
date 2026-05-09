from __future__ import annotations

import csv
from io import BytesIO, StringIO
from typing import Any

import pandas as pd


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
