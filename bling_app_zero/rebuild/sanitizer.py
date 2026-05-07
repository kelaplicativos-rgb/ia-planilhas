from __future__ import annotations

import re
from typing import Any

import pandas as pd

_GTIN_LENGTHS = {8, 12, 13, 14}


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\ufeff", "").replace("\x00", "")
    text = text.replace("\r", " ").replace("\n", " ").strip()
    return re.sub(r"\s+", " ", text)


def clean_gtin(value: Any) -> str:
    digits = re.sub(r"\D+", "", clean_text(value))
    return digits if len(digits) in _GTIN_LENGTHS else ""


def normalize_price(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    text = text.replace("R$", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return ""
    try:
        return f"{float(match.group(0)):.2f}".replace(".", ",")
    except ValueError:
        return ""


def normalize_stock(value: Any) -> str:
    text = clean_text(value).lower()
    if not text:
        return ""
    if any(token in text for token in ("sem estoque", "indisponível", "indisponivel", "esgotado", "zerado")):
        return "0"
    match = re.search(r"-?\d+", text)
    return match.group(0) if match else ""


def sanitize_final_df(df: pd.DataFrame) -> pd.DataFrame:
    final = df.copy()
    for col in final.columns:
        low = str(col).lower()
        if any(token in low for token in ("gtin", "ean", "código de barras", "codigo de barras")):
            final[col] = final[col].map(clean_gtin)
        elif any(token in low for token in ("preço", "preco", "valor")):
            final[col] = final[col].map(normalize_price)
        elif any(token in low for token in ("estoque", "quantidade", "saldo", "balanço", "balanco")):
            final[col] = final[col].map(normalize_stock)
        else:
            final[col] = final[col].map(clean_text)
    return final


def to_bling_csv_bytes(df: pd.DataFrame) -> bytes:
    clean = sanitize_final_df(df)
    return clean.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")
