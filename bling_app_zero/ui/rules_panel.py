from __future__ import annotations

import streamlit as st

from bling_app_zero.core.user_rules import add_custom_rule
from bling_app_zero.ui.rules_ai_resources_tab import render_ai_resources_tab
from bling_app_zero.ui.rules_resources_tab import render_resources_tab

NOTICE_KEY = 'rules_panel_notice'


def _notice(text: str) -> None:
    st.session_state[NOTICE_KEY] = text


def _show_notice() -> None:
    text = st.session_state.pop(NOTICE_KEY, '')
    if text:
        st.caption(f'✅ {text}')


def _add_supplier_default_rule() -> None:
    add_custom_rule('Fornecedor', 'Fornecedor', 'Não definido', True)
    _notice('Regra de fornecedor padrão adicionada. Ela só preenche quando o campo estiver vazio.')
    st.rerun()


def _render_new_rule() -> None:
    st.markdown('##### Nova regra')
    st.caption('Regras manuais não usam IA e devem completar lacunas sem sobrescrever o mapeamento.')

    if st.button('Fornecedor vazio → Não definido', use_container_width=True, key='add_supplier_default_rule'):
        _add_supplier_default_rule()

    target = st.text_input(
        'Coluna',
        key='new_rule_target',
        placeholder='Ex: Fornecedor',
    )
    value = st.text_input(
        'Valor',
        key='new_rule_value',
        placeholder='Ex: Não definido',
    )

    if st.button('Adicionar regra', use_container_width=True, key='add_rule_clean'):
        target_text = str(target or '').strip()
        value_text = str(value or '').strip()
        if not target_text:
            st.warning('Informe a coluna da nova regra.')
            return

        add_custom_rule(target_text, target_text, value_text, True)
        st.session_state['new_rule_target'] = ''
        st.session_state['new_rule_value'] = ''
        _notice('Nova regra adicionada. Ela só preenche quando a coluna estiver vazia.')
        st.rerun()


def render_rules_panel() -> None:
    """Renderiza recursos, IA e regras manuais na sidebar."""
    with st.sidebar:
        with st.expander('Recursos do CSV final', expanded=False):
            render_resources_tab()

        with st.expander('Recursos com IA', expanded=False):
            render_ai_resources_tab()

        with st.expander('Regras manuais', expanded=False):
            _show_notice()
            _render_new_rule()
