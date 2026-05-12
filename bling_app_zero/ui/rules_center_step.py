from __future__ import annotations

import streamlit as st

from bling_app_zero.core.user_rules import get_user_rules, reset_user_rules
from bling_app_zero.ui.home_wizard_constants import STEP_ENTRADA, STEP_REGRAS, WIZARD_STEP_KEY
from bling_app_zero.ui.rules_center_sections import render_default_rules, render_protection_rules
from bling_app_zero.ui.rules_center_state import (
    RULES_CENTER_ADVANCED_KEY,
    RULES_CENTER_AUTOSAVE_SIGNATURE_KEY,
    RULES_CENTER_READY_KEY,
    auto_save_rules_if_changed,
    clear_mapping_rule_cache,
    mark_rules_ready,
    rules_center_ready,
    rules_signature,
)


def _confirm_and_continue(rules: dict) -> None:
    mark_rules_ready(rules, source='confirm_and_continue')
    current_step = str(st.session_state.get(WIZARD_STEP_KEY) or '').strip().lower()

    if current_step == STEP_REGRAS:
        st.session_state[WIZARD_STEP_KEY] = STEP_ENTRADA
        st.session_state[RULES_CENTER_ADVANCED_KEY] = True
        st.success('Central de regras confirmada. Avançando para Entrada dos dados...')
    else:
        st.success('Central de regras confirmada.')

    st.rerun()


def render_rules_center_step() -> None:
    st.markdown('### Regras e Padrões')
    st.caption('Central visível do fluxo. Regras importantes não ficam escondidas em caixas recolhidas.')
    st.info('Valores definidos aqui funcionam como padrão de segurança: só serão aplicados quando a coluna existir e não houver valor real vindo da planilha, do site, do XML/PDF ou do mapeamento manual. Se houver valor real, ele tem prioridade.')

    original_rules = get_user_rules()
    previous_signature = rules_signature(original_rules)
    st.session_state.setdefault(RULES_CENTER_AUTOSAVE_SIGNATURE_KEY, previous_signature)

    rules = render_protection_rules(original_rules)
    st.divider()
    rules = render_default_rules(rules)
    auto_save_rules_if_changed(rules, previous_signature)

    col_save, col_reset = st.columns(2)
    with col_save:
        if st.button('Salvar regras desta sessão', use_container_width=True, key='rules_center_save'):
            mark_rules_ready(rules, source='save_button')
            st.success('Regras e padrões salvos para esta sessão.')
    with col_reset:
        if st.button('Restaurar padrões', use_container_width=True, key='rules_center_reset'):
            normalized = reset_user_rules()
            st.session_state[RULES_CENTER_AUTOSAVE_SIGNATURE_KEY] = rules_signature(normalized)
            st.session_state[RULES_CENTER_READY_KEY] = True
            clear_mapping_rule_cache()
            st.success('Padrões restaurados.')
            st.rerun()

    if st.button('Confirmar e continuar', use_container_width=True, key='rules_center_confirm'):
        _confirm_and_continue(rules)


__all__ = [
    'RULES_CENTER_ADVANCED_KEY',
    'RULES_CENTER_READY_KEY',
    'render_rules_center_step',
    'rules_center_ready',
]
