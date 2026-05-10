from __future__ import annotations

import streamlit as st

from bling_app_zero.core.user_rules import add_custom_rule, get_user_rules, remove_custom_rule, update_custom_rule

EDIT_ICON = '✏️'
DELETE_ICON = '🗑️'
SYSTEM_BADGE = '🧩 Padrão'
USER_BADGE = '👤 Usuário'
NOTICE_KEY = 'rules_tab_notice'
CRITICAL_SYSTEM_COLUMNS = {'unidade', 'unidade de medida', 'altura', 'largura', 'profundidade', 'comprimento'}


def _notice(message: str) -> None:
    st.session_state[NOTICE_KEY] = message


def _render_notice() -> None:
    message = st.session_state.pop(NOTICE_KEY, '')
    if message:
        st.caption(f'✅ {message}')


def _rule_key(rule: dict, index: int) -> str:
    target = str(rule.get('target_column', '')).strip().lower()
    value = str(rule.get('fill_value', '')).strip().lower()
    safe = ''.join(ch if ch.isalnum() else '_' for ch in f'{target}_{value}')[:80]
    return safe or str(index)


def _rule_badge(rule: dict) -> str:
    source = str(rule.get('source') or 'user').strip().lower()
    return SYSTEM_BADGE if source == 'system' else USER_BADGE


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


def _render_edit_mode(rule: dict, index: int, suffix: str, edit_key: str, target: str, value: str) -> None:
    with st.container(border=True):
        st.caption(_rule_badge(rule))
        col_target, col_value = st.columns([0.55, 0.45])
        new_target = col_target.text_input('Coluna', value=target, key=f'edit_target_{suffix}')
        new_value = col_value.text_input('Valor', value=value, key=f'edit_value_{suffix}')
        col_save, col_cancel = st.columns(2)

        if col_save.button('Salvar', use_container_width=True, key=f'save_edit_{suffix}'):
            error = _validate_rule_edit(rule, new_target, new_value)
            if error:
                st.warning(error)
                return
            update_custom_rule(index, new_target, new_value, False)
            st.session_state[edit_key] = False
            _notice('Regra atualizada.')
            st.rerun()

        if col_cancel.button('Cancelar', use_container_width=True, key=f'cancel_edit_{suffix}'):
            st.session_state[edit_key] = False
            st.rerun()


def _render_rule_row(rule: dict, index: int) -> None:
    target = str(rule.get('target_column', '')).strip()
    value = str(rule.get('fill_value', '')).strip()
    suffix = _rule_key(rule, index)
    edit_key = f'edit_rule_{suffix}'
    is_system_rule = _is_system_rule(rule)

    if st.session_state.get(edit_key, False):
        _render_edit_mode(rule, index, suffix, edit_key, target, value)
        return

    col_name, col_value, col_badge, col_edit, col_delete = st.columns([0.33, 0.29, 0.20, 0.09, 0.09])
    col_name.caption('Coluna')
    col_name.markdown(f'**{target}**')
    col_value.caption('Valor')
    col_value.markdown(value if value else '—')
    col_badge.caption('Tipo')
    col_badge.caption(_rule_badge(rule))

    if col_edit.button(EDIT_ICON, key=f'edit_button_{suffix}', help='Editar regra'):
        st.session_state[edit_key] = True
        st.rerun()

    if is_system_rule:
        col_delete.caption('🔒')
    elif col_delete.button(DELETE_ICON, key=f'delete_rule_{index}_{suffix}', help='Excluir regra'):
        remove_custom_rule(index)
        _notice('Regra excluída.')
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
            _notice('Regra adicionada.')
            st.rerun()


def render_user_rules_tab() -> None:
    rules = get_user_rules()
    custom_rules = list(rules.get('custom_rules', []))

    st.markdown(f'##### Regras salvas ({len(custom_rules)})')
    st.caption('Regras escrevem valores em colunas do CSV final.')
    _render_notice()

    if custom_rules:
        for index, rule in enumerate(custom_rules):
            _render_rule_row(rule, index)
    else:
        st.info('Nenhuma regra criada ainda.')

    _render_new_rule_form()
