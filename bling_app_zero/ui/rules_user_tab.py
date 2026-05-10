from __future__ import annotations

import html

import streamlit as st

from bling_app_zero.core.user_rules import (
    add_custom_rule,
    get_user_rules,
    remove_custom_rule_by_id,
    reset_user_rules,
    set_custom_rule_enabled,
    update_custom_rule_by_id,
)

NOTICE_KEY = 'rules_tab_notice'
EDIT_RULE_KEY = 'rules_tab_edit_rule_id'


def _notice(message: str) -> None:
    st.session_state[NOTICE_KEY] = message


def _render_notice() -> None:
    message = st.session_state.pop(NOTICE_KEY, '')
    if message:
        st.success(message)


def _rule_id(rule: dict, index: int) -> str:
    value = str(rule.get('id') or '').strip()
    if value:
        return value
    target = str(rule.get('target_column', '')).strip().lower()
    safe = ''.join(ch if ch.isalnum() else '_' for ch in target).strip('_')
    return f'rule_{index}_{safe or "item"}'


def _is_system_rule(rule: dict) -> bool:
    return str(rule.get('source') or '').strip().lower() == 'system'


def _system_display_group(rule: dict) -> str:
    target = str(rule.get('target_column') or '').strip().lower()
    if target in {'fornecedor', 'nome fornecedor', 'nome do fornecedor'}:
        return 'fornecedor'
    if target in {'unidade', 'unidade de medida', 'unidade medida'}:
        return 'unidade'
    return target


def _visible_system_rules(system_rules: list[dict]) -> list[dict]:
    visible: list[dict] = []
    seen: set[str] = set()
    for rule in system_rules:
        group = _system_display_group(rule)
        if group in seen:
            continue
        seen.add(group)
        visible.append(rule)
    return visible


def _rule_label(rule: dict) -> str:
    target = str(rule.get('target_column') or '').strip() or 'Coluna sem nome'
    value = str(rule.get('fill_value') or '').strip()
    suffix = value if value else '(vazio)'
    return f'{target} = {suffix}'


def _status_badge(enabled: bool) -> str:
    return 'Ativo' if enabled else 'Inativo'


