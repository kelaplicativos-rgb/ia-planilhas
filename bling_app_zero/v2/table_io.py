from __future__ import annotations

import csv
import zipfile
from io import BytesIO, StringIO
from typing import Any

import pandas as pd

SUPPORTED_EXTENSIONS = ('.csv', '.xlsx', '.xls', '.zip')
_TABLE_EXTENSIONS = ('.csv', '.xlsx', '.xls')


def _file_name(uploaded_file: Any) -> str:
    return str(getattr(uploaded_file, 'name', '') or '').lower().strip()


def _read_bytes(uploaded_file: Any) -> bytes:
    if hasattr(uploaded_file, 'getvalue'):
        return uploaded_file.getvalue()
    return uploaded_file.read()


def _decode_csv_bytes(raw: bytes) -> str:
    for encoding in ('utf-8-sig', 'utf-8', 'cp1252', 'latin1'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='ignore')


def _detect_separator(text: str) -> str:
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=';,\t|')
        return dialect.delimiter
    except Exception:
        candidates = [';', ',', '\t', '|']
        return max(candidates, key=lambda separator: sample.count(separator))


def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    out = df.copy().fillna('')
    out.columns = [str(column).replace('\ufeff', '').strip().strip('"') for column in out.columns]

    empty_columns = [column for column in out.columns if not str(column).strip() or str(column).lower().startswith('unnamed')]
    if empty_columns:
        out = out.drop(columns=empty_columns, errors='ignore')

    for column in out.columns:
        out[column] = out[column].map(lambda value: str(value).replace('\ufeff', '').strip() if value is not None else '')
    return out.fillna('')


def _load_csv_bytes(raw: bytes) -> pd.DataFrame:
    text = _decode_csv_bytes(raw)
    separator = _detect_separator(text)
    return _clean_dataframe(pd.read_csv(StringIO(text), sep=separator, dtype=str).fillna(''))


def _load_excel_bytes(raw: bytes, file_name: str) -> pd.DataFrame:
    _ = file_name
    return _clean_dataframe(pd.read_excel(BytesIO(raw), dtype=str).fillna(''))


def _load_table_bytes(file_name: str, raw: bytes) -> pd.DataFrame:
    lower_name = file_name.lower().strip()
    if lower_name.endswith('.csv'):
        return _load_csv_bytes(raw)
    if lower_name.endswith(('.xlsx', '.xls')):
        return _load_excel_bytes(raw, lower_name)
    raise ValueError('Formato não suportado. Envie CSV, XLS, XLSX ou ZIP do Bling.')


def _zip_members(zip_file: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members: list[zipfile.ZipInfo] = []
    for info in zip_file.infolist():
        if info.is_dir():
            continue
        name = info.filename.lower().strip()
        if name.startswith('__macosx/'):
            continue
        if name.endswith(_TABLE_EXTENSIONS):
            members.append(info)
    return members


def _load_zip_bytes(raw: bytes) -> pd.DataFrame:
    try:
        with zipfile.ZipFile(BytesIO(raw)) as zip_file:
            members = _zip_members(zip_file)
            if not members:
                raise ValueError('ZIP sem CSV, XLS ou XLSX dentro.')

            # Exportações do Bling normalmente vêm com uma única planilha dentro do ZIP.
            # Se houver mais de uma, usamos a maior porque tende a ser o arquivo de dados real.
            selected = max(members, key=lambda item: item.file_size)
            return _load_table_bytes(selected.filename, zip_file.read(selected))
    except zipfile.BadZipFile as exc:
        raise ValueError('ZIP inválido ou corrompido.') from exc


def load_table(uploaded_file: Any) -> pd.DataFrame:
    if uploaded_file is None:
        return pd.DataFrame()

    file_name = _file_name(uploaded_file)
    if not file_name.endswith(SUPPORTED_EXTENSIONS):
        raise ValueError('Formato não suportado. Envie CSV, XLS, XLSX ou ZIP do Bling.')

    raw = _read_bytes(uploaded_file)
    if file_name.endswith('.zip'):
        return _load_zip_bytes(raw)
    return _load_table_bytes(file_name, raw)


__all__ = ['SUPPORTED_EXTENSIONS', 'load_table']
