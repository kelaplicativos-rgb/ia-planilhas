from __future__ import annotations

"""Qualidade dos dados capturados por página de produto.

Objetivo:
- Não mascarar dado ausente com valores falsos, como preço `0,00`.
- Enriquecer marca quando ela aparece claramente no nome do produto.
- Manter apenas colunas com dado real no preview de origem.
"""

import re
from typing import Iterable

import pandas as pd


ZERO_LIKE = {"0", "0,0", "0,00", "0.0", "0.00", "r$ 0,00", "r$0,00"}

KNOWN_BRANDS = {
    "LEHMOX": "Lehmox",
    "JBL": "JBL",
    "H MASTON": "H'Maston",
    "HMASTON": "H'Maston",
    "INTELBRAS": "Intelbras",
    "TOSHIBA": "Toshiba",
    "APPLE": "Apple",
    "SAMSUNG": "Samsung",
    "XIAOMI": "Xiaomi",
    "B-MAX": "B-Max",
    "B MAX": "B-Max",
    "CLARO": "Claro",
    "TIM": "TIM",
    "VIVO": "Vivo",
}

PRICE_COLUMNS = {
    "Preço",
    "Preço unitário (OBRIGATÓRIO)",
    "Preço de custo",
    "Preço de compra",
}

OPTIONAL_EMPTY_COLUMNS = {
    "NCM",
    "CEST",
    "Preço de custo",
    "Preço de compra",
    "Categoria do produto",
    "Departamento",
    "Descrição Complementar",
    "Descrição complementar",
}


def _text(value: object) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()


def _is_zero_like(value: object) -> bool:
    return _text(value).lower().strip() in ZERO_LIKE


def infer_brand_from_name(name: object) -> str:
    text = re.sub(r"[^A-Za-zÀ-ÿ0-9]+", " ", _text(name)).upper().strip()
    if not text:
        return ""
    padded = f" {text} "
    for token, brand in KNOWN_BRANDS.items():
        if f" {token} " in padded:
            return brand
    return ""


def normalize_product_row(row: dict[str, object]) -> dict[str, str]:
    cleaned: dict[str, str] = {str(k): _text(v) for k, v in row.items() if _text(v)}

    # Nunca tratar 0,00 como preço capturado real. Se o site não trouxe preço,
    # deixa vazio para revisão/manual/calculadora.
    for col in PRICE_COLUMNS:
        if _is_zero_like(cleaned.get(col)):
            cleaned.pop(col, None)

    if not cleaned.get("Marca"):
        brand = infer_brand_from_name(cleaned.get("Descrição"))
        if brand:
            cleaned["Marca"] = brand

    # Se GTIN veio, espelha no campo de embalagem apenas se o campo existir na saída final.
    if cleaned.get("GTIN/EAN") and not cleaned.get("GTIN/EAN da embalagem"):
        cleaned["GTIN/EAN da embalagem"] = cleaned["GTIN/EAN"]

    # Remove opcionais vazios/falsos para não poluir preview.
    for col in OPTIONAL_EMPTY_COLUMNS:
        if not cleaned.get(col):
            cleaned.pop(col, None)

    return cleaned


def normalize_product_rows(rows: Iterable[dict[str, object]]) -> list[dict[str, str]]:
    return [normalize_product_row(row) for row in rows]


def normalize_product_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df
    return pd.DataFrame(normalize_product_rows(df.to_dict(orient="records")))
