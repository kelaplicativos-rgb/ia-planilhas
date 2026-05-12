from __future__ import annotations

import json
from typing import Any

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.user_rules import set_user_rules
from bling_app_zero.ui.home_wizard_constants import WIZARD_STEP_KEY

RULES_CENTER_READY_KEY = 'rules_center_reviewed'
RULES_CENTER_ADVANCED_KEY = 'rules_center_advanced_to_next_step'
RULES_CENTER_AUTOSAVE_SIGNATURE_KEY = 'rules_center_autosave_signature'


def rules_signature(rules: dict[str, Any]) -> str:
    try:
        return json.dumps(rules, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        return str(rules)


def clear_mapping_rule_cache() -> None:
    prefixes_to_clear = ('cad_map_', 'stk_map_', 'mapping_confidence_')
    exact_keys = {'mapping_confidence_cadastro', 'mapping_confidence_estoque_from_cadastro'}
    for key in list(st.session_state.keys()):
        text_key = str(key)
        if text_key.startswith('rules_center_'):
            continue
        if text_key in exact_keys or text_key.endswith('_order') or text_key.startswith(prefixes_to_clear):
            st.session_state.pop(key, None)


def auto_save_rules_if_changed(rules: dict[str, Any], previous_signature: str) -> None:
    normalized = set_user_rules(rules)
    current_signature = rules_signature(normalized)
    saved_signature = str(st.session_state.get(RULES_CENTER_AUTOSAVE_SIGNATURE_KEY) or previous_signature or '')
    if current_signature == saved_signature:
        st.session_state[RULES_CENTER_AUTOSAVE_SIGNATURE_KEY] = current_signature
        return

    st.session_state[RULES_CENTER_AUTOSAVE_SIGNATURE_KEY] = current_signature
    st.session_state[RULES_CENTER_READY_KEY] = True
    clear_mapping_rule_cache()
    add_audit_event(
        'rules_center_autosaved_instant',
        area='REGRAS',
        step=str(st.session_state.get(WIZARD_STEP_KEY) or ''),
        details={
            'ready_key': RULES_CENTER_READY_KEY,
            'ready': True,
            'effect': 'mapping_rule_badges_recomputed_immediately',
            'responsible_file': 'bling_app_zero/ui/rules_center_state.py',
        },
    )
    st.rerun()


def mark_rules_ready(rules: dict[str, Any], *, source: str) -> dict[str, Any]:
    normalized = set_user_rules(rules)
    st.session_state[RULES_CENTER_AUTOSAVE_SIGNATURE_KEY] = rules_signature(normalized)
    st.session_state[RULES_CENTER_READY_KEY] = True
    clear_mapping_rule_cache()
    add_audit_event(
        'rules_center_saved',
        area='REGRAS',
        step=str(st.session_state.get(WIZARD_STEP_KEY) or ''),
        details={'source': source, 'ready_key': RULES_CENTER_READY_KEY, 'ready': True},
    )
    return normalized


def rules_center_ready() -> bool:
    return bool(st.session_state.get(RULES_CENTER_READY_KEY, False))


__all__ = [
    'RULES_CENTER_ADVANCED_KEY',
    'RULES_CENTER_AUTOSAVE_SIGNATURE_KEY',
    'RULES_CENTER_READY_KEY',
    'auto_save_rules_if_changed',
    'clear_mapping_rule_cache',
    'mark_rules_ready',
    'rules_center_ready',
    'rules_signature',
]
