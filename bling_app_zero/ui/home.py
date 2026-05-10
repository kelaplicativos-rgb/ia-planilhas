from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.home_wizard import render_home_wizard
from bling_app_zero.ui.layout import inject_app_layout, render_compact_hero


def render_home() -> None:
    inject_app_layout()
    render_compact_hero()
    render_home_wizard()


__all__ = ['render_home']
