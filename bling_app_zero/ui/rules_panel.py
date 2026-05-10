from __future__ import annotations

import streamlit as st

from bling_app_zero.core.user_rules import (
    add_custom_rule,
    get_user_rules,
    remove_custom_rule,
    reset_user_rules,
    set_user_rules,
    update_custom_rule,
)

EDIT_ICON = '✏️'
DELETE_ICON = '🗑️'


def _bool_label(value: bool) -> str:
    return 'Sim' if value else 'Não'


def _rule_key(rule: dict, index: int) -> str:
    target = str(rule.get('target_column', '')).strip().lower()
    value = str(rule.get('fill_value', '')).strip().lower()
    safe = ''.join(ch if ch.isalnum() else '_' for ch in f'{target}_{value}')[:80]
    return safe or str(index)


def _render_rule_row(rule: dict, index: int) -> None:
    target = str(rule.get('target_column', '')).strip()
    value = str(rule.get('fill_value', '')).strip()
    rule_suffix = _rule_key(rule, index)
    edit_key = f'edit_rule_{rule_suffix}'
    edit_mode = bool(st.session_state.get(edit_key, False))

    with st.container(border=True):
        if edit_mode:
            new_target = st.text_input('Coluna', value=target, key=f'edit_target_{rule_suffix}')
            new_value = st.text_input('Valor', value=value, key=f'edit_value_{rule_suffix}')
            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.button('Salvar', use_container_width=True, key=f'save_edit_{rule_suffix}'):
                    update_custom_rule(index, new_target, new_value, False)
                    st.session_state[edit_key] = False
                    st.success('Regra atualizada.')
                    st.rerun()
            with col_cancel:
                if st.button('Cancelar', use_container_width=True, key=f'cancel_edit_{rule_suffix}'):
                    st.session_state[edit_key] = False
                    st.rerun()
            return

        col_info, col_edit, col_delete = st.columns([0.74, 0.13, 0.13])
        with col_info:
            st.markdown(f'**{target}**')
            st.caption(f'Valor: {value if value else "(vazio)"}')
        with col_edit:
            if st.button(EDIT_ICON, key=f'edit_button_{rule_suffix}', help='Editar regra'):
                st.session_state[edit_key] = True
                st.rerun()
        with col_delete:
            if st.button(DELETE_ICON, key=f'delete_rule_{index}_{rule_suffix}', help='Excluir regra'):
                remove_custom_rule(index)
                st.success('Regra excluída.')
                st.rerun()


def _render_rules_tab() -> None:
    rules = get_user_rules()
    custom_rules = list(rules.get('custom_rules', []))

    st.markdown(f'##### Regras salvas ({len(custom_rules)})')
    st.caption('Cada regra preenche uma coluna do CSV final para todos os produtos.')

    if custom_rules:
        for index, rule in enumerate(custom_rules):
            _render_rule_row(rule, index)
    else:
        st.info('Nenhuma regra criada ainda.')

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


def _render_resources_tab() -> None:
    updated = dict(get_user_rules())

    st.markdown('##### Recursos automáticos')
    st.caption('Recursos são motores internos. O usuário só liga ou desliga.')

    updated['clean_invalid_gtin'] = st.toggle(
        'Limpar GTIN inválido',
        value=bool(updated.get('clean_invalid_gtin', True)),
        key='resource_clean_invalid_gtin',
    )
    updated['normalize_image_separator'] = st.toggle(
        'Separar imagens por |',
        value=bool(updated.get('normalize_image_separator', True)),
        key='resource_normalize_images',
    )
    updated['auto_product_code'] = st.toggle(
        f'Gerar código automático: {_bool_label(bool(updated.get("auto_product_code", True)))}',
        value=bool(updated.get('auto_product_code', True)),
        key='rule_auto_product_code',
    )
    updated['unique_product_code'] = st.toggle(
        f'Evitar código duplicado: {_bool_label(bool(updated.get("unique_product_code", True)))}',
        value=bool(updated.get('unique_product_code', True)),
        key='rule_unique_product_code',
    )

    updated['invalid_gtin_mode'] = 'limpar'
    updated['image_separator'] = '|'
    updated['custom_rules'] = get_user_rules().get('custom_rules', [])

    col_save, col_reset = st.columns(2)
    with col_save:
        if st.button('Salvar', use_container_width=True, key='save_user_resources'):
            set_user_rules(updated)
            st.success('Recursos atualizados.')
            st.rerun()
    with col_reset:
        if st.button('Restaurar', use_container_width=True, key='reset_user_resources'):
            reset_user_rules()
            st.success('Padrão restaurado.')
            st.rerun()


def render_rules_panel() -> None:
    with st.sidebar:
        with st.expander('Regras e recursos do CSV final', expanded=False):
            tab_rules, tab_resources = st.tabs(['Regras', 'Recursos'])
            with tab_rules:
                _render_rules_tab()
            with tab_resources:
                _render_resources_tab()
