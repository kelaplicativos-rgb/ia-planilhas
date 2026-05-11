from __future__ import annotations

import streamlit as st

from bling_app_zero.core.user_rules import add_custom_rule
from bling_app_zero.ui.rules_resources_tab import render_resources_tab

NOTICE_KEY = 'rules_panel_notice'


def _notice(text: str) -> None:
    st.session_state[NOTICE_KEY] = text


def _show_notice() -> None:
    text = st.session_state.pop(NOTICE_KEY, '')
    if text:
        st.caption(f'✅ {text}')


def _render_new_rule() -> None:
    st.markdown('##### Nova regra')
    st.caption('Crie apenas regras manuais que você realmente quer aplicar no CSV final.')

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

        add_custom_rule(target_text, target_text, value_text, False)
        st.session_state['new_rule_target'] = ''
        st.session_state['new_rule_value'] = ''
        _notice('Nova regra adicionada.')
        st.rerun()


def render_rules_panel() -> None:
    """Renderiza somente Recursos e Nova regra na sidebar.

    BLINGFIX: removido o bloco de regras/padrões automáticos da interface para
    evitar poluição visual. As regras do sistema continuam existindo no motor,
    mas não aparecem mais como cards editáveis na lateral.
    """
    with st.sidebar:
        with st.expander('Recursos do CSV final', expanded=False):
            st.markdown('##### Recursos')
            render_resources_tab()
            st.divider()
            _show_notice()
            _render_new_rule()