def _render_system_rule_header(target: str, enabled: bool) -> None:
    safe_target = html.escape(str(target or 'Coluna sem nome'))
    status = _status_badge(enabled)
    status_class = 'is-active' if enabled else 'is-muted'
    st.markdown(
        f"""
        <div class="bling-rule-pro-head">
            <div>
                <div class="bling-rule-pro-label">Coluna final</div>
                <div class="bling-rule-pro-title">{safe_target}</div>
            </div>
            <div class="bling-rule-pro-badge {status_class}">{status}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_rule_toggle(rule: dict, index: int) -> None:
    rule_id = _rule_id(rule, index)
    enabled = bool(rule.get('enabled', True))
    label = _rule_label(rule)

    new_enabled = st.toggle(
        label,
        value=enabled,
        key=f'rule_enabled_compact_{rule_id}',
        help='Quando ligado, essa regra será aplicada no CSV final.',
    )
    if new_enabled != enabled:
        set_custom_rule_enabled(rule_id, new_enabled)
        _notice('Regra atualizada.')
        st.rerun()


def _render_system_rule_value_editor(rule: dict, index: int) -> None:
    rule_id = _rule_id(rule, index)
    target = str(rule.get('target_column') or '').strip() or 'Coluna sem nome'
    current_value = str(rule.get('fill_value') or '')
    enabled = bool(rule.get('enabled', True))

    st.markdown('<div class="bling-rule-pro-card">', unsafe_allow_html=True)
    _render_system_rule_header(target, enabled)

    new_enabled = st.toggle(
        'Aplicar preenchimento automático',
        value=enabled,
        key=f'system_rule_enabled_{rule_id}',
        help='Quando ligado, esse padrão será aplicado no CSV final.',
    )

    new_value = st.text_input(
        'Valor aplicado na coluna final',
        value=current_value,
        key=f'system_rule_value_{rule_id}',
        help='Edite somente o valor. O cabeçalho da coluna final fica travado.',
        placeholder='Ex: Não definido',
    )
    st.markdown('</div>', unsafe_allow_html=True)

    if new_enabled != enabled:
        set_custom_rule_enabled(rule_id, new_enabled)
        _notice('Padrão atualizado.')
        st.rerun()

    if str(new_value) != current_value:
        update_custom_rule_by_id(rule_id, target, str(new_value), bool(rule.get('only_when_empty', False)))
        _notice('Valor padrão atualizado.')
        st.rerun()


def _start_edit_rule(rule_id: str, rule: dict) -> None:
    st.session_state[EDIT_RULE_KEY] = rule_id
    st.session_state[f'edit_rule_target_{rule_id}'] = str(rule.get('target_column') or '')
    st.session_state[f'edit_rule_value_{rule_id}'] = str(rule.get('fill_value') or '')
    st.rerun()


def _cancel_edit_rule(rule_id: str) -> None:
    st.session_state.pop(EDIT_RULE_KEY, None)
    st.session_state.pop(f'edit_rule_target_{rule_id}', None)
    st.session_state.pop(f'edit_rule_value_{rule_id}', None)
    st.rerun()


def _render_edit_form(rule: dict, rule_id: str) -> None:
    st.caption('Editar regra personalizada')
    new_target = st.text_input(
        'Coluna final',
        key=f'edit_rule_target_{rule_id}',
        placeholder='Ex: Tipo',
        help='Informe somente o nome da coluna do modelo final.',
    )
    new_value = st.text_input(
        'Valor aplicado',
        key=f'edit_rule_value_{rule_id}',
        placeholder='Ex: Produto',
        help='Informe o valor que será aplicado nessa coluna.',
    )

    col_save, col_cancel = st.columns(2)
    with col_save:
        if st.button('Salvar', use_container_width=True, key=f'save_rule_{rule_id}'):
            column_name = str(new_target or '').strip()
            if not column_name:
                st.warning('Informe a coluna.')
                return
            update_custom_rule_by_id(rule_id, column_name, str(new_value or ''), bool(rule.get('only_when_empty', False)))
            st.session_state.pop(EDIT_RULE_KEY, None)
            st.session_state.pop(f'edit_rule_target_{rule_id}', None)
            st.session_state.pop(f'edit_rule_value_{rule_id}', None)
            _notice('Regra editada.')
            st.rerun()
    with col_cancel:
        if st.button('Cancelar', use_container_width=True, key=f'cancel_rule_{rule_id}'):
            _cancel_edit_rule(rule_id)


def _render_system_rules(system_rules: list[dict]) -> None:
    st.markdown('##### Padrões automáticos')
    st.caption('Valores fixos aplicados ao CSV final. A coluna fica travada; você altera somente o valor.')

    visible_rules = _visible_system_rules(system_rules)
    if not visible_rules:
        st.caption('Nenhum padrão carregado.')
        return

    for index, rule in enumerate(visible_rules):
        _render_system_rule_value_editor(rule, index)


def _render_custom_rules(user_rules: list[dict], start_index: int) -> None:
    st.markdown('##### Personalizadas')

    if not user_rules:
        st.caption('Nenhuma regra personalizada.')
        return

    editing_rule_id = str(st.session_state.get(EDIT_RULE_KEY) or '')

    for offset, rule in enumerate(user_rules):
        index = start_index + offset
        rule_id = _rule_id(rule, index)

        if editing_rule_id == rule_id:
            with st.container(border=True):
                _render_edit_form(rule, rule_id)
            continue

        with st.container(border=True):
            col_toggle, col_edit, col_delete = st.columns([0.62, 0.19, 0.19])
            with col_toggle:
                _render_rule_toggle(rule, index)
            with col_edit:
                st.write('')
                if st.button('Editar', key=f'edit_rule_compact_{rule_id}', help='Editar regra'):
                    _start_edit_rule(rule_id, rule)
            with col_delete:
                st.write('')
                if st.button('Excluir', key=f'delete_rule_compact_{rule_id}', help='Excluir regra'):
                    remove_custom_rule_by_id(rule_id)
                    st.session_state.pop(EDIT_RULE_KEY, None)
                    _notice('Regra excluída.')
                    st.rerun()


def _render_new_rule_form() -> None:
    st.markdown('##### Nova regra')
    target_column = st.text_input(
        'Coluna final',
        key='custom_rule_target_column',
        placeholder='Ex: Tipo',
        help='Informe somente o nome da coluna do modelo final.',
    )
    fill_value = st.text_input(
        'Valor aplicado',
        key='custom_rule_fill_value',
        placeholder='Ex: Produto',
        help='Informe o valor que será aplicado nessa coluna.',
    )

    if st.button('Adicionar regra', use_container_width=True, key='add_custom_rule_button'):
        column_name = target_column.strip()
        if not column_name:
            st.warning('Informe a coluna.')
            return
        add_custom_rule(column_name, column_name, fill_value, False)
        st.session_state['custom_rule_target_column'] = ''
        st.session_state['custom_rule_fill_value'] = ''
        _notice('Regra adicionada.')
        st.rerun()


def _render_footer_actions() -> None:
    if st.button('Restaurar padrão', use_container_width=True, key='reset_user_rules_footer'):
        reset_user_rules()
        st.session_state.pop(EDIT_RULE_KEY, None)
        _notice('Regras restauradas para o padrão.')
        st.rerun()


def render_user_rules_tab() -> None:
    rules = get_user_rules()
    custom_rules = list(rules.get('custom_rules', []))
    system_rules = [rule for rule in custom_rules if _is_system_rule(rule)]
    user_rules = [rule for rule in custom_rules if not _is_system_rule(rule)]

    st.markdown('##### Regras')
    st.caption('Controle os preenchimentos automáticos que entram no CSV final.')
    _render_notice()

    _render_system_rules(system_rules)
    st.divider()
    _render_custom_rules(user_rules, len(_visible_system_rules(system_rules)))
    st.divider()
    _render_new_rule_form()
    st.divider()
    _render_footer_actions()
