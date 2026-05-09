from __future__ import annotations

from bling_app_zero.ui.layout.components import inject_clean_home_css
from bling_app_zero.ui.unified_light_layout import inject_unified_light_layout


def inject_app_layout() -> None:
    """Ponto único oficial para aplicar o layout global do sistema."""
    inject_unified_light_layout()


__all__ = ['inject_app_layout', 'inject_clean_home_css', 'inject_unified_light_layout']
