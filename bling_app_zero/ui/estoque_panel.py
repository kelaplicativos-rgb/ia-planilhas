from __future__ import annotations

from bling_app_zero.ui.estoque_entry_step import render_estoque_entry_step

RESPONSIBLE_FILE = 'bling_app_zero/ui/estoque_panel.py'


def render_estoque_panel() -> None:
    render_estoque_entry_step()


__all__ = ['RESPONSIBLE_FILE', 'render_estoque_panel']
