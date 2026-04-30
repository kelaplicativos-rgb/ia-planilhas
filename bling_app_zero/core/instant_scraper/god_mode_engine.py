from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from .auto_learning import aprender_padrao, aplicar_padrao_aprendido
from .domain_crawler import descobrir_urls_produto
from .html_fetcher import fetch_html
from .instant_dom_engine import instant_extract
from .playwright_engine import browser_extract
from .self_healing import auto_heal_dataframe, diagnosticar_dataframe


@dataclass
class GodModeConfig:
    max_product_urls: int = 80
    max_browser_pages: int = 12
    min_score: int = 65


def _safe_df(df: object) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df.copy().fillna("").reset_index(drop=True)
    return pd.DataFrame()


def _score(df: pd.DataFrame) -> int:
    try:
        return int(diagnosticar_dataframe(df).get("score", 0))
    except Exception:
        return 0


def _finalizar(df: pd.DataFrame, url: str, fonte: str) -> pd.DataFrame:
    base = _safe_df(df)
    if base.empty:
        return pd.DataFrame()

    base = aplicar_padrao_aprendido(url, base)
    base = auto_heal_dataframe(base, url)
    base = _safe_df(base)

    if base.empty:
        return pd.DataFrame()

    base["agente_estrategia"] = fonte
    base["agente_score"] = str(_score(base))
    aprender_padrao(url, base, fonte=fonte)
    return base.reset_index(drop=True)


def _fetch(url: str) -> str:
    try:
        return fetch_html(url, force_refresh=True)
    except Exception:
        return ""


def _extrair_http_dom(url: str) -> pd.DataFrame:
    html = _fetch(url)
    if not html:
        return pd.DataFrame()
    return instant_extract(html, url, min_score=30)


def run_god_mode_scraper(
    url: str,
    *,
    config: GodModeConfig | None = None,
    progress_callback: Callable[[int, str, int], None] | None = None,
) -> pd.DataFrame:
    """
    GOD MODE: orquestração agressiva, mas segura.

    Estratégias:
    1. reaplica padrão aprendido por domínio;
    2. tenta DOM estático na URL inicial;
    3. renderiza browser real com cliques e scroll;
    4. descobre URLs de produtos por sitemap/links internos;
    5. renderiza até algumas páginas com browser quando HTTP não resolve.
    """
    config = config or GodModeConfig()
    url = str(url or "").strip()
    if not url:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []

    def progress(percent: int, msg: str, total: int = 0) -> None:
        if progress_callback:
            try:
                progress_callback(percent, msg, total)
            except Exception:
                pass

    progress(3, "GOD MODE iniciado: analisando DOM inicial...", 0)

    df_http = _finalizar(_extrair_http_dom(url), url, "god_http_dom")
    if not df_http.empty:
        frames.append(df_http)
        if _score(df_http) >= config.min_score and len(df_http) >= 5:
            progress(100, "GOD MODE finalizado via DOM inicial.", len(df_http))
            return df_http

    progress(18, "GOD MODE abrindo browser real com cliques automáticos...", len(df_http))
    browser_result = browser_extract(url, max_clicks=8, progress_callback=progress)
    df_browser = _finalizar(browser_result.dataframe, url, "god_browser_click_scroll")
    if not df_browser.empty:
        frames.append(df_browser)
        if _score(df_browser) >= config.min_score and len(df_browser) >= 5:
            progress(100, "GOD MODE finalizado via browser.", len(df_browser))
            return df_browser

    progress(45, "GOD MODE descobrindo URLs internas de produtos...", 0)
    crawl = descobrir_urls_produto(url, _fetch, max_urls=config.max_product_urls, max_paginas_base=40)
    produto_urls = list(dict.fromkeys(crawl.urls or []))[: config.max_product_urls]

    for idx, produto_url in enumerate(produto_urls, start=1):
        percent = 45 + int((idx / max(len(produto_urls), 1)) * 45)
        progress(percent, f"GOD MODE lendo produto {idx}/{len(produto_urls)}", idx)

        df_prod = _finalizar(_extrair_http_dom(produto_url), url, "god_product_http")
        if df_prod.empty and idx <= config.max_browser_pages:
            df_prod = _finalizar(browser_extract(produto_url, max_clicks=2).dataframe, url, "god_product_browser")

        if not df_prod.empty:
            frames.append(df_prod)

    if not frames:
        progress(100, "GOD MODE sem resultado.", 0)
        return pd.DataFrame()

    final = _finalizar(pd.concat(frames, ignore_index=True, sort=False), url, "god_mode_final")
    if not final.empty:
        if "url_produto" in final.columns and "nome" in final.columns:
            final = final.drop_duplicates(subset=["url_produto", "nome"], keep="first")
        elif "nome" in final.columns and "preco" in final.columns:
            final = final.drop_duplicates(subset=["nome", "preco"], keep="first")
        else:
            final = final.drop_duplicates(keep="first")

    progress(100, "GOD MODE finalizado.", len(final))
    return final.reset_index(drop=True)
