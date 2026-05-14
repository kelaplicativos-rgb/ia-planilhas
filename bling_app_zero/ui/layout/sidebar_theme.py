from __future__ import annotations


def inject_sidebar_tools_theme() -> None:
    """Compatibilidade sem CSS próprio.

    Tema único oficial: bling_app_zero/ui/layout/theme.py.
    A sidebar deve herdar somente o tema mestre.
    """
    return None


__all__ = ['inject_sidebar_tools_theme']
