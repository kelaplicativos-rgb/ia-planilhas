# GOD MODE RUNNER FINAL (ULTRA FIX)
from __future__ import annotations

import pandas as pd

from bling_app_zero.core.suppliers.megacenter import MegaCenterSupplier

from .autonomous_agent import run_autonomous_agent
from .god_mode_engine import run_god_mode_scraper
from .instant_dom_engine import instant_extract
from .auth_fetcher import fetch_html_with_auth
from .self_healing import auto_heal_dataframe


def _fetch_http(url: str, auth_context=None) -> str:
    return fetch_html_with_auth(url, auth_context=auth_context)


def _run_basic(url: str, auth_context=None) -> pd.DataFrame:
    html = _fetch_http(url, auth_context)
    if not html:
        return pd.DataFrame()
    df = instant_extract(html, url)
    if df.empty:
        return df
    return auto_heal_dataframe(df, url)


def run_scraper(url: str, auth_context=None):
    url = str(url or "").strip()
    if not url:
        return pd.DataFrame()

    supplier = MegaCenterSupplier()

    strategies = {
        "supplier": lambda u: pd.DataFrame(supplier.fetch(u, limite=5000, max_paginas=200, max_workers=8)) if supplier.can_handle(u) else pd.DataFrame(),
        "god_mode": lambda u: run_god_mode_scraper(u),
        "basic": lambda u: _run_basic(u, auth_context),
    }

    result = run_autonomous_agent(url, strategies)
    return result.dataframe
