from __future__ import annotations

from importlib import import_module


def render_universal_mapeamento_step() -> None:
    module = import_module('bling_app_zero.ui.cadastro_mapping_step')
    module.render_cadastro_mapeamento_step()


__all__ = ['render_universal_mapeamento_step']
