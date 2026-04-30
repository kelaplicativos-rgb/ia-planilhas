# UPDATED RUNNER WITH BROWSER ENGINE
from __future__ import annotations

import pandas as pd

from bling_app_zero.core.suppliers.megacenter import MegaCenterSupplier

from .html_fetcher import fetch_html
from .pagination import coletar_paginas_genericas
from .domain_crawler import descobrir_urls_produto
from .instant_dom_engine import instant_extract
from .self_healing import auto_heal_dataframe
from .autonomous_agent import run_autonomous_agent
from .playwright_engine import run_browser_scraper


def _safe_df(df):
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df.copy().fillna("").reset_index(drop=True)
    return pd.DataFrame()


def _fetch_http(url: str) -> str:
    return fetch_html(url, force_refresh=True)


def _run_instant(url: str) -> pd.DataFrame:
    paginas = coletar_paginas_genericas(url, _fetch_http, max_paginas=5)
    frames = []
    for pagina_url in paginas.urls:
        html = _fetch_http(pagina_url)
        if not html:
            continue
        df = instant_extract(html, pagina_url)
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    return auto_heal_dataframe(pd.concat(frames, ignore_index=True), url)


def _run_fallback(url):
    crawl = descobrir_urls_produto(url, _fetch_http)
    frames = []
    for prod_url in crawl.urls:
        html = _fetch_http(prod_url)
        if not html:
            continue
        df = instant_extract(html, prod_url)
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    return auto_heal_dataframe(pd.concat(frames, ignore_index=True), url)


def run_scraper(url: str):
    url = str(url or "").strip()
    if not url:
        return pd.DataFrame()

    supplier = MegaCenterSupplier()

    strategies = {
        "supplier": lambda u: pd.DataFrame(supplier.fetch(u)) if supplier.can_handle(u) else pd.DataFrame(),
        "instant_dom": _run_instant,
        "browser": run_browser_scraper,
        "fallback": _run_fallback,
    }

    result = run_autonomous_agent(url, strategies)
    return result.dataframe
