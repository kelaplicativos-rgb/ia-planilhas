from __future__ import annotations

from datetime import datetime

import streamlit as st

from bling_app_zero.core import APP_VERSION
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.alerts import enforce_attention_alert_policy
from bling_app_zero.ui.bottom_nav import render_bottom_nav, render_persistent_operation_controls
from bling_app_zero.ui.home_router import render_home as render_home_router
from bling_app_zero.ui.layout import inject_app_layout, render_compact_hero
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
                'purpose': 'silent_route_proof_after_minimal_ui_update',
            },
        )


def render_home() -> None:
    from bling_app_zero.ui.home_autofluxo import run_home_autofluxo

    enforce_attention_alert_policy()
    run_wizard_state_guard()
    run_home_autofluxo()
    inject_app_layout()
    inject_scroll_position_keeper()
    render_compact_hero()
    _render_blingfix_runtime_stamp()

    # Apenas os dois comandos essenciais carregam cedo. Diagnóstico, atalhos e
    # links auxiliares ficam para depois, reduzindo trabalho em aparelhos modestos.
    render_persistent_operation_controls()
    render_home_router()
    render_bottom_nav()


__all__ = ['render_home']
