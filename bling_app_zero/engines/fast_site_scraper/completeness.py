from __future__ import annotations

from bling_app_zero.engines.fast_site_scraper.constants import (
    SMART_COMPLETE_TARGET,
    SMART_STOP_COMPLETE_RATIO,
    SMART_STOP_MIN_FOUND,
    SMART_STOP_MIN_PROCESSED,
    SMART_STOP_NO_GAIN_WINDOW,
)
from bling_app_zero.engines.fast_site_scraper.contract_rules import value_for_kind
from bling_app_zero.engines.fast_site_scraper.models import FastProductData


def is_complete_product(product: FastProductData, important_kinds: set[str]) -> bool:
    for kind in important_kinds:
        value = str(value_for_kind(product, kind) or '').strip()
        if not value:
            return False
    return True


def should_stop_early(*, processed: int, products: list[FastProductData], complete_count: int, last_gain_at: int) -> tuple[bool, str]:
    found = len(products)
    if complete_count >= SMART_COMPLETE_TARGET:
        return True, f'{complete_count} produto(s) completos encontrados.'
    if processed >= SMART_STOP_MIN_PROCESSED and found >= SMART_STOP_MIN_FOUND:
        ratio = complete_count / max(found, 1)
        if ratio >= SMART_STOP_COMPLETE_RATIO:
            return True, f'{complete_count}/{found} produto(s) com os principais campos preenchidos.'
    if processed - last_gain_at >= SMART_STOP_NO_GAIN_WINDOW and found >= SMART_STOP_MIN_FOUND:
        return True, 'A busca parou porque os últimos links não trouxeram novos produtos úteis.'
    return False, ''


__all__ = ['is_complete_product', 'should_stop_early']
