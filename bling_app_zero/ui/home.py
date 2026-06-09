from __future__ import annotations

from datetime import datetime

import streamlit as st

from bling_app_zero.core import APP_VERSION
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.alerts import enforce_attention_alert_policy
from bling_app_zero.ui.bottom_nav import render_bottom_nav
from bling_app_zero.ui.home_router import render_home as render_home_router
from bling_app_zero.ui.layout import inject_app_layout, render_compact_hero
from bling_app_zero.ui.scroll_position import inject_scroll_position_keeper
from bling_app_zero.ui.wizard_state_guard import run_wizard_state_guard

RESPONSIBLE_FILE = 'bling_app_zero/ui/home.py'
RUNTIME_STAMP_KEY = 'blingfix_runtime_route_stamp_rendered_v1'


def _render_blingfix_runtime_stamp() -> None:
    """Mostra e registra a prova da rota ativa carregada pelo Streamlit.

    Esse carimbo existe para encerrar a dúvida de correções aplicadas no arquivo errado.
    Se ele aparecer no app e no diagnóstico, a Home ativa veio por este arquivo.
    """
    rendered_at = datetime.utcnow().isoformat(timespec='seconds') + 'Z'
    st.session_state['blingfix_runtime_route_version'] = APP_VERSION
    st.session_state['blingfix_runtime_route_file'] = RESPONSIBLE_FILE
    st.session_state['blingfix_runtime_route_rendered_at'] = rendered_at

    st.markdown(
        f'''
<div style="border:1px solid rgba(234,88,12,.32);background:rgba(255,237,213,.70);color:#7c2d12;border-radius:14px;padding:.62rem .72rem;margin:.35rem 0 .7rem 0;font-size:.82rem;line-height:1.35;font-weight:800;">
  BLINGFIX ativo · versão <code>{APP_VERSION}</code> · rota <code>{RESPONSIBLE_FILE}</code>
</div>
''',
        unsafe_allow_html=True,
    )

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
                'purpose': 'prove_active_route_after_blingfix',
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
    render_home_router()
    render_bottom_nav()


__all__ = ['render_home']
