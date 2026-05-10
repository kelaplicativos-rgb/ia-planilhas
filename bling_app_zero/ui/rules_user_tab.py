from __future__ import annotations

import streamlit as st

from bling_app_zero.core.user_rules import add_custom_rule, get_user_rules, remove_custom_rule, update_custom_rule

EDIT_ICON = '✏️'
DELETE_ICON = '🗑️'


def _rule_key(rule: dict, index: int) -> str:
    target = str(rule.get('target_column', '')).strip().lower()
    value = str(rule.get('fill_value', '')).strip().lower()
    safe = ''.join(ch if ch.isalnum() else '_' for ch in f'{target}_{value}')[:80]
    return safe or str(index)


def _render_rule_row(rule: dict, index: int) -> None:
    target = str(rule.get('target_column', '')).strip()
    value = str(rule.get('fill_value', '')).strip()
    suffix = _rule_key(rule, index)
    edit_key = f'edit_rule_{suffix}'

    if st.session_state.get(edit_key, False):
        with st.container(border=True):
            col_target, col_value = st.columns([0.55, 0.45])
            new_target = col_target.text_input('Coluna', value=target, key=f'edit_target_{suffix}')
            new_value = col_value.text_input('Valor', value=value, key=f'edit_value_{suffix}')
            col_save, col_cancel = st.columns(2)
            if col_save.button('Salvar', use_container_width=True, key=f'save_edit_{suffix}'):
                update_custom_rule(index, new_target, new_value, False)
                st.session_state[edit_key] = False
                st.success('Regra atualizada.')
                st.rerun()
            if col_cancel.button('Cancelar', use_container_width=True, key=f'cancel_edit_{suffix}'):
                st.session_state[edit_key] = False
                st.rerun()
        return

    col_name, col_value, col_edit, col_delete = st.columns([0.42, 0.38, 0.10, 0.10])
    col_name.caption('Coluna')
    col_name.markdown(f'**{target}**')
    col_value.caption('Valor')
    col_value.markdown(value if value else '—')

    if col_edit.button(EDIT_ICON, key=f'edit_button_{suffix}', help='Editar regra'):
        st.session_state[edit_key] = True
        st.rerun()
    if col_delete.button(DELETE_ICON, key=f'delete_rule_{index}_{suffix}', help='Excluir regra'):
        remove_custom_rule(index)
        st.success('Regra excluída.')
        st.rerun()


def _render_new_rule_form() -> None:
    with st.expander('Adicionar nova regra', expanded=False):
        target_column = st.text_input('Nome da coluna', key='custom_rule_target_column', placeholder='Ex: Itens por caixa')
        fill_value = st.text_input('Valor predefinido', key='custom_rule_fill_value', placeholder='Ex: 1')
        if st.button('Adicionar regra', use_container_width=True, key='add_custom_rule_button'):
            column_name = target_column.strip()
            if not column_name:
                st.warning('Informe o nome da coluna.')
                return
            add_custom_rule(column_name, column_name, fill_value, False)
            st.success('Regra adicionada.')
            st.rerun()


def render_user_rules_tab() -> None:
    rules = get_user_rules()
    custom_rules = list(rules.get('custom_rules', []))

    st.markdown(f'##### Regras salvas ({len(custom_rules)})')
    st.caption('Preenche colunas do CSV final para todos os produtos.')

    if custom_rules:
        for index, rule in enumerate(custom_rules):
            _render_rule_row(rule, index)
    else:
        st.info('Nenhuma regra criada ainda.')

    _render_new_rule_form()
