from __future__ import annotations

from io import BytesIO
from typing import Iterable

import pandas as pd

SUPPORTED_EXTENSIONS = {"csv", "xlsx", "xls", "xlsm", "xlsb"}


def dedupe_columns(columns: Iterable[object]) -> list[str]:
    seen: dict[str, int] = {}
    result: list[str] = []
    for raw_col in columns:
        col = str(raw_col).strip()
        if not col or col.lower().startswith("unnamed"):
            continue
        count = seen.get(col, 0)
        seen[col] = count + 1
        result.append(col if count == 0 else f"{col} ({count + 1})")
    return result


def read_table(uploaded_file) -> pd.DataFrame:
    filename = getattr(uploaded_file, "name", "arquivo")
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Formato não suportado: {ext or 'sem extensão'}")

    raw = uploaded_file.getvalue()
    buffer = BytesIO(raw)

    if ext == "csv":
        df = pd.read_csv(buffer, sep=None, engine="python", dtype=str, keep_default_na=False)
    else:
        df = pd.read_excel(buffer, dtype=str, keep_default_na=False)

    df.columns = dedupe_columns(df.columns)
    return df.fillna("")


def empty_like_model(model_df: pd.DataFrame, rows: int = 1) -> pd.DataFrame:
    row_count = max(int(rows), 1)
    return pd.DataFrame([{col: "" for col in model_df.columns} for _ in range(row_count)], columns=list(model_df.columns))
