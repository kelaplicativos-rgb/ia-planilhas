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
    "cp1252",
    "latin1",
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


def _normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [
        str(c)
        .replace("\ufeff", "")
        .replace("\x00", "")
        .strip()
        .strip('"')
        .strip("'")
        for c in df.columns
    ]

    df = df.loc[:, [str(c).strip() != "" for c in df.columns]]
    df = df.dropna(how="all")

    return df


def _score_dataframe(df: pd.DataFrame) -> int:
    if df is None or df.empty:
        return -1

    cols = len(df.columns)
    rows = len(df.index)

    if cols <= 1:
        return -1000 + rows

    unnamed = sum(1 for c in df.columns if str(c).lower().startswith("unnamed"))
    empty_names = sum(1 for c in df.columns if str(c).strip() == "")
    useful_names = sum(1 for c in df.columns if len(str(c).strip()) > 1)

    filled_cells = 0
    try:
        sample = df.head(30).astype(str)
        filled_cells = int((sample.apply(lambda col: col.str.strip()) != "").sum().sum())
    except Exception:
        filled_cells = 0

    return (
        cols * 10000
        + min(rows, 5000)
        + useful_names * 100
        + filled_cells
        - unnamed * 250
        - empty_names * 500
    )


def _read_with_options(data: bytes, encoding: str, sep: str | None) -> pd.DataFrame:
    kwargs = {
        "encoding": encoding,
        "dtype": str,
        "engine": "python",
        "on_bad_lines": "skip",
        "keep_default_na": False,
        "quoting": 0,
        "skip_blank_lines": True,
    }

    if sep is None:
        return pd.read_csv(BytesIO(data), sep=None, **kwargs)

    return pd.read_csv(BytesIO(data), sep=sep, **kwargs)


def read_csv_robusto(uploaded_file: Any) -> CSVReadResult:
    data = _read_bytes(uploaded_file)

    if not data:
        raise ValueError("Arquivo CSV vazio.")

    best: CSVReadResult | None = None
    best_score = -10**9
    erros: list[str] = []

    tentativas: list[tuple[str, str | None]] = []
    for encoding in _ENCODINGS:
        for sep in _SEPARATORS:
            tentativas.append((encoding, sep))
        tentativas.append((encoding, None))

    for encoding, sep in tentativas:
        try:
            df = _read_with_options(data, encoding, sep)
            df = _normalizar_colunas(df)
            score = _score_dataframe(df)

            if score > best_score:
                best_score = score
                best = CSVReadResult(df, encoding, sep or "auto")
        except Exception as exc:
            erros.append(f"{encoding}/{sep or 'auto'}: {exc}")

    if best is not None and best.dataframe is not None and not best.dataframe.empty and len(best.dataframe.columns) > 1:
        return best

    try:
        df = pd.read_csv(
            BytesIO(data),
            sep=None,
            encoding="utf-8-sig",
            engine="python",
            dtype=str,
            keep_default_na=False,
            on_bad_lines="warn",
            skip_blank_lines=True,
        )
        df = _normalizar_colunas(df)
        if not df.empty and len(df.columns) > 1:
            return CSVReadResult(df, "utf-8-sig", "auto")
    except Exception as exc:
        erros.append(f"fallback utf-8-sig/auto: {exc}")

    detalhe = "; ".join(erros[:8])
    raise ValueError(
        "Não foi possível ler o CSV enviado. "
        "Verifique se o arquivo não está corrompido e tente exportar novamente em CSV com cabeçalho. "
        f"Tentativas: {detalhe}"
    )
