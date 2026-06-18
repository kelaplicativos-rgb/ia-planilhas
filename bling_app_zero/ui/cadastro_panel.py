from __future__ import annotations

import streamlit as st

RESPONSIBLE_FILE = 'bling_app_zero/ui/cadastro_panel.py'


def render_cadastro_panel(*args, **kwargs) -> None:
    """Compatibilidade para imports legados.

    O fluxo atual usa o wizard/universal_entry_step. Este painel permanece
    importável para CI, patches antigos e chamadas legadas não quebrarem.
    """
    _ = args, kwargs
    st.caption('Cadastro de produtos é conduzido pelo fluxo principal.')


def render_panel(*args, **kwargs) -> None:
    render_cadastro_panel(*args, **kwargs)


__all__ = ['RESPONSIBLE_FILE', 'render_cadastro_panel', 'render_panel']
