"""Core compartilhado: configuração, erros, normalização, validação, GTIN, exportação e leitura."""

from __future__ import annotations

try:
    from bling_app_zero.core import multiloja_price_model_patch as _multiloja_price_model_patch
    _multiloja_price_model_patch.install()
except Exception:
    pass

try:
    from bling_app_zero.core import category_intelligence as _category_intelligence
    from bling_app_zero.core.category_semantic_bridge import classify_dataframe_semantic as _classify_dataframe_semantic

    _category_intelligence.classify_dataframe = _classify_dataframe_semantic
except Exception:
    pass

from bling_app_zero.core.app_config import APP_VERSION, PAGE_CONFIG
from bling_app_zero.core.app_errors import register_critical_error

__all__ = ['APP_VERSION', 'PAGE_CONFIG', 'register_critical_error']
