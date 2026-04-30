from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import pandas as pd


PREFERRED_COLUMNS = [
    "produto_id_url",
    "sku",
    "nome",
    "preco",
    "moeda",
    "marca",
    "categoria",
    "gtin",
    "estoque",
    "url_produto",
    "imagens",
    "descricao",
]

SOURCE_PRIORITY = {"sitemap": 3, "visual": 2, "manual": 1, "unknown": 0}


def _txt(value: Any) -> str:
    text = str(value or "").strip()
    if text.lower() in {"nan", "none", "null", "undefined"}:
        return ""
    return " ".join(text.split())


def _norm_url(value: Any) -> str:
    text = _txt(value)
    if not text:
        return ""
    return text.split("#", 1)[0].rstrip("/")


def _id_from_url(value: Any) -> str:
    url = _norm_url(value)
    path = urlparse(url).path.strip("/")
    if not path:
        return ""
    last = path.split("/")[-1]
    digits = "".join(ch if ch.isdigit() else " " for ch in last).split()
    long_digits = [d for d in digits if len(d) >= 4]
    if long_digits:
        return long_digits[-1]
    return last[:80]


def _prepare(df: pd.DataFrame, source: str) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    base = df.copy().fillna("")
    for col in PREFERRED_COLUMNS:
        if col not in base.columns:
            base[col] = ""
    base["produto_id_url"] = base.apply(
        lambda row: _txt(row.get("produto_id_url")) or _id_from_url(row.get("url_produto")),
        axis=1,
    )
    base["_merge_source"] = source
    base["_merge_priority"] = SOURCE_PRIORITY.get(source, 0)
    base["_merge_key"] = base.apply(_merge_key, axis=1)
    base = base[base["_merge_key"].astype(str).str.strip().ne("")].copy()
    return base


def _merge_key(row: pd.Series) -> str:
    pid = _txt(row.get("produto_id_url"))
    if pid:
        return "id:" + pid.lower()
    url = _norm_url(row.get("url_produto"))
    if url:
        return "url:" + url.lower()
    sku = _txt(row.get("sku"))
    if sku:
        return "sku:" + sku.lower()
    nome = _txt(row.get("nome"))
    if nome:
        return "nome:" + nome.lower()
    return ""


def _best(current: Any, new: Any, col: str) -> str:
    a = _txt(current)
    b = _txt(new)
    if not a:
        return b
    if not b:
        return a
    if col in {"descricao", "imagens"}:
        return b if len(b) > len(a) else a
    if col == "preco":
        return a if any(ch.isdigit() for ch in a) else b
    return a


def auto_merge_produtos(*frames: tuple[str, pd.DataFrame]) -> pd.DataFrame:
    parts = []
    for source, df in frames:
        prepared = _prepare(df, source)
        if not prepared.empty:
            parts.append(prepared)
    if not parts:
        return pd.DataFrame(columns=PREFERRED_COLUMNS)

    full = pd.concat(parts, ignore_index=True).fillna("")
    full = full.sort_values("_merge_priority", ascending=False)

    merged: dict[str, dict[str, Any]] = {}
    for _, row in full.iterrows():
        key = _txt(row.get("_merge_key"))
        if not key:
            continue
        if key not in merged:
            merged[key] = row.to_dict()
            continue
        current = merged[key]
        for col in full.columns:
            if col in {"_merge_key", "_merge_priority"}:
                continue
            if col == "_merge_source":
                old = set(_txt(current.get(col)).split("+")) if _txt(current.get(col)) else set()
                old.add(_txt(row.get(col)))
                current[col] = "+".join(sorted(x for x in old if x))
            else:
                current[col] = _best(current.get(col), row.get(col), col)

    result = pd.DataFrame(list(merged.values())).fillna("")
    for col in PREFERRED_COLUMNS:
        if col not in result.columns:
            result[col] = ""
    ordered = PREFERRED_COLUMNS + [c for c in result.columns if c not in PREFERRED_COLUMNS]
    result = result[ordered].drop(columns=["_merge_key", "_merge_priority"], errors="ignore")
    return result.reset_index(drop=True)
