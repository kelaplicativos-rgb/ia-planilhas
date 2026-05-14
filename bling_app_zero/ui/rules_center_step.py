from __future__ import annotations

import streamlit as st

from bling_app_zero.core.user_rules import get_user_rules, reset_user_rules, set_user_rules
from bling_app_zero.ui.rules_center_sections import disable_all_rules, render_default_rules, render_protection_rules
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


def render_rules_center_step() -> None:
    st.markdown('### Regras e Padrões')
    st.caption('Central visível do fluxo. Regras importantes não ficam escondidas em caixas recolhidas nem duplicadas na sidebar.')
    st.info(
        'Valores definidos aqui funcionam como padrão de segurança: só serão aplicados quando a coluna existir e não houver valor real vindo da planilha, do site, do XML/PDF ou do mapeamento manual. Se houver valor real, ele tem prioridade.'
    )

    original_rules = get_user_rules()
    previous_signature = rules_signature(original_rules)
    st.session_state.setdefault(RULES_CENTER_AUTOSAVE_SIGNATURE_KEY, previous_signature)

    col_title, col_off = st.columns([2, 1])
    with col_title:
        st.markdown('#### Controle geral')
        st.caption('Use o botão ao lado para desligar tudo: proteções, padrões opcionais e regras personalizadas.')
    with col_off:
        if st.button('Desligar tudo', use_container_width=True, key='rules_center_disable_all_rules'):
            disabled = disable_all_rules(original_rules)
            normalized = set_user_rules(disabled)
            st.session_state[RULES_CENTER_AUTOSAVE_SIGNATURE_KEY] = rules_signature(normalized)
            st.session_state[RULES_CENTER_READY_KEY] = True
            st.session_state['rules_center_default_rules_enabled'] = False
            clear_mapping_rule_cache()
            st.success('Todas as regras foram desligadas.')
            st.rerun()

    st.divider()
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
            st.session_state['rules_center_default_rules_enabled'] = True
            clear_mapping_rule_cache()
            st.success('Padrões restaurados.')
            st.rerun()

    st.caption('Após revisar ou salvar os padrões, use o botão Continuar abaixo para avançar no fluxo.')


__all__ = [
    'RULES_CENTER_READY_KEY',
    'render_rules_center_step',
    'rules_center_ready',
]
