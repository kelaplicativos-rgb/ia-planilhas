from __future__ import annotations

from typing import Any

import streamlit as st

from bling_app_zero.core.user_rules import (
    add_custom_rule,
    get_user_rules,
    remove_custom_rule_by_id,
    set_custom_rule_enabled,
    update_custom_rule_by_id,
)
from bling_app_zero.ui.rules_ai_resources_tab import render_ai_resources_tab
from bling_app_zero.ui.rules_resources_tab import render_resources_tab

NOTICE_KEY = 'rules_panel_notice'
NEW_RULE_TARGET_KEY = 'new_rule_target'
NEW_RULE_VALUE_KEY = 'new_rule_value'
NEW_RULE_CLEAR_PENDING_KEY = 'new_rule_clear_pending'
EDITING_RULE_ID_KEY = 'rules_panel_editing_rule_id'


def _notice(text: str) -> None:
    st.session_state[NOTICE_KEY] = text


def _show_notice() -> None:
    text = st.session_state.pop(NOTICE_KEY, '')
    if text:
        st.caption(f'✅ {text}')


def _prepare_new_rule_fields() -> None:
    """Limpa campos antes dos widgets serem instanciados.

    Streamlit não permite alterar st.session_state de uma key usada por widget
    depois que o widget já foi criado na mesma execução. Por isso a limpeza fica
    pendente e é aplicada no começo do próximo render.
    """
    if not bool(st.session_state.pop(NEW_RULE_CLEAR_PENDING_KEY, False)):
        return
    st.session_state[NEW_RULE_TARGET_KEY] = ''
    st.session_state[NEW_RULE_VALUE_KEY] = ''


def _safe_rule_id(rule: dict[str, Any], index: int) -> str:
    return str(rule.get('id') or f'rule_{index}')


def _rule_label(rule: dict[str, Any]) -> str:
    column = str(rule.get('target_column') or rule.get('condition') or 'Coluna').strip()
    value = str(rule.get('fill_value') or '').strip()
    if value:
        return f'{column} vazio → {value}'
    return f'{column} vazio → vazio'


def _editable_rules() -> list[dict[str, Any]]:
    rules = get_user_rules()
    custom_rules = rules.get('custom_rules', [])
    if not isinstance(custom_rules, list):
        return []
    return [dict(rule) for rule in custom_rules if bool(rule.get('enabled', False))]


def _enable_rule_by_target(target_column: str) -> None:
    rules = get_user_rules()
    for rule in rules.get('custom_rules', []):
        if str(rule.get('target_column', '')).strip().lower() == target_column.strip().lower():
            set_custom_rule_enabled(str(rule.get('id')), True)
            return


def _add_supplier_default_rule() -> None:
    add_custom_rule('Fornecedor', 'Fornecedor', 'Não definido', True)
    _enable_rule_by_target('Fornecedor')
    _notice('Regra de fornecedor padrão adicionada. Ela só preenche quando o campo estiver vazio.')
    st.rerun()


def _add_new_rule_from_fields(target: object, value: object) -> None:
    target_text = str(target or '').strip()
    value_text = str(value or '').strip()
    if not target_text:
        st.warning('Informe a coluna da nova regra.')
        return

    add_custom_rule(target_text, target_text, value_text, True)
    _enable_rule_by_target(target_text)
    st.session_state[NEW_RULE_CLEAR_PENDING_KEY] = True
    _notice('Nova regra adicionada. Ela só preenche quando a coluna estiver vazia.')
    st.rerun()


def _start_edit_rule(rule_id: str) -> None:
    st.session_state[EDITING_RULE_ID_KEY] = rule_id
    st.rerun()


def _cancel_edit_rule() -> None:
    st.session_state.pop(EDITING_RULE_ID_KEY, None)
    st.rerun()


def _delete_rule(rule_id: str) -> None:
    remove_custom_rule_by_id(rule_id)
    st.session_state.pop(EDITING_RULE_ID_KEY, None)
    _notice('Regra excluída.')
    st.rerun()


def _save_rule_edit(rule_id: str, column: object, value: object) -> None:
    column_text = str(column or '').strip()
    value_text = str(value or '').strip()
    if not column_text:
        st.warning('Informe a coluna da regra.')
        return
    update_custom_rule_by_id(rule_id, column_text, value_text, True)
    set_custom_rule_enabled(rule_id, True)
    st.session_state.pop(EDITING_RULE_ID_KEY, None)
    _notice('Regra atualizada.')
    st.rerun()


def _render_rule_item(rule: dict[str, Any], index: int) -> None:
    rule_id = _safe_rule_id(rule, index)
    editing_id = str(st.session_state.get(EDITING_RULE_ID_KEY) or '')
    is_editing = editing_id == rule_id

    st.divider()
    if is_editing:
        column = st.text_input(
            'Coluna da regra',
            value=str(rule.get('target_column') or rule.get('condition') or ''),
            key=f'rule_edit_column_{rule_id}',
        )
        value = st.text_input(
            'Valor predefinido',
            value=str(rule.get('fill_value') or ''),
            key=f'rule_edit_value_{rule_id}',
        )
        col_save, col_cancel = st.columns(2)
        with col_save:
            if st.button('Salvar', use_container_width=True, key=f'rule_save_{rule_id}'):
                _save_rule_edit(rule_id, column, value)
        with col_cancel:
            if st.button('Cancelar', use_container_width=True, key=f'rule_cancel_{rule_id}'):
                _cancel_edit_rule()
        return

    col_text, col_edit, col_delete = st.columns([6, 1, 1])
    with col_text:
        st.caption(_rule_label(rule))
    with col_edit:
        if st.button('✏️', key=f'rule_edit_{rule_id}', help='Editar regra'):
            _start_edit_rule(rule_id)
    with col_delete:
        if st.button('🗑️', key=f'rule_delete_{rule_id}', help='Excluir regra'):
            _delete_rule(rule_id)


def _render_rules_list() -> None:
    rules = _editable_rules()
    if not rules:
        st.caption('Nenhuma regra manual ativa ainda.')
        return
    st.markdown('##### Regras existentes')
    for index, rule in enumerate(rules):
        _render_rule_item(rule, index)


def _render_new_rule() -> None:
    _prepare_new_rule_fields()

    st.markdown('##### Nova regra')
    st.caption('Regras manuais não usam IA e devem completar lacunas sem sobrescrever o mapeamento.')

    if st.button('Fornecedor vazio → Não definido', use_container_width=True, key='add_supplier_default_rule'):
        _add_supplier_default_rule()

    target = st.text_input(
        'Coluna',
        key=NEW_RULE_TARGET_KEY,
        placeholder='Ex: Fornecedor',
    )
    value = st.text_input(
        'Valor',
        key=NEW_RULE_VALUE_KEY,
        placeholder='Ex: Não definido',
    )

    if st.button('Adicionar regra', use_container_width=True, key='add_rule_clean'):
        _add_new_rule_from_fields(target, value)


def render_rules_panel() -> None:
    """Renderiza recursos, IA e regras manuais na sidebar."""
    with st.sidebar:
        with st.expander('Recursos do CSV final', expanded=False):
            render_resources_tab()

        with st.expander('Recursos com IA', expanded=False):
            render_ai_resources_tab()

        with st.expander('Regras manuais', expanded=False):
            _show_notice()
            _render_rules_list()
            _render_new_rule()
