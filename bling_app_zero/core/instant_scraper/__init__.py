from __future__ import annotations

from .browser_engine import BrowserScraperConfig, BrowserScraperResult, run_browser_scraper
from .engine import FlashScraperEngine, FlashScraperResult, run_flash_scraper
from .smart_fields import FieldRequest, build_field_requests

__all__ = [
    "BrowserScraperConfig",
    "BrowserScraperResult",
    "FlashScraperEngine",
    "FlashScraperResult",
    "FieldRequest",
    "build_field_requests",
    "run_browser_scraper",
    "run_flash_scraper",
]
