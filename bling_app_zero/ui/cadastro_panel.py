from __future__ import annotations

"""Compatibilidade para rotas antigas do painel de cadastro.

O fluxo oficial fica em ``bling_app_zero.ui.cadastro_panel_modular``.
Este arquivo permanece para não quebrar imports antigos, mas não mantém mais
uma cópia paralela da tela de cadastro.
"""

from bling_app_zero.ui.cadastro_panel_modular import render_cadastro_panel

__all__ = ['render_cadastro_panel']
