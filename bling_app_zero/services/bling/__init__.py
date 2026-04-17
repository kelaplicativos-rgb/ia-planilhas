
from __future__ import annotations

"""
Pacote de serviços de integração com o Bling (API v3).

Este pacote centraliza:
- sincronização de produtos
- envio de dados
- estratégias de atualização

Uso padrão no sistema:

    from bling_app_zero.services.bling import sincronizar_produtos_bling
"""

# ============================================================
# IMPORTS PRINCIPAIS
# ============================================================

from .bling_sync import (
    sincronizar_produtos_bling,
    enviar_produtos,
    SyncConfig,
)

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "sincronizar_produtos_bling",
    "enviar_produtos",
    "SyncConfig",
]

# ============================================================
# METADADOS (opcional para debug interno)
# ============================================================

BLING_SERVICE_VERSION = "1.0.0"
BLING_SERVICE_NAME = "bling_services_core"
