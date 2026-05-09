from __future__ import annotations

"""Compatibilidade do layout antigo.

O layout oficial agora fica em ``bling_app_zero.ui.layout``.
Este arquivo permanece apenas para não quebrar imports antigos.
"""

from bling_app_zero.ui.layout.components import (
    close_home_start_card,
    inject_clean_home_css,
    render_compact_hero,
    render_compact_note,
    render_home_pricing_card,
    render_home_start_card,
    render_step_title,
)

__all__ = [
    'inject_clean_home_css',
    'render_compact_hero',
    'render_home_start_card',
    'render_home_pricing_card',
    'close_home_start_card',
    'render_step_title',
    'render_compact_note',
]
