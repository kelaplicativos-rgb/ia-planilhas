# bling_app_zero/core/instant_scraper/runner.py

from __future__ import annotations

from typing import Any, List

import pandas as pd

from bling_app_zero.core.suppliers.megacenter import MegaCenterSupplier

from .html_fetcher import fetch_html, obter_ultimo_fetch_info
from .browser_fetcher import fetch_html_browser, obter_ultimo_browser_fetch_info
from .ultra_detector import detectar_blocos_repetidos
from .ultra_extractor import extrair_lista


MAX_CANDIDATOS_RUNNER = 5


def _normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy().fillna("")

    colunas_base = [
        "fornecedor",
        "url_produto",
        "nome",
        "sku",
        "marca",
        "categoria",
        "preco",
        "estoque",
        "quantidade",
        "quantidade_real",
        "estoque_origem",
        "gtin",
        "descricao",
        "imagens",
    ]

    for col in colunas_base:
        if col not in df.columns:
            df[col] = ""

    for col in df.columns:
        df[col] = df[col].map(lambda x: str(x or "").strip())

    return df.reset_index(drop=True)


def _obter_html_hibrido(url: str) -> str:
    # 1. tenta HTTP
    html = fetch_html(url)
    info = obter_ultimo_fetch_info()

    if html:
        # se parece JS pesado, tenta browser também
        if info.get("parece_javascript"):
            html_browser = fetch_html_browser(url)
            if html_browser:
                return html_browser

        return html

    # 2. fallback browser
    html_browser = fetch_html_browser(url)
    if html_browser:
        return html_browser

    return ""


def _run_generico(url: str) -> pd.DataFrame:
    html = _obter_html_hibrido(url)

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


def run_scraper(url: str) -> pd.DataFrame:
    url = str(url or "").strip()
    if not url:
        return pd.DataFrame()

    supplier = MegaCenterSupplier()
    if supplier.can_handle(url):
        return supplier.fetch(url)

    return _run_generico(url)
