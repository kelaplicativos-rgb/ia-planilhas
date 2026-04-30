# GOD MODE RUNNER FINAL
from __future__ import annotations

import pandas as pd

from bling_app_zero.core.suppliers.megacenter import MegaCenterSupplier

from .autonomous_agent import run_autonomous_agent
from .god_mode_engine import run_god_mode_scraper
from .instant_dom_engine import instant_extract
from .html_fetcher import fetch_html
from .self_healing import auto_heal_dataframe


def _fetch_http(url: str) -> str:
    return fetch_html(url, force_refresh=True)


def _run_basic(url: str) -> pd.DataFrame:
    html = _fetch_http(url)
    if not html:
        return pd.DataFrame()
    df = instant_extract(html, url)
    if df.empty:
        return df
    return auto_heal_dataframe(df, url)


def run_scraper(url: str):
    url = str(url or "").strip()
    if not url:
        return pd.DataFrame()

    supplier = MegaCenterSupplier()

    strategies = {
        "supplier": lambda u: pd.DataFrame(supplier.fetch(u)) if supplier.can_handle(u) else pd.DataFrame(),
        "god_mode": run_god_mode_scraper,
        "basic": _run_basic,
    }

    result = run_autonomous_agent(url, strategies)
    return result.dataframe
