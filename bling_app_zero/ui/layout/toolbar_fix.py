from __future__ import annotations


def inject_streamlit_toolbar_fix() -> None:
    """Compatibilidade sem CSS próprio.

    Tema único oficial: bling_app_zero/ui/layout/theme.py.
    A visibilidade da toolbar deve ser controlada pelo tema mestre.
    """
    return None


__all__ = ['inject_streamlit_toolbar_fix']
