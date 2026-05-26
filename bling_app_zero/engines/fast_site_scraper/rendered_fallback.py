from __future__ import annotations

from typing import Callable

from bling_app_zero.engines.devtools_scraper.enhancer import enhance_with_rendered_page, needs_rendered_fallback
from bling_app_zero.engines.fast_site_scraper.constants import DEVTOOLS_FALLBACK_MAX_PER_RUN
from bling_app_zero.engines.fast_site_scraper.models import FastProductData
from bling_app_zero.engines.fast_site_scraper.progress import emit
from bling_app_zero.engines.fast_site_scraper.scrape_worker import log_rich_description_result


def enhance_products_sequentially(
    products_by_url: list[tuple[str, FastProductData]],
    needed: set[str],
    progress_callback: Callable[[dict], None] | None,
) -> tuple[list[FastProductData], int]:
    enhanced_products: list[FastProductData] = []
    used = 0
    total_candidates = sum(1 for _, product in products_by_url if needs_rendered_fallback(product, needed))

    for url, product in products_by_url:
        if used < DEVTOOLS_FALLBACK_MAX_PER_RUN and needs_rendered_fallback(product, needed):
            emit(progress_callback, {
                'stage': 'Reforço DevTools',
                'message': f'Reforçando página dinâmica {used + 1}/{min(total_candidates, DEVTOOLS_FALLBACK_MAX_PER_RUN)} sem paralelo.',
                'progress': 0.89,
                'devtools': used,
            })
            product = enhance_with_rendered_page(url, product, needed)
            used += 1
            log_rich_description_result(url, product, needed)
        enhanced_products.append(product)
    return enhanced_products, used


__all__ = ['enhance_products_sequentially']
