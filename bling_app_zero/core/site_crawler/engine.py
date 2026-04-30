from __future__ import annotations

# 🔥 FACHADA BLINGPERF
from .perf_engine import crawl_site_perf as crawl_site, buscar_produtos_site_perf as buscar_produtos_site

__all__ = [
    "crawl_site",
    "buscar_produtos_site",
]
