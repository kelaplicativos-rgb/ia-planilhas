from __future__ import annotations

from importlib import import_module


def render_universal_preview_step() -> None:
    module = import_module('bling_app_zero.ui.cadastro_preview_step')
    module.render_cadastro_preview_step()


__all__ = ['render_universal_preview_step']
