from __future__ import annotations

import streamlit as st

RESPONSIBLE_FILE = 'bling_app_zero/ui/alerts.py'


def inject_alert_theme() -> None:
    return None


def render_alert(message: str, *, title: str | None = None, variant: str = 'warning', icon: str | None = None) -> None:
    text = str(message or '').strip()
    if not text:
        return
    prefix = str(title or '').strip()
    output = f'{prefix}: {text}' if prefix else text
    method_name = variant if variant in {'warning', 'error', 'success', 'info'} else 'warning'
    getattr(st, method_name)(output)


__all__ = ['inject_alert_theme', 'render_alert']
