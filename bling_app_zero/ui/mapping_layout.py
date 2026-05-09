from __future__ import annotations

"""Compatibilidade do layout antigo de mapeamento.

O layout oficial agora fica em ``bling_app_zero.ui.layout.mapping``.
Este arquivo permanece apenas para não quebrar imports antigos.
"""

from bling_app_zero.ui.layout.mapping import inject_mapping_css, render_mapping_preview, render_mapping_title

__all__ = ['inject_mapping_css', 'render_mapping_title', 'render_mapping_preview']
