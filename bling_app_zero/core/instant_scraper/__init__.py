# bling_app_zero/core/instant_scraper/__init__.py

from __future__ import annotations

try:
    from .runner import buscar_dataframe, buscar_produtos, run_scraper
except Exception:
    run_scraper = None
    buscar_dataframe = None
    buscar_produtos = None


__all__ = [
    "run_scraper",
    "buscar_dataframe",
    "buscar_produtos",
]
