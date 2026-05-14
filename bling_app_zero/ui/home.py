from __future__ import annotations

from bling_app_zero.ui.home_router import render_home_router
from bling_app_zero.ui.layout import inject_app_layout, render_compact_hero
from bling_app_zero.ui.scroll_position import inject_scroll_position_keeper
from bling_app_zero.ui.wizard_state_guard import run_wizard_state_guard


def render_home() -> None:
    from bling_app_zero.ui.home_autofluxo import run_home_autofluxo

    run_wizard_state_guard()
    run_home_autofluxo()
    inject_app_layout()
    inject_scroll_position_keeper()
    render_compact_hero()
    render_home_router()


__all__ = ['render_home']
