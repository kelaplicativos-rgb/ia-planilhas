# bling_app_zero/core/instant_scraper/__init__.py

from __future__ import annotations

import pandas as pd

try:
    from .runner import run_scraper as _run_scraper
except Exception:
    _run_scraper = None

try:
    from .flash_stock_runner import run_flash_scraper
except Exception:
    try:
        from .flash_scraper import run_flash_scraper
    except Exception:
        run_flash_scraper = None


def run_scraper(url: str, *args, **kwargs) -> pd.DataFrame:
    if _run_scraper is None:
        return pd.DataFrame()
    try:
        return _run_scraper(url, *args, **kwargs)
    except TypeError:
        return _run_scraper(url)
    except Exception:
        return pd.DataFrame()


def run_flash(url: str, *args, **kwargs) -> pd.DataFrame:
    if run_flash_scraper is None:
        return pd.DataFrame()
    try:
        return run_flash_scraper(url, *args, **kwargs)
    except TypeError:
        return run_flash_scraper(url)
    except Exception:
        return pd.DataFrame()


def buscar_dataframe(url: str, *args, **kwargs) -> pd.DataFrame:
    return run_scraper(url, *args, **kwargs)


def buscar_produtos(url: str, *args, **kwargs) -> pd.DataFrame:
    return run_scraper(url, *args, **kwargs)


__all__ = [
    "run_scraper",
    "run_flash",
    "run_flash_scraper",
    "buscar_dataframe",
    "buscar_produtos",
]
