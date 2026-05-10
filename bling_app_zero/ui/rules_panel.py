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


def _bool_label(value: bool) -> str:
    return 'Sim' if value else 'Não'


def _rule_key(rule: dict, index: int) -> str:
    target = str(rule.get('target_column', '')).strip().lower()
    value = str(rule.get('fill_value', '')).strip().lower()
    safe = ''.join(ch if ch.isalnum() else '_' for ch in f'{target}_{value}')[:80]
    return safe or str(index)


def _render_saved_column_rules(rules: dict) -> None:
    custom_rules = list(rules.get('custom_rules', []))

    with st.expander(f'📌 Regras para colunas salvas ({len(custom_rules)})', expanded=False):
        if not custom_rules:
            st.caption('Nenhuma regra criada ainda.')
            return

        st.caption('Essas regras entram no CSV final antes do download quando a coluna existir no modelo.')

        for index, rule in enumerate(custom_rules):
            target = str(rule.get('target_column', '')).strip()
            value = str(rule.get('fill_value', '')).strip()
            rule_suffix = _rule_key(rule, index)
            edit_mode = bool(st.session_state.get(f'edit_rule_{rule_suffix}', False))

            with st.container(border=True):
                if edit_mode:
                    new_target = st.text_input('Nome da coluna', value=target, key=f'edit_target_{rule_suffix}')
                    new_value = st.text_input('Valor predefinido', value=value, key=f'edit_value_{rule_suffix}')

                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        if st.button('Salvar edição', use_container_width=True, key=f'save_edit_{rule_suffix}'):
                            update_custom_rule(index, new_target, new_value, False)
                            st.session_state[f'edit_rule_{rule_suffix}'] = False
                            st.success('Regra atualizada.')
                            st.rerun()
                    with col_cancel:
                        if st.button('Cancelar', use_container_width=True, key=f'cancel_edit_{rule_suffix}'):
                            st.session_state[f'edit_rule_{rule_suffix}'] = False
                            st.rerun()
                else:
                    st.caption(f'**Coluna:** {target}')
                    st.caption(f'**Valor:** {value if value else "(vazio)"}')

                    col_edit, col_delete = st.columns(2)
                    with col_edit:
                        if st.button('Editar', use_container_width=True, key=f'edit_button_{rule_suffix}'):
                            st.session_state[f'edit_rule_{rule_suffix}'] = True
                            st.rerun()
                    with col_delete:
                        if st.button('Excluir', use_container_width=True, key=f'delete_saved_column_rule_{index}_{rule_suffix}'):
                            remove_custom_rule(index)
                            st.success('Regra excluída.')
                            st.rerun()


def _render_new_column_rule_form() -> None:
    st.markdown('##### Criar regra por coluna')
    st.caption('Digite o cabeçalho exato da coluna final e o valor fixo que deve sair no CSV.')

    target_column = st.text_input(
        'Nome da coluna',
        key='custom_rule_target_column',
        placeholder='Ex: Itens por caixa',
        help='Digite o cabeçalho como ele aparece no modelo/CSV final.',
    )
    fill_value = st.text_input(
        'Valor predefinido',
        key='custom_rule_fill_value',
        placeholder='Ex: 1',
        help='Esse valor será aplicado nessa coluna antes do download final.',
    )

    if st.button('Salvar regra', use_container_width=True, key='add_custom_rule_button'):
        column_name = target_column.strip()
        if not column_name:
            st.warning('Informe o nome da coluna.')
            return
        add_custom_rule(column_name, column_name, fill_value, False)
        st.success('Regra salva.')
        st.rerun()


def _render_rules_tab() -> None:
    _render_new_column_rule_form()
    _render_saved_column_rules(get_user_rules())


def _render_resources_tab() -> None:
    st.markdown('##### Recursos antes do download final')
    st.caption('Recursos são tratamentos automáticos do CSV final. Eles são diferentes das regras por coluna.')

    updated = dict(get_user_rules())

    st.toggle(
        'Limpar GTIN inválido antes do download final',
        value=True,
        disabled=True,
        key='resource_clean_invalid_gtin',
        help='Recurso obrigatório: GTIN fora do padrão é limpo e sai vazio no CSV final.',
    )
    updated['invalid_gtin_mode'] = 'limpar'

    updated['image_separator'] = st.text_input(
        'Separador entre imagens',
        value=str(updated.get('image_separator', '|')),
        key='rule_image_separator',
        help='Para o Bling, mantenha | quando houver várias imagens no mesmo produto.',
    )
    updated['auto_product_code'] = st.toggle(
        f'Gerar código se vier vazio: {_bool_label(bool(updated.get("auto_product_code", True)))}',
        value=bool(updated.get('auto_product_code', True)),
        key='rule_auto_product_code',
    )
    updated['unique_product_code'] = st.toggle(
        f'Evitar código duplicado: {_bool_label(bool(updated.get("unique_product_code", True)))}',
        value=bool(updated.get('unique_product_code', True)),
        key='rule_unique_product_code',
    )

    st.divider()
    st.markdown('##### Padrões básicos')
    st.caption('Usados somente quando esses campos existirem no CSV final e vierem vazios.')

    updated['supplier_default'] = st.text_input(
        'Fornecedor quando vier vazio',
        value=str(updated.get('supplier_default', 'Não definido')),
        key='rule_supplier_default',
    )
    updated['measure_unit_default'] = st.text_input(
        'Unidade quando vier vazia',
        value=str(updated.get('measure_unit_default', 'Centímetro')),
        key='rule_measure_unit_default',
    )

    col_a, col_b = st.columns(2)
    updated['height_default'] = col_a.text_input('Altura', value=str(updated.get('height_default', '2')), key='rule_height_default')
    updated['width_default'] = col_b.text_input('Largura', value=str(updated.get('width_default', '11')), key='rule_width_default')
    col_c, col_d = st.columns(2)
    updated['depth_default'] = col_c.text_input('Profundidade', value=str(updated.get('depth_default', '18')), key='rule_depth_default')
    updated['length_default'] = col_d.text_input('Comprimento', value=str(updated.get('length_default', '18')), key='rule_length_default')

    updated['custom_rules'] = get_user_rules().get('custom_rules', [])

    col_save, col_reset = st.columns(2)
    with col_save:
        if st.button('Salvar recursos', use_container_width=True, key='save_user_resources'):
            set_user_rules(updated)
            st.success('Recursos salvos nesta sessão.')
            st.rerun()
    with col_reset:
        if st.button('Restaurar recursos', use_container_width=True, key='reset_user_resources'):
            reset_user_rules()
            st.success('Recursos restaurados.')
            st.rerun()


def render_rules_panel() -> None:
    """Painel lateral para regras por coluna e recursos do CSV final."""
    with st.sidebar:
        with st.expander('⚙️ Regras e recursos do CSV final', expanded=False):
            tab_rules, tab_resources = st.tabs(['Regras', 'Recursos'])
            with tab_rules:
                _render_rules_tab()
            with tab_resources:
                _render_resources_tab()
