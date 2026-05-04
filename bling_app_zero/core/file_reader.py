from __future__ import annotations

import json
from dataclasses import dataclass
from io import BytesIO, StringIO
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
    return df.fillna("")


def _ensure_valid_df(df: pd.DataFrame, detail: str) -> pd.DataFrame:
    df = _clean_columns(df)
    if df is None or df.empty or len(df.columns) == 0:
        raise ValueError(f"O arquivo foi reconhecido, mas não possui tabela válida. {detail}")
    return df


def _read_excel_bytes(data: bytes, suffix: str) -> FileReadResult:
    df = pd.read_excel(BytesIO(data), dtype=str, keep_default_na=False)
    return FileReadResult(
        dataframe=_ensure_valid_df(df, "Excel sem linhas ou colunas."),
        file_type=suffix or "excel",
        detail="planilha Excel lida automaticamente",
    )


def _read_ods_bytes(data: bytes) -> FileReadResult:
    df = pd.read_excel(BytesIO(data), dtype=str, keep_default_na=False, engine="odf")
    return FileReadResult(
        dataframe=_ensure_valid_df(df, "ODS sem linhas ou colunas."),
        file_type="ods",
        detail="planilha ODS lida automaticamente",
    )


def _read_html_bytes(data: bytes) -> FileReadResult:
    text = data.decode("utf-8", errors="ignore")
    tables = pd.read_html(StringIO(text))
    if not tables:
        raise ValueError("HTML reconhecido, mas nenhuma tabela foi encontrada.")
    df = max(tables, key=lambda item: len(item.index) * max(len(item.columns), 1))
    return FileReadResult(
        dataframe=_ensure_valid_df(df.astype(str), "HTML sem tabela válida."),
        file_type="html",
        detail=f"HTML lido automaticamente | tabelas encontradas={len(tables)}",
    )


def _read_json_bytes(data: bytes) -> FileReadResult:
    text = data.decode("utf-8", errors="ignore").strip()
    payload = json.loads(text)

    if isinstance(payload, list):
        df = pd.DataFrame(payload)
    elif isinstance(payload, dict):
        rows = None
        for key in ("items", "produtos", "products", "data", "rows", "results"):
            if isinstance(payload.get(key), list):
                rows = payload[key]
                break
        df = pd.DataFrame(rows if rows is not None else [payload])
    else:
        raise ValueError("JSON reconhecido, mas o conteúdo não parece uma tabela.")

    return FileReadResult(
        dataframe=_ensure_valid_df(df.astype(str), "JSON sem linhas ou colunas."),
        file_type="json",
        detail="JSON convertido automaticamente em tabela",
    )


def _try_csv(uploaded_file: Any) -> FileReadResult:
    csv_result: CSVReadResult = read_csv_robusto(uploaded_file)
    return FileReadResult(
        dataframe=_ensure_valid_df(csv_result.dataframe, "CSV/TXT sem linhas ou colunas."),
        file_type="csv",
        detail=f"encoding={csv_result.encoding} | separador={csv_result.separator}",
    )


def read_uploaded_table(uploaded_file: Any) -> FileReadResult:
    name = _get_name(uploaded_file)
    suffix = Path(name).suffix.lower().strip(".")
    data = _get_bytes(uploaded_file)

    if not data:
        raise ValueError("Arquivo vazio. Anexe outro arquivo.")

    if suffix in {"csv", "txt", "tsv", "tab"}:
        return _try_csv(uploaded_file)

    if suffix in {"xlsx", "xlsm", "xls", "xlsb"}:
        return _read_excel_bytes(data, suffix)

    if suffix == "ods":
        return _read_ods_bytes(data)

    if suffix in {"html", "htm"}:
        return _read_html_bytes(data)

    if suffix == "json":
        return _read_json_bytes(data)

    # Reconhecimento automático quando a extensão vem ausente, estranha ou genérica.
    attempts: list[tuple[str, Any]] = [
        ("excel", lambda: _read_excel_bytes(data, suffix or "excel")),
        ("csv", lambda: _try_csv(uploaded_file)),
        ("html", lambda: _read_html_bytes(data)),
        ("json", lambda: _read_json_bytes(data)),
    ]

    errors: list[str] = []
    for name_attempt, reader in attempts:
        try:
            return reader()
        except Exception as exc:
            errors.append(f"{name_attempt}: {exc}")

    raise ValueError(
        "Não consegui reconhecer esse anexo como tabela. "
        "Envie um arquivo Excel, CSV, TXT, TSV, ODS, HTML ou JSON. "
        f"Detalhes: {' | '.join(errors[:3])}"
    )
