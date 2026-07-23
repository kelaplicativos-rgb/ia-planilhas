from __future__ import annotations

from bling_app_zero.ui.cadastro_entry_step import render_cadastro_entrada_step

RESPONSIBLE_FILE = 'bling_app_zero/ui/cadastro_panel.py'


def render_cadastro_panel() -> None:
    render_cadastro_entrada_step()


__all__ = ['RESPONSIBLE_FILE', 'render_cadastro_panel']
