from __future__ import annotations

# BLINGFIX: este módulo legado era mais permissivo que send_validation_v2.
# Manter dois guards diferentes deixava caminho para fluxo antigo/cache liberar
# cadastro sem categoria válida. A partir daqui, qualquer import antigo passa
# pela mesma validação rígida usada no envio final.
from bling_app_zero.core.send_validation_v2 import SendGuardResult, validate_before_bling_send

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_api_send_guard.py'

__all__ = ['SendGuardResult', 'validate_before_bling_send']
