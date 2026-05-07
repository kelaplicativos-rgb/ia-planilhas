from __future__ import annotations

import re
from typing import Any

import pandas as pd

VALID_GTIN_LENGTHS = {8, 12, 13, 14}


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\ufeff", "").replace("\x00", "")
    text = text.replace("\r", " ").replace("\n", " ").strip()
    return re.sub(r"\s+", " ", text)


def clean_gtin(value: Any) -> str:
    digits = re.sub(r"\D+", "", clean_text(value))
    return digits if len(digits) in VALID_GTIN_LENGTHS else ""


def sanitize_for_export(df: pd.DataFrame) -> pd.DataFrame:
    final = df.copy().fillna("")
    for col in final.columns:
        low = str(col).lower()
        if any(token in low for token in ("gtin", "ean", "código de barras", "codigo de barras")):
            final[col] = final[col].map(clean_gtin)
        else:
            final[col] = final[col].map(clean_text)
    return final


def to_bling_csv_bytes(df: pd.DataFrame) -> bytes:
    clean = sanitize_for_export(df)
    return clean.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")
