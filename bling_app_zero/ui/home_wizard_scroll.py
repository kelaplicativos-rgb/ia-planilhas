from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_wizard_constants import STEP_MAPEAMENTO, STEP_OPERACAO, STEP_ORIGEM

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_wizard_scroll.py'
SCROLL_TARGET_KEY = 'home_wizard_scroll_target_step'
MAPPING_FIELDS_ANCHOR_ID = 'bling-mapping-fields-anchor'


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


def render_mapping_fields_anchor() -> None:
    st.markdown(
        f'<div id="{MAPPING_FIELDS_ANCHOR_ID}" data-bling-scroll-anchor="mapping-fields" style="position:relative; top:-84px; height:1px;"></div>',
        unsafe_allow_html=True,
    )


def inject_scroll_to_target() -> None:
    target = str(st.session_state.pop(SCROLL_TARGET_KEY, '') or '').strip().lower()
    if not target:
        return
    safe_target = ''.join(ch for ch in target if ch.isalnum() or ch in {'_', '-'})
    if not safe_target:
        return
    primary_id = MAPPING_FIELDS_ANCHOR_ID if target == STEP_MAPEAMENTO else f'bling-step-{safe_target}'
    fallback_id = f'bling-step-{safe_target}'
    primary_selector = f'[data-bling-scroll-anchor="mapping-fields"]' if target == STEP_MAPEAMENTO else f'[data-bling-step="{safe_target}"]'
    fallback_selector = f'[data-bling-step="{safe_target}"]'
    components.html(
        f"""
<script>
(function () {{
  const w = window.parent;
  const d = w.document;
  const primaryId = {primary_id!r};
  const fallbackId = {fallback_id!r};
  const primarySelector = {primary_selector!r};
  const fallbackSelector = {fallback_selector!r};
  function findTarget() {{
    return d.getElementById(primaryId) || d.querySelector(primarySelector) || d.getElementById(fallbackId) || d.querySelector(fallbackSelector);
  }}
  function scrollToTarget() {{
    const target = findTarget();
    if (!target) return false;
    const rect = target.getBoundingClientRect();
    const currentY = w.scrollY || w.pageYOffset || d.documentElement.scrollTop || d.body.scrollTop || 0;
    const y = Math.max(0, currentY + rect.top - 72);
    try {{
      w.sessionStorage.setItem('home_wizard_scroll_y', String(y));
      w.sessionStorage.setItem('home_wizard_scroll_pending_restore', '1');
      w.sessionStorage.setItem('home_wizard_scroll_restoring_until', String(Date.now() + 2400));
    }} catch (e) {{}}
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
    add_audit_event('wizard_scroll_target_requested', area='WIZARD', step=target, status='OK', details={'target_step': target, 'primary_id': primary_id, 'responsible_file': RESPONSIBLE_FILE})


__all__ = ['inject_scroll_to_target', 'render_mapping_fields_anchor', 'render_step_anchor', 'set_scroll_target']
