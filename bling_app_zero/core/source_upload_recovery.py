from __future__ import annotations

import csv
import re
import zipfile
from dataclasses import dataclass
from io import BytesIO, StringIO
from typing import Any

import pandas as pd

from bling_app_zero.core.files import read_uploaded_file

RESPONSIBLE_FILE = 'bling_app_zero/core/source_upload_recovery.py'
MAX_DEPTH = 3
SUPPORTED_IN_ZIP = (
    '.csv', '.xlsx', '.xls', '.xlsm', '.xlsb', '.txt', '.tsv', '.html', '.htm',
    '.mht', '.mhtml', '.xml', '.pdf', '.zip',
)
SPREADSHEET_BINARY_EXTENSIONS = ('.xlsx', '.xls', '.xlsm', '.xlsb')


@dataclass
class _BytesUpload:
    name: str
    data: bytes

    def getvalue(self) -> bytes:
        return bytes(self.data or b'')


def _clean(value: Any) -> str:
    text = '' if value is None else str(value)
    text = text.replace('\ufeff', '').replace('\x00', '').replace('\xa0', ' ')
    return ' '.join(text.replace('\r', ' ').replace('\n', ' ').replace('\t', ' ').split()).strip()


def _valid_frame(df: Any) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0


def _decode_text(data: bytes) -> str:
    raw = bytes(data or b'')
    for encoding in ('utf-8-sig', 'utf-8', 'latin-1', 'cp1252'):
        try:
            return raw.decode(encoding, errors='strict')
        except Exception:
            continue
    return raw.decode('utf-8', errors='replace')


def _looks_binary(data: bytes) -> bool:
    raw = bytes(data or b'')[:4096]
    if not raw:
        return False
    if raw.count(b'\x00') >= 3:
        return True
    text = _decode_text(raw)
    printable = sum(1 for char in text if char.isprintable() or char.isspace())
    return printable / max(1, len(text)) < 0.70


def _dedupe_columns(columns: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out: list[str] = []
    for index, column in enumerate(columns, start=1):
        base = _clean(column) or f'Coluna {index}'
        count = seen.get(base, 0)
        seen[base] = count + 1
        out.append(base if count == 0 else f'{base}_{count + 1}')
    return out


def _detect_separator(text: str) -> str:
    sample = text[:8192]
    try:
        return csv.Sniffer().sniff(sample, delimiters=',;\t|').delimiter
    except Exception:
        candidates = [',', ';', '\t', '|']
        return max(candidates, key=lambda sep: sample.count(sep))


def _try_text_table(file_name: str, data: bytes) -> pd.DataFrame:
    text = _decode_text(data)
    if not text.strip():
        return pd.DataFrame()

    sep = _detect_separator(text)
    try:
        df = pd.read_csv(StringIO(text), sep=sep, dtype=str, engine='python').fillna('')
        if _valid_frame(df):
            return _clean_dataframe(df)
    except Exception:
        pass

    lines = [_clean(line) for line in text.splitlines() if _clean(line)]
    rows: list[list[str]] = []
    for line in lines[:5000]:
        parts = [_clean(part) for part in re.split(r'\s{2,}|;|\t|\|', line) if _clean(part)]
        if len(parts) <= 1 and ',' in line and 'http' not in line.casefold():
            parts = [_clean(part) for part in line.split(',') if _clean(part)]
        if parts:
            rows.append(parts)

    if len(rows) >= 2 and max(len(row) for row in rows) >= 2:
        width = max(len(row) for row in rows)
        normalized = [row + [''] * (width - len(row)) for row in rows]
        columns = _dedupe_columns(normalized[0])
        return _clean_dataframe(pd.DataFrame(normalized[1:], columns=columns).fillna(''))

    # Texto solto não é tabela confiável para o fluxo universal. Retornar vazio
    # evita que 'Arquivo/Conteúdo extraído' vire contrato final por engano.
    return pd.DataFrame()


def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy().fillna('')
    out.columns = _dedupe_columns([str(column) for column in out.columns])
    return out.astype(str)


def _best_frame(frames: list[pd.DataFrame]) -> pd.DataFrame:
    valid = [_clean_dataframe(frame) for frame in frames if _valid_frame(frame)]
    if not valid:
        return pd.DataFrame()
    valid.sort(key=lambda frame: (int(len(frame) > 0), len(frame) * max(1, len(frame.columns)), len(frame.columns)), reverse=True)
    return valid[0]


def _recover_zip(data: bytes, file_name: str, depth: int) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                inner_name = str(info.filename or '').strip() or 'arquivo_sem_nome'
                lower = inner_name.casefold()
                if not lower.endswith(SUPPORTED_IN_ZIP):
                    continue
                try:
                    frame = _recover_bytes(inner_name, archive.read(info), depth=depth + 1)
                except Exception:
                    frame = pd.DataFrame()
                if _valid_frame(frame):
                    frames.append(frame)
    except Exception:
        return pd.DataFrame()
    return _best_frame(frames)


def _recover_bytes(file_name: str, data: bytes, *, depth: int = 0) -> pd.DataFrame:
    lower = str(file_name or 'arquivo').casefold()
    if depth > MAX_DEPTH:
        return pd.DataFrame()

    if lower.endswith('.zip'):
        return _recover_zip(data, file_name, depth)

    try:
        df = read_uploaded_file(_BytesUpload(file_name, data))
        if _valid_frame(df):
            return _clean_dataframe(df)
    except Exception:
        pass

    # Planilhas binárias que falharam no leitor principal não podem virar uma
    # linha técnica Arquivo/Status. Isso contaminava o modelo universal.
    if lower.endswith(SPREADSHEET_BINARY_EXTENSIONS):
        return pd.DataFrame()
    if _looks_binary(data):
        return pd.DataFrame()
    return _try_text_table(file_name, data)


def recover_uploaded_source_file(uploaded_file: Any) -> pd.DataFrame:
    if uploaded_file is None:
        return pd.DataFrame()
    name = str(getattr(uploaded_file, 'name', '') or 'arquivo')
    try:
        data = bytes(uploaded_file.getvalue() or b'')
    except Exception:
        return pd.DataFrame()
    return _recover_bytes(name, data, depth=0)


__all__ = ['recover_uploaded_source_file']
