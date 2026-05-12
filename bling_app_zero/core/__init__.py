"""Core compartilhado: configuração, erros, normalização, validação, GTIN, exportação e leitura."""

from __future__ import annotations

from bling_app_zero.core.app_config import APP_VERSION, PAGE_CONFIG
from bling_app_zero.core.app_errors import register_critical_error

__all__ = ['APP_VERSION', 'PAGE_CONFIG', 'register_critical_error']
