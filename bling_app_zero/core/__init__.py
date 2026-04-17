
from __future__ import annotations

"""
Core do projeto IA Planilhas → Bling.

Este pacote concentra módulos centrais do sistema, como:
- autenticação OAuth com Bling
- sessão do usuário
- integração com API
- serviços internos de origem e processamento

Importe daqui apenas os módulos já estabilizados para evitar
quebra circular entre UI, services e core.
"""

# ============================================================
# EXPORTS DISPONÍVEIS
# ============================================================

from . import bling_auth

__all__ = [
    "bling_auth",
]

# ============================================================
# METADADOS
# ============================================================

CORE_PACKAGE_NAME = "bling_app_zero.core"
CORE_PACKAGE_VERSION = "1.0.0"
