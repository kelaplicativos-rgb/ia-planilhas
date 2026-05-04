from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

from bling_app_zero.core.csv_reader import CSVReadResult, read_csv_robusto


@dataclass
class FileReadResult:
    dataframe: pd.DataFrame
    file_type: str
    detail: str


def _get_name(uploaded_file: Any) -> str:
    return str(getattr(uploaded_file, "name", "arquivo"))


def _get_bytes(uploaded_file: Any) -> bytes:
    if isinstance(uploaded_file, bytes):
        return uploaded_file
    if hasattr(uploaded_file, "getvalue"):
        return uploaded_file.getvalue()
    if hasattr(uploaded_file, "read"):
        pos = None
        try:
            pos = uploaded_file.tell()
        except Exception:
            pos = None
        data = uploaded_file.read()
        if pos is not None:
            try:
                uploaded_file.seek(pos)
            except Exception:
                pass
        return data
    raise ValueError("Arquivo inválido ou vazio.")


def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).replace("\ufeff", "").strip().strip('"') for c in df.columns]
    return df


def read_uploaded_table(uploaded_file: Any) -> FileReadResult:
    name = _get_name(uploaded_file)
    suffix = Path(name).suffix.lower().strip(".")

    if suffix == "csv" or suffix == "txt":
        csv_result: CSVReadResult = read_csv_robusto(uploaded_file)
        return FileReadResult(
            dataframe=_clean_columns(csv_result.dataframe),
            file_type="csv",
            detail=f"encoding={csv_result.encoding} | separador={csv_result.separator}",
        )

    if suffix in {"xlsx", "xlsm", "xls"}:
        data = _get_bytes(uploaded_file)
        if not data:
            raise ValueError("Arquivo de planilha vazio.")
        df = pd.read_excel(BytesIO(data), dtype=str, keep_default_na=False)
        return FileReadResult(
            dataframe=_clean_columns(df),
            file_type=suffix,
            detail="planilha Excel lida com pandas/openpyxl",
        )

    raise ValueError(f"Formato não suportado: .{suffix or 'sem extensão'}. Envie CSV, XLSX, XLSM ou XLS.")
