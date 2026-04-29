# bling_app_zero/core/instant_scraper/runner.py

from __future__ import annotations

from typing import Any, List

import pandas as pd

from .html_fetcher import fetch_html
from .ultra_detector import detectar_blocos_repetidos
from .ultra_extractor import extrair_lista


def _normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy().fillna("")

    colunas_base = ["nome", "preco", "url_produto", "imagens", "descricao"]
    for col in colunas_base:
        if col not in df.columns:
            df[col] = ""

    df = df[colunas_base + [c for c in df.columns if c not in colunas_base]]

    if "url_produto" in df.columns:
        df = df.drop_duplicates(subset=["url_produto", "nome"], keep="first")
    else:
        df = df.drop_duplicates(keep="first")

    return df.reset_index(drop=True)


def run_scraper(url: str) -> pd.DataFrame:
    """
    Executa o modo automático do Instant Scraper.

    Importante:
    - Não executa nada no import.
    - Busca o HTML apenas quando a função é chamada.
    - Detecta blocos repetidos.
    - Extrai produtos dos melhores blocos.
    - Retorna DataFrame pronto para o fluxo do Streamlit.
    """
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

    for candidate in candidates:
        try:
            elements = candidate.get("elements", [])
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
