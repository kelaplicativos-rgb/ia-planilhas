# bling_app_zero/core/instant_scraper/runner.py

from __future__ import annotations

import pandas as pd

from bling_app_zero.core.suppliers.megacenter import MegaCenterSupplier

from .html_fetcher import fetch_html, obter_ultimo_fetch_info
from .browser_fetcher import fetch_html_browser
from .pagination import coletar_paginas_genericas
from .domain_crawler import descobrir_urls_produto
from .ultra_detector import detectar_blocos_repetidos
from .ultra_extractor import extrair_lista
from .ai_normalizer import normalizar_produtos_ai


MAX_CANDIDATOS = 5


def _normalizar_df(df):
    if df is None or df.empty:
        return pd.DataFrame()
    return df.copy().fillna("").reset_index(drop=True)


def _fetch_hibrido(url):
    html = fetch_html(url)
    info = obter_ultimo_fetch_info()

    if html:
        if info.get("parece_javascript"):
            html_browser = fetch_html_browser(url)
            if html_browser:
                return html_browser
        return html

    return fetch_html_browser(url)


def _extrair_da_pagina(html, url):
    try:
        candidatos = detectar_blocos_repetidos(html)
    except Exception:
        return pd.DataFrame()

    frames = []

    for c in candidatos[:MAX_CANDIDATOS]:
        try:
            elementos = c.get("elements", [])[:80]
            produtos = extrair_lista(elementos, url)
            if produtos:
                frames.append(pd.DataFrame(produtos))
        except Exception:
            continue

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


def _run_generico(url):
    paginas = coletar_paginas_genericas(url, _fetch_hibrido, max_paginas=8)

    frames = []

    for pagina_url in paginas.urls:
        html = _fetch_hibrido(pagina_url)
        if not html:
            continue

        df = _extrair_da_pagina(html, pagina_url)
        if not df.empty:
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    final = pd.concat(frames, ignore_index=True)

    if "url_produto" in final.columns and "nome" in final.columns:
        final = final.drop_duplicates(subset=["url_produto", "nome"], keep="first")

    return normalizar_produtos_ai(final)


def _run_god_mode(url):
    crawl = descobrir_urls_produto(url, _fetch_hibrido)

    frames = []

    for prod_url in crawl.urls:
        html = _fetch_hibrido(prod_url)
        if not html:
            continue

        df = _extrair_da_pagina(html, prod_url)
        if not df.empty:
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    final = pd.concat(frames, ignore_index=True)

    if "url_produto" in final.columns:
        final = final.drop_duplicates(subset=["url_produto"], keep="first")

    return normalizar_produtos_ai(final)


def run_scraper(url: str):
    url = str(url or "").strip()
    if not url:
        return pd.DataFrame()

    supplier = MegaCenterSupplier()
    if supplier.can_handle(url):
        produtos = supplier.fetch(url)
        return normalizar_produtos_ai(pd.DataFrame(produtos))

    df_god = _run_god_mode(url)
    if not df_god.empty:
        return df_god

    return _run_generico(url)
