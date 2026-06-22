from __future__ import annotations

from datetime import datetime

import streamlit as st

from bling_app_zero.core import APP_VERSION
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.alerts import enforce_attention_alert_policy
from bling_app_zero.ui.bottom_nav import render_bottom_nav, render_persistent_operation_controls
from bling_app_zero.ui.home_official import render_home as render_home_router, should_render_official_landing
from bling_app_zero.ui.layout import inject_app_layout
from bling_app_zero.ui.scroll_position import inject_scroll_position_keeper
from bling_app_zero.ui.wizard_state_guard import run_wizard_state_guard

RESPONSIBLE_FILE = 'bling_app_zero/ui/home.py'
RUNTIME_STAMP_KEY = 'blingfix_runtime_route_stamp_rendered_v1'


def _render_blingfix_runtime_stamp() -> None:
    """Registra a prova da rota ativa sem poluir a interface principal."""
    rendered_at = datetime.utcnow().isoformat(timespec='seconds') + 'Z'
    st.session_state['blingfix_runtime_route_version'] = APP_VERSION
    st.session_state['blingfix_runtime_route_file'] = RESPONSIBLE_FILE
    st.session_state['blingfix_runtime_route_rendered_at'] = rendered_at

    if not bool(st.session_state.get(RUNTIME_STAMP_KEY)):
        st.session_state[RUNTIME_STAMP_KEY] = True
        add_audit_event(
            'blingfix_runtime_route_stamp_visible',
            area='APP',
            status='OK',
            details={
                'version': APP_VERSION,
                'responsible_file': RESPONSIBLE_FILE,
                'rendered_at_utc': rendered_at,
                'purpose': 'official_dual_card_home_entry_active',
            },
        )


def render_home() -> None:
    from bling_app_zero.ui.home_autofluxo import run_home_autofluxo

    enforce_attention_alert_policy()
    run_wizard_state_guard()
    run_home_autofluxo()
    inject_app_layout()
    inject_scroll_position_keeper()
    _render_blingfix_runtime_stamp()

    # BLINGFIX 2026-06-22:
    # A landing oficial precisa nascer limpa na HOME, mesmo quando o navegador
    # mantém querystring antiga (?operation_v2=...). Só mostramos controles de
    # fluxo quando a rota foi autorizada por clique real nos cards oficiais.
    official_landing = should_render_official_landing()
    if not official_landing:
        render_persistent_operation_controls()
    render_home_router()
    if not official_landing:
        render_bottom_nav()


__all__ = ['render_home']
