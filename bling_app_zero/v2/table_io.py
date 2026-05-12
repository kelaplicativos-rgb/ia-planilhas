from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd

SUPPORTED_EXTENSIONS = ('.csv', '.xlsx', '.xls')


def load_table(uploaded_file: Any) -> pd.DataFrame:
    if uploaded_file is None:
        return pd.DataFrame()

    file_name = str(getattr(uploaded_file, 'name', '') or '').lower()
    if not file_name.endswith(SUPPORTED_EXTENSIONS):
        raise ValueError('Formato não suportado. Envie CSV, XLS ou XLSX.')

    raw = uploaded_file.getvalue() if hasattr(uploaded_file, 'getvalue') else uploaded_file.read()
    buffer = BytesIO(raw)

    if file_name.endswith('.csv'):
        return _load_csv(buffer)
    return pd.read_excel(buffer, dtype=str).fillna('')


def _load_csv(buffer: BytesIO) -> pd.DataFrame:
    attempts = [
        {'sep': ';', 'encoding': 'utf-8-sig'},
        {'sep': ',', 'encoding': 'utf-8-sig'},
        {'sep': ';', 'encoding': 'latin1'},
        {'sep': ',', 'encoding': 'latin1'},
    ]
    last_error: Exception | None = None
    for kwargs in attempts:
        buffer.seek(0)
        try:
            df = pd.read_csv(buffer, dtype=str, **kwargs).fillna('')
            if len(df.columns) > 1 or len(df) > 0:
                return df
        except Exception as exc:
            last_error = exc
    raise ValueError(f'Não consegui ler o CSV. {last_error}')


__all__ = ['SUPPORTED_EXTENSIONS', 'load_table']
