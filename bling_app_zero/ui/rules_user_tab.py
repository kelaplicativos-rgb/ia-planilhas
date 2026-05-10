from __future__ import annotations

import streamlit as st

from bling_app_zero.core.user_rules import (
    add_custom_rule,
    get_user_rules,
    remove_custom_rule_by_id,
    set_custom_rule_enabled,
)

NOTICE_KEY = 'rules_tab_notice'


def _notice(message: str) -> None:
    st.session_state[NOTICE_KEY] = message


def _render_notice() -> None:
    message = st.session_state.pop(NOTICE_KEY, '')
    if message:
        st.caption(f'✅ {message}')


def _bool_label(value: bool) -> str:
    return 'Sim' if value else 'Não'


def _rule_id(rule: dict, index: int) -> str:
    value = str(rule.get('id') or '').strip()
    if value:
        return value
    target = str(rule.get('target_column', '')).strip().lower()
    safe = ''.join(ch if ch.isalnum() else '_' for ch in target).strip('_')
    return f'rule_{index}_{safe or "item"}'


def _is_system_rule(rule: dict) -> bool:
    return str(rule.get('source') or '').strip().lower() == 'system'


def _rule_label(rule: dict) -> str:
    target = str(rule.get('target_column') or '').strip() or 'Coluna sem nome'
    value = str(rule.get('fill_value') or '').strip()
    suffix = value if value else '(vazio)'
    return f'{target}: {suffix}'


def _render_rule_toggle(rule: dict, index: int) -> None:
    rule_id = _rule_id(rule, index)
    enabled = bool(rule.get('enabled', True))
    label = f'{_rule_label(rule)}: {_bool_label(enabled)}'

    new_enabled = st.toggle(
        label,
        value=enabled,
        key=f'rule_enabled_compact_{rule_id}',
    )
    if new_enabled != enabled:
        set_custom_rule_enabled(rule_id, new_enabled)
        _notice('Regra atualizada.')
        st.rerun()


def _render_system_rules(system_rules: list[dict]) -> None:
    st.markdown('##### Padrões')

    if not system_rules:
        st.caption('Nenhum padrão carregado.')
        return

    for index, rule in enumerate(system_rules):
        _render_rule_toggle(rule, index)


def _render_custom_rules(user_rules: list[dict], start_index: int) -> None:
    st.markdown('##### Personalizadas')

    if not user_rules:
        st.caption('Nenhuma regra personalizada.')
        return

    for offset, rule in enumerate(user_rules):
        index = start_index + offset
        rule_id = _rule_id(rule, index)
        col_toggle, col_delete = st.columns([0.82, 0.18])
        with col_toggle:
            _render_rule_toggle(rule, index)
        with col_delete:
            st.write('')
            if st.button('🗑️', key=f'delete_rule_compact_{rule_id}', help='Excluir regra'):
                remove_custom_rule_by_id(rule_id)
                _notice('Regra excluída.')
                st.rerun()


def _render_new_rule_form() -> None:
    with st.expander('Adicionar regra', expanded=False):
        target_column = st.text_input(
            'Coluna',
            key='custom_rule_target_column',
            placeholder='Ex: Itens por caixa',
        )
        fill_value = st.text_input(
            'Valor',
            key='custom_rule_fill_value',
            placeholder='Ex: 1',
        )

        if st.button('Adicionar', use_container_width=True, key='add_custom_rule_button'):
            column_name = target_column.strip()
            if not column_name:
                st.warning('Informe a coluna.')
                return
            add_custom_rule(column_name, column_name, fill_value, False)
            _notice('Regra adicionada.')
            st.rerun()


def render_user_rules_tab() -> None:
    rules = get_user_rules()
    custom_rules = list(rules.get('custom_rules', []))
    system_rules = [rule for rule in custom_rules if _is_system_rule(rule)]
    user_rules = [rule for rule in custom_rules if not _is_system_rule(rule)]

    st.markdown('##### Regras')
    st.caption('Liga ou desliga preenchimentos automáticos do CSV final.')
    _render_notice()

    _render_system_rules(system_rules)
    st.divider()
    _render_custom_rules(user_rules, len(system_rules))
    st.divider()
    _render_new_rule_form()
