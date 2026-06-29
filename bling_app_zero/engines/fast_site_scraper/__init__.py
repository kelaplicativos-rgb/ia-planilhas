from __future__ import annotations

from bling_app_zero.engines.fast_site_scraper.wbuy_cards_patch import install as _install_wbuy_cards_patch

_install_wbuy_cards_patch()

from bling_app_zero.engines.fast_site_scraper.engine import run_fast_site_scraper

__all__ = ['run_fast_site_scraper']
