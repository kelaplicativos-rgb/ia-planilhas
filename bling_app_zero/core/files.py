from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd


def read_uploaded_file(uploaded_file: Any) -> pd.DataFrame:
    if uploaded_file is None:
        return pd.DataFrame()

    name = str(getattr(uploaded_file, 'name', '') or '').lower()
    data = uploaded_file.getvalue()
    buffer = BytesIO(data)

    if name.endswith('.csv'):
        try:
            return pd.read_csv(buffer, sep=';', dtype=str, encoding='utf-8-sig').fillna('')
        except Exception:
            buffer.seek(0)
            return pd.read_csv(buffer, sep=None, engine='python', dtype=str, encoding='utf-8-sig').fillna('')

    if name.endswith(('.xlsx', '.xls', '.xlsm', '.xlsb')):
        return pd.read_excel(buffer, dtype=str).fillna('')

    if name.endswith('.xml'):
        text = data.decode('utf-8', errors='ignore')
        return pd.DataFrame([{'arquivo_xml': getattr(uploaded_file, 'name', 'xml'), 'conteudo_xml': text}])

    if name.endswith('.pdf'):
        return pd.DataFrame([{'arquivo_pdf': getattr(uploaded_file, 'name', 'pdf'), 'observacao': 'PDF recebido para extração futura'}])

    return pd.DataFrame()


def ensure_dataframe(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy().fillna('')
    return pd.DataFrame()
