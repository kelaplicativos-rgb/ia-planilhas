from __future__ import annotations

from bling_app_zero.core.ncm.ncm_engine import suggest_ncm_for_product
from bling_app_zero.core.ncm.ncm_service import apply_ncm_suggestions
from bling_app_zero.core.ncm.ncm_types import EMPTY_NCM_SUGGESTION, NcmSuggestion

__all__ = [
    'EMPTY_NCM_SUGGESTION',
    'NcmSuggestion',
    'apply_ncm_suggestions',
    'suggest_ncm_for_product',
]
