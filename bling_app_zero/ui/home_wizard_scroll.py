from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_wizard_constants import STEP_OPERACAO, STEP_ORIGEM

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
    primary_id = f'bling-step-{safe_target}'
    primary_selector = f'[data-bling-step="{safe_target}"]'
    components.html(
        f"""
<script>
(function () {{
  const w = window.parent;
  const d = w.document;
  const primaryId = {primary_id!r};
  const primarySelector = {primary_selector!r};
  function scrollingTargets() {{
    return [
      w,
      d.scrollingElement,
      d.documentElement,
      d.body,
      d.querySelector('[data-testid="stAppViewContainer"]'),
      d.querySelector('[data-testid="stMain"]'),
      d.querySelector('section.main'),
      d.querySelector('.main')
    ].filter(Boolean);
  }}
  function currentY() {{
    let y = 0;
    for (const el of scrollingTargets()) {{
      try {{
        const value = el === w ? (w.scrollY || w.pageYOffset || 0) : (el.scrollTop || 0);
        if (value > y) y = value;
      }} catch (e) {{}}
    }}
    return y;
  }}
  function applyScroll(y) {{
    for (const el of scrollingTargets()) {{
      try {{
        if (el === w) el.scrollTo(0, y);
        else el.scrollTop = y;
      }} catch (e) {{}}
    }}
  }}
  function findTarget() {{
    return d.getElementById(primaryId) || d.querySelector(primarySelector);
  }}
  function scrollToTarget() {{
    const target = findTarget();
    if (!target) return false;
    const rect = target.getBoundingClientRect();
    const y = Math.max(0, currentY() + rect.top - 72);
    try {{
      w.sessionStorage.setItem('home_wizard_scroll_y', String(y));
      w.sessionStorage.setItem('home_wizard_scroll_pending_restore', '1');
      w.sessionStorage.setItem('home_wizard_scroll_restoring_until', String(Date.now() + 2600));
    }} catch (e) {{}}
    applyScroll(y);
    return true;
  }}
  [0, 50, 100, 180, 320, 520, 900, 1400, 2100].forEach(delay => w.setTimeout(scrollToTarget, delay));
}})();
</script>
        """,
        height=0,
        width=0,
    )
    add_audit_event('wizard_scroll_target_requested', area='WIZARD', step=target, status='OK', details={'target_step': target, 'primary_id': primary_id, 'scroll_rule': 'top_of_step_for_all_flows', 'responsible_file': RESPONSIBLE_FILE})


__all__ = ['inject_scroll_to_target', 'render_mapping_fields_anchor', 'render_step_anchor', 'set_scroll_target']
