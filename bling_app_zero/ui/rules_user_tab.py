from __future__ import annotations

import streamlit as st

from bling_app_zero.core.user_rules import (
    add_custom_rule,
    get_user_rules,
    remove_custom_rule_by_id,
    set_custom_rule_enabled,
    update_custom_rule_by_id,
)

EDIT_ICON = '✏️'
DELETE_ICON = '🗑️'
NOTICE_KEY = 'rules_tab_notice'
CRITICAL_SYSTEM_COLUMNS = {'unidade', 'unidade de medida', 'altura', 'largura', 'profundidade', 'comprimento'}


def _notice(message: str) -> None:
    st.session_state[NOTICE_KEY] = message


def _render_notice() -> None:
    message = st.session_state.pop(NOTICE_KEY, '')
    if message:
        st.caption(f'✅ {message}')


def _rule_id(rule: dict, index: int) -> str:
    value = str(rule.get('id') or '').strip()
    if value:
        return value
    target = str(rule.get('target_column', '')).strip().lower()
    return f'rule_{index}_{target}'


def _is_system_rule(rule: dict) -> bool:
    return str(rule.get('source') or '').strip().lower() == 'system'


def _validate_rule_edit(rule: dict, target: str, value: str) -> str:
    target_key = target.strip().lower()
    value_clean = value.strip()

    if not target.strip():
        return 'Informe o nome da coluna.'

    if _is_system_rule(rule) and target_key in CRITICAL_SYSTEM_COLUMNS and not value_clean:
        return 'Essa regra padrão não pode ficar vazia.'

    if target_key in {'altura', 'largura', 'profundidade', 'comprimento'}:
        try:
            number = float(value_clean.replace(',', '.'))
        except Exception:
            return 'Medidas precisam ser numéricas.'
        if number <= 0:
            return 'Medidas precisam ser maiores que zero.'

    if target_key in {'unidade', 'unidade de medida'} and len(value_clean) > 8:
        return 'Unidade deve ser curta, exemplo: UN.'

    return ''


def _render_edit_card(rule: dict, rule_id: str, edit_key: str) -> None:
    target = str(rule.get('target_column', '')).strip()
    value = str(rule.get('fill_value', '')).strip()

    with st.container(border=True):
        st.caption('Editando regra')
        col_target, col_value = st.columns([0.55, 0.45])
        new_target = col_target.text_input('Coluna', value=target, key=f'edit_target_{rule_id}')
        new_value = col_value.text_input('Valor', value=value, key=f'edit_value_{rule_id}')

        col_save, col_cancel = st.columns(2)
        if col_save.button('Salvar', use_container_width=True, key=f'save_edit_{rule_id}'):
            error = _validate_rule_edit(rule, new_target, new_value)
            if error:
                st.warning(error)
                return
            update_custom_rule_by_id(rule_id, new_target, new_value, False)
            st.session_state[edit_key] = False
            _notice('Regra atualizada.')
            st.rerun()

        if col_cancel.button('Cancelar', use_container_width=True, key=f'cancel_edit_{rule_id}'):
            st.session_state[edit_key] = False
            st.rerun()


def _render_rule_card(rule: dict, index: int) -> None:
    target = str(rule.get('target_column', '')).strip()
    value = str(rule.get('fill_value', '')).strip()
    rule_id = _rule_id(rule, index)
    edit_key = f'edit_rule_{rule_id}'
    is_system = _is_system_rule(rule)
    enabled = bool(rule.get('enabled', True))

    if st.session_state.get(edit_key, False):
        _render_edit_card(rule, rule_id, edit_key)
        return

    with st.container(border=True):
        col_main, col_actions = st.columns([0.72, 0.28])
        with col_main:
            badge = '🧩 Padrão do sistema' if is_system else '👤 Personalizada'
            status = 'Ativa' if enabled else 'Inativa'
            st.caption(f'{badge} • {status}')
            st.markdown(f'**{target}**')
            st.caption(f'Preencher com: {value if value else "(vazio)"}')

        with col_actions:
            new_enabled = st.toggle('Ativa', value=enabled, key=f'enabled_{rule_id}')
            if new_enabled != enabled:
                set_custom_rule_enabled(rule_id, new_enabled)
                _notice('Status da regra atualizado.')
                st.rerun()

            col_edit, col_delete = st.columns(2)
            if col_edit.button(EDIT_ICON, key=f'edit_button_{rule_id}', help='Editar regra'):
                st.session_state[edit_key] = True
                st.rerun()

            if is_system:
                col_delete.caption('🔒')
            elif col_delete.button(DELETE_ICON, key=f'delete_rule_{rule_id}', help='Excluir regra'):
                remove_custom_rule_by_id(rule_id)
                _notice('Regra excluída.')
                st.rerun()


def _render_new_rule_form() -> None:
    with st.container(border=True):
        st.markdown('##### Nova regra personalizada')
        st.caption('Crie uma regra para preencher uma coluna específica antes do download final.')
        target_column = st.text_input('Nome da coluna', key='custom_rule_target_column', placeholder='Ex: Itens por caixa')
        fill_value = st.text_input('Valor predefinido', key='custom_rule_fill_value', placeholder='Ex: 1')

        if st.button('Adicionar regra', use_container_width=True, key='add_custom_rule_button'):
            column_name = target_column.strip()
            if not column_name:
                st.warning('Informe o nome da coluna.')
                return
            add_custom_rule(column_name, column_name, fill_value, False)
            _notice('Regra adicionada.')
            st.rerun()


def _render_rules_group(title: str, rules: list[dict], start_index: int, empty_message: str) -> None:
    """Renderiza grupos de regras sem usar st.expander.

    Este painel já fica dentro de um expander em rules_panel.py.
    O Streamlit não permite expander dentro de expander, então aqui usamos
    containers comuns para evitar StreamlitAPIException.
    """
    st.markdown(f'##### {title}')
    with st.container(border=True):
        if rules:
            for offset, rule in enumerate(rules):
                _render_rule_card(rule, start_index + offset)
        else:
            st.caption(empty_message)


def render_user_rules_tab() -> None:
    rules = get_user_rules()
    custom_rules = list(rules.get('custom_rules', []))
    system_rules = [rule for rule in custom_rules if _is_system_rule(rule)]
    user_rules = [rule for rule in custom_rules if not _is_system_rule(rule)]

    st.markdown('##### Regras')
    st.caption('Regras escrevem valores em colunas do CSV final.')
    _render_notice()

    _render_new_rule_form()

    _render_rules_group(
        f'🧩 Padrões do sistema ({len(system_rules)})',
        system_rules,
        0,
        'Nenhuma regra padrão carregada.',
    )

    _render_rules_group(
        f'👤 Regras personalizadas ({len(user_rules)})',
        user_rules,
        len(system_rules),
        'Nenhuma regra personalizada criada ainda.',
    )
