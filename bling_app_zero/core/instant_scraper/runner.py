# GOD MODE RUNNER FINAL (ULTRA FIX + CLICK SCRAPER)
from __future__ import annotations

import pandas as pd

from bling_app_zero.core.suppliers.megacenter import MegaCenterSupplier

from .autonomous_agent import run_autonomous_agent
from .god_mode_engine import run_god_mode_scraper
from .instant_dom_engine import instant_extract
from .click_scraper import auto_click_extract
from .auth_fetcher import fetch_html_with_auth
from .self_healing import auto_heal_dataframe


def _emit_progress(progress_callback, percent: int, message: str, step: int = 0) -> None:
    if not progress_callback:
        return
    try:
        progress_callback(int(percent), str(message), int(step))
    except Exception:
        pass


def _safe_dataframe(value) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.fillna("").reset_index(drop=True)
    return pd.DataFrame()


def _fetch_http(url: str, auth_context=None) -> str:
    return fetch_html_with_auth(url, auth_context=auth_context)


def _run_basic(url: str, auth_context=None, progress_callback=None) -> pd.DataFrame:
    _emit_progress(progress_callback, 20, "Baixando HTML", 1)
    html = _fetch_http(url, auth_context)
    if not html:
        return pd.DataFrame()

    _emit_progress(progress_callback, 45, "Detectando estruturas repetidas", 2)
    df = instant_extract(html, url)
    if df.empty:
        _emit_progress(progress_callback, 65, "Tentando captura alternativa", 3)
        df = auto_click_extract(html, url)
    if df.empty:
        return df
    return auto_heal_dataframe(df, url)


def run_scraper(url: str, auth_context=None, config=None, progress_callback=None, **kwargs):
    url = str(url or "").strip()
    if not url:
        return pd.DataFrame()

    _emit_progress(progress_callback, 5, "Iniciando captura", 0)
    supplier = MegaCenterSupplier()

    strategies = {
        "instant_dom": lambda u: instant_extract(_fetch_http(u, auth_context), u),
        "click_scraper": lambda u: auto_click_extract(_fetch_http(u, auth_context), u),
        "supplier": lambda u: pd.DataFrame(supplier.fetch(u, limite=5000, max_paginas=200, max_workers=8)) if supplier.can_handle(u) else pd.DataFrame(),
        "god_mode": lambda u: run_god_mode_scraper(u),
        "basic": lambda u: _run_basic(u, auth_context, progress_callback),
    }

    try:
        result = run_autonomous_agent(url, strategies)
        df = _safe_dataframe(result.dataframe)
    except Exception:
        df = pd.DataFrame()

    if df.empty:
        for name in ("supplier", "instant_dom", "click_scraper", "basic", "god_mode"):
            try:
                df = _safe_dataframe(strategies[name](url))
            except Exception:
                df = pd.DataFrame()
            if not df.empty:
                break

    if not df.empty:
        df["origem_scraper_real"] = df.get("origem_scraper_real", "instant_scraper")
        df["url_captura"] = df.get("url_captura", url)
        _emit_progress(progress_callback, 100, f"Captura concluída: {len(df)} linhas", 4)
        return df.fillna("").reset_index(drop=True)

    _emit_progress(progress_callback, 100, "Nenhuma estrutura útil encontrada", 4)
    return pd.DataFrame()
