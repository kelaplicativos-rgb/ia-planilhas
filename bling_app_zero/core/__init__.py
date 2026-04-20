
from __future__ import annotations

"""
Core do projeto IA Planilhas → Bling.

🔥 BLINGFIX:
- Removido import automático de módulos
- Evita import circular
- Evita crash global no app

IMPORTANTE:
Sempre importar módulos diretamente, ex:
from bling_app_zero.core import bling_auth  ❌ (não usar)
from bling_app_zero.core.bling_auth import BlingAuthManager ✅
"""

# ============================================================
# EXPORTS (NÃO IMPORTAR AUTOMÁTICO)
# ============================================================

__all__ = []

# ============================================================
# METADADOS
# ============================================================

CORE_PACKAGE_NAME = "bling_app_zero.core"
CORE_PACKAGE_VERSION = "1.0.1"
