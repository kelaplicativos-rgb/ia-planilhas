from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/success_banner.py'


def render_congratulations_success(*, area: str = 'FINAL', context: str = '') -> None:
    st.success('Congratulations Success 👏')
    add_audit_event(
        'mapeiaai_congratulations_success_rendered',
        area=area,
        status='OK',
        details={
            'context': context,
            'message': 'Congratulations Success 👏',
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


__all__ = ['render_congratulations_success']
