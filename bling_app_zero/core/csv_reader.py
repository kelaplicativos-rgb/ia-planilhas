from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any

import pandas as pd


@dataclass
class CSVReadResult:
    dataframe: pd.DataFrame
    encoding: str
    separator: str


_ENCODINGS = (
    "utf-8-sig",
    "utf-8",
    "latin1",
    "cp1252",
    "iso-8859-1",
)

_SEPARATORS = (";", ",", "\t", "|")


def _read_bytes(uploaded_file: Any) -> bytes:
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

    raise ValueError("Arquivo CSV inválido ou vazio.")


def _score_dataframe(df: pd.DataFrame) -> int:
    if df is None or df.empty:
        return -1
    cols = len(df.columns)
    rows = len(df.index)
    unnamed = sum(1 for c in df.columns if str(c).lower().startswith("unnamed"))
    return (cols * 1000) + min(rows, 1000) - (unnamed * 50)


def read_csv_robusto(uploaded_file: Any) -> CSVReadResult:
    data = _read_bytes(uploaded_file)
    if not data:
        raise ValueError("Arquivo CSV vazio.")

    best: CSVReadResult | None = None
    best_score = -1
    erros: list[str] = []

    for encoding in _ENCODINGS:
        for sep in _SEPARATORS:
            try:
                df = pd.read_csv(
                    BytesIO(data),
                    sep=sep,
                    encoding=encoding,
                    dtype=str,
                    engine="python",
                    on_bad_lines="skip",
                    keep_default_na=False,
                )
                score = _score_dataframe(df)
                if score > best_score and len(df.columns) > 1:
                    best_score = score
                    best = CSVReadResult(df, encoding, sep)
            except Exception as exc:
                erros.append(f"{encoding}/{sep}: {exc}")

    if best is not None:
        best.dataframe.columns = [str(c).replace("\ufeff", "").strip().strip('"') for c in best.dataframe.columns]
        return best

    try:
        df = pd.read_csv(BytesIO(data), sep=None, encoding="utf-8-sig", engine="python", dtype=str, keep_default_na=False)
        df.columns = [str(c).replace("\ufeff", "").strip().strip('"') for c in df.columns]
        return CSVReadResult(df, "utf-8-sig", "auto")
    except Exception as exc:
        detalhe = "; ".join(erros[:5])
        raise ValueError(f"Não foi possível ler o CSV. Último erro: {exc}. Tentativas: {detalhe}") from exc
