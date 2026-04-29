# bling_app_zero/core/instant_scraper/runner.py

from __future__ import annotations

from typing import Any, List

import pandas as pd

from .html_fetcher import fetch_html
from .ultra_detector import detectar_blocos_repetidos
from .ultra_extractor import extrair_lista


MAX_CANDIDATOS_RUNNER = 5


def _normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy().fillna("")

    colunas_base = ["nome", "preco", "url_produto", "imagens", "descricao"]
    for col in colunas_base:
        if col not in df.columns:
            df[col] = ""

    for col in df.columns:
        df[col] = df[col].map(lambda x: str(x or "").strip())

    df = df[colunas_base + [c for c in df.columns if c not in colunas_base]]

    if "url_produto" in df.columns:
        df = df.drop_duplicates(subset=["url_produto", "nome"], keep="first")
    else:
        df = df.drop_duplicates(keep="first")

    return df.reset_index(drop=True)


def run_scraper(url: str) -> pd.DataFrame:
    url = str(url or "").strip()
    if not url:
        return pd.DataFrame()

    try:
        html = fetch_html(url)
    except Exception:
        return pd.DataFrame()

    if not html:
        return pd.DataFrame()

    try:
        candidates: List[dict[str, Any]] = detectar_blocos_repetidos(html)
    except Exception:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []

    for candidate in candidates[:MAX_CANDIDATOS_RUNNER]:
        try:
            elements = candidate.get("elements", [])[:80]
            produtos = extrair_lista(elements, url)

            if produtos:
                frames.append(pd.DataFrame(produtos))
        except Exception:
            continue

    if not frames:
        return pd.DataFrame()

    try:
        df = pd.concat(frames, ignore_index=True)
    except Exception:
        return pd.DataFrame()

    return _normalizar_df(df)

