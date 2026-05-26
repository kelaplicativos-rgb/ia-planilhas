from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_wizard_constants import STEP_OPERACAO, STEP_ORIGEM

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_wizard_scroll.py'
SCROLL_TARGET_KEY = 'home_wizard_scroll_target_step'


def set_scroll_target(step: str) -> None:
    if step == STEP_OPERACAO:
        step = STEP_ORIGEM
    if step:
        st.session_state[SCROLL_TARGET_KEY] = step


def render_step_anchor(step: str) -> None:
    safe_step = ''.join(ch for ch in str(step or '') if ch.isalnum() or ch in {'_', '-'})
    if safe_step:
        st.markdown(
            f'<div id="bling-step-{safe_step}" data-bling-step="{safe_step}" style="position:relative; top:-84px; height:1px;"></div>',
            unsafe_allow_html=True,
        )


def inject_scroll_to_target() -> None:
    target = str(st.session_state.pop(SCROLL_TARGET_KEY, '') or '').strip().lower()
    if not target:
        return
    safe_target = ''.join(ch for ch in target if ch.isalnum() or ch in {'_', '-'})
    if not safe_target:
        return
    components.html(
        f"""
<script>
(function () {{
  const w = window.parent;
  const d = w.document;
  const targetId = 'bling-step-{safe_target}';
  function findTarget() {{ return d.getElementById(targetId) || d.querySelector('[data-bling-step="{safe_target}"]'); }}
  function scrollToTarget() {{
    const target = findTarget();
    if (!target) return false;
    const rect = target.getBoundingClientRect();
    const currentY = w.scrollY || w.pageYOffset || d.documentElement.scrollTop || d.body.scrollTop || 0;
    const y = Math.max(0, currentY + rect.top - 72);
    try {{ w.sessionStorage.setItem('home_wizard_scroll_y', String(y)); }} catch (e) {{}}
    try {{ w.scrollTo({{ top: y, behavior: 'auto' }}); }} catch (e) {{ w.scrollTo(0, y); }}
    try {{ d.documentElement.scrollTop = y; d.body.scrollTop = y; }} catch (e) {{}}
    return true;
  }}
  [0, 80, 180, 320, 520, 900, 1400].forEach(delay => w.setTimeout(scrollToTarget, delay));
}})();
</script>
        """,
        height=0,
        width=0,
    )
    add_audit_event('wizard_scroll_target_requested', area='WIZARD', step=target, status='OK', details={'target_step': target, 'responsible_file': RESPONSIBLE_FILE})


__all__ = ['inject_scroll_to_target', 'render_step_anchor', 'set_scroll_target']
