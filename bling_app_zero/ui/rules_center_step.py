from __future__ import annotations

import streamlit as st

from bling_app_zero.core.user_rules import get_user_rules, reset_user_rules
from bling_app_zero.ui.rules_center_sections import render_default_rules, render_protection_rules
from bling_app_zero.ui.rules_center_state import (
    RULES_CENTER_AUTOSAVE_SIGNATURE_KEY,
    RULES_CENTER_READY_KEY,
    auto_save_rules_if_changed,
    clear_mapping_rule_cache,
    mark_rules_ready,
    rules_center_ready,
    rules_signature,
)

RESPONSIBLE_FILE = 'bling_app_zero/ui/rules_center_step.py'


def _render_rules_header() -> None:
    st.markdown('### Configurações do arquivo final')
    st.caption('Configure proteções, preenchimentos opcionais e regras. Valores reais e mapeamentos manuais continuam tendo prioridade.')


def render_rules_center_step() -> None:
    original_rules = get_user_rules()
    previous_signature = rules_signature(original_rules)
    st.session_state.setdefault(RULES_CENTER_AUTOSAVE_SIGNATURE_KEY, previous_signature)

    with st.container(border=True):
        _render_rules_header()
        rules = render_protection_rules(original_rules)
        rules = render_default_rules(rules)
        auto_save_rules_if_changed(rules, previous_signature)

        st.divider()
        col_save, col_reset = st.columns(2)
        with col_save:
            if st.button('Salvar configurações', use_container_width=True, key='rules_center_save'):
                mark_rules_ready(rules, source='save_button')
                st.success('Configurações salvas para esta sessão.')
        with col_reset:
            if st.button('Restaurar padrão', use_container_width=True, key='rules_center_reset'):
                normalized = reset_user_rules()
                st.session_state[RULES_CENTER_AUTOSAVE_SIGNATURE_KEY] = rules_signature(normalized)
                st.session_state[RULES_CENTER_READY_KEY] = True
                st.session_state['rules_center_default_rules_enabled'] = True
                clear_mapping_rule_cache()
                st.success('Configurações padrão restauradas.')
                st.rerun()

    st.caption('Revise as configurações e use Continuar para seguir no fluxo.')


__all__ = [
    'RULES_CENTER_READY_KEY',
    'render_rules_center_step',
    'rules_center_ready',
]
