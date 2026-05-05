from __future__ import annotations

"""Instant Scraper exports.

Exports compatíveis para o modo Flash Amplo página por página.
"""

try:
    from bling_app_zero.core.instant_scraper.flash_amplo_page_mode import (
        flash_amplo_dataframe,
        flash_amplo_rows,
        run_flash_amplo,
        run_flash_amplo_page_mode,
    )
except Exception:  # pragma: no cover
    flash_amplo_dataframe = None  # type: ignore[assignment]
    flash_amplo_rows = None  # type: ignore[assignment]
    run_flash_amplo = None  # type: ignore[assignment]
    run_flash_amplo_page_mode = None  # type: ignore[assignment]


__all__ = [
    "flash_amplo_dataframe",
    "flash_amplo_rows",
    "run_flash_amplo",
    "run_flash_amplo_page_mode",
]
