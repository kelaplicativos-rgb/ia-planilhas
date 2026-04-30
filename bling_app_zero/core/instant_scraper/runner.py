# bling_app_zero/core/instant_scraper/runner.py

from __future__ import annotations

import pandas as pd

from bling_app_zero.core.suppliers.megacenter import MegaCenterSupplier

from .html_fetcher import fetch_html
from .pagination import coletar_paginas_genericas
from .domain_crawler import descobrir_urls_produto
from .ultra_detector import detectar_blocos_repetidos
from .ultra_extractor import extrair_lista
from .instant_dom_engine import instant_extract
from .ai_normalizer import normalizar_produtos_ai
from .gpt_enricher import enriquecer_produtos_gpt
from .auto_learning import aprender_padrao, aplicar_padrao_aprendido
from .self_healing import auto_heal_dataframe, diagnosticar_dataframe


MAX_CANDIDATOS = 5
MAX_PAGINAS_INSTANT = 8


def _normalizar_df(df):
    if df is None or df.empty:
        return pd.DataFrame()
    return df.copy().fillna("").reset_index(drop=True)


def _finalizar_df(df: pd.DataFrame, url_base: str = "") -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    base = df.copy().fillna("")

    if url_base:
        base = aplicar_padrao_aprendido(url_base, base)

    # 🔥 SELF HEALING ENTRA AQUI
    base = auto_heal_dataframe(base, url_base)

    if "url_produto" in base.columns and "nome" in base.columns:
        base = base.drop_duplicates(subset=["url_produto", "nome"], keep="first")
    elif "url_produto" in base.columns:
        base = base.drop_duplicates(subset=["url_produto"], keep="first")
    elif "nome" in base.columns:
        base = base.drop_duplicates(subset=["nome"], keep="first")

    base = normalizar_produtos_ai(base)
    base = enriquecer_produtos_gpt(base, limite=30, score_minimo=50)

    if url_base and not base.empty:
        aprender_padrao(url_base, base, fonte="ultra_scraper")

    return _normalizar_df(base)


def _fetch_http(url: str) -> str:
    return fetch_html(url, force_refresh=True)


def _extrair_instant_da_pagina(html: str, url: str) -> pd.DataFrame:
    try:
        return instant_extract(html, url)
    except Exception:
        return pd.DataFrame()


def _extrair_fallback_antigo(html, url):
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


def _extrair_da_pagina(html, url):
    df_instant = _extrair_instant_da_pagina(html, url)
    if not df_instant.empty:
        return df_instant
    return _extrair_fallback_antigo(html, url)


def _run_instant(url: str) -> pd.DataFrame:
    paginas = coletar_paginas_genericas(url, _fetch_http, max_paginas=MAX_PAGINAS_INSTANT)

    frames = []

    for pagina_url in paginas.urls:
        html = _fetch_http(pagina_url)
        if not html:
            continue

        df = _extrair_da_pagina(html, pagina_url)
        if not df.empty:
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    return _finalizar_df(pd.concat(frames, ignore_index=True), url)


def _run_god_mode(url):
    crawl = descobrir_urls_produto(url, _fetch_http)

    frames = []

    for prod_url in crawl.urls:
        html = _fetch_http(prod_url)
        if not html:
            continue

        df = _extrair_da_pagina(html, prod_url)
        if not df.empty:
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    return _finalizar_df(pd.concat(frames, ignore_index=True), url)


def run_scraper(url: str):
    url = str(url or "").strip()
    if not url:
        return pd.DataFrame()

    supplier = MegaCenterSupplier()
    if supplier.can_handle(url):
        produtos = supplier.fetch(url)
        return _finalizar_df(pd.DataFrame(produtos), url)

    df_instant = _run_instant(url)
    if not df_instant.empty:
        return df_instant

    df_god = _run_god_mode(url)
    if not df_god.empty:
        return df_god

    return pd.DataFrame()
