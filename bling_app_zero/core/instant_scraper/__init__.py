from __future__ import annotations

"""Instant Scraper exports.

Exports compatíveis para o modo Flash Amplo página por página.

Não silenciar erro de import aqui é intencional: se o motor Flash Amplo quebrar,
o Streamlit deve mostrar o erro real em vez de transformar a função em None e
falhar depois com `NoneType is not callable`.
"""

from bling_app_zero.core.instant_scraper.flash_amplo_page_mode import (
    flash_amplo_dataframe,
    flash_amplo_rows,
    run_flash_amplo,
    run_flash_amplo_page_mode,
)


__all__ = [
    "flash_amplo_dataframe",
    "flash_amplo_rows",
    "run_flash_amplo",
    "run_flash_amplo_page_mode",
]
