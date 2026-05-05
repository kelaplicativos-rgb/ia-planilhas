from __future__ import annotations

import re

import pandas as pd


def _norm_name(value: object) -> str:
    text = str(value or "").strip().lower()
    repl = str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc")
    text = text.translate(repl)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_image_url_column(column_name: object) -> bool:
    name = _norm_name(column_name)
    return any(token in name for token in ["imagem", "imagens", "image", "foto", "fotos", "url imagens"])


def normalize_image_urls(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    urls = re.findall(r"https?://[^\s,|;]+", raw, flags=re.IGNORECASE)

    if not urls:
        parts = re.split(r"[|,;\n\r\t]+", raw)
        urls = [p.strip() for p in parts if p.strip()]

    cleaned: list[str] = []
    seen: set[str] = set()
    for url in urls:
        item = str(url or "").strip().strip('"').strip("'").strip()
        item = item.rstrip(".,;)")
        if not item:
            continue
        if item not in seen:
            seen.add(item)
            cleaned.append(item)

    return "|".join(cleaned)


def normalize_image_url_columns(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df

    out = df.copy().fillna("")
    for col in out.columns:
        if is_image_url_column(col):
            out[col] = out[col].apply(normalize_image_urls)
    return out.fillna("")
