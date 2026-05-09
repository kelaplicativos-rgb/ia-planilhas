from __future__ import annotations

"""Compatibilidade do tema antigo.

O tema oficial agora fica em ``bling_app_zero.ui.layout.theme``.
Este arquivo permanece apenas para não quebrar imports antigos.
"""

from bling_app_zero.ui.layout.theme import inject_unified_light_layout

__all__ = ['inject_unified_light_layout']
