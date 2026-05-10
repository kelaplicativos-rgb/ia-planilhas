from __future__ import annotations

import streamlit as st

from bling_app_zero.core.user_rules import (
    add_custom_rule,
    get_user_rules,
    remove_custom_rule,
    reset_user_rules,
    set_user_rules,
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
            st.caption('Nenhuma regra de coluna criada ainda.')
            return

        st.caption('Toda regra salva pode ser excluída a qualquer momento.')

        for index, rule in enumerate(custom_rules):
            target = str(rule.get('target_column', '')).strip()
            value = str(rule.get('fill_value', '')).strip()
            only_when_empty = bool(rule.get('only_when_empty', True))
            rule_suffix = _rule_key(rule, index)

            col_text, col_remove = st.columns([0.72, 0.28])
            with col_text:
                st.caption(f'**{target}** → {value if value else "(vazio)"}')
                if only_when_empty:
                    st.caption('Aplicar somente quando estiver vazio.')
            with col_remove:
                if st.button('Excluir regra', use_container_width=True, key=f'delete_saved_column_rule_{index}_{rule_suffix}'):
                    remove_custom_rule(index)
                    st.success('Regra excluída.')
                    st.rerun()


def _render_new_column_rule_form() -> None:
    st.markdown('##### Criar regra para coluna')
    st.caption('Informe exatamente o cabeçalho da coluna final e o valor que deve entrar antes do download.')

    target_column = st.text_input(
        'Nome da coluna / cabeçalho',
        key='custom_rule_target_column',
        placeholder='Ex: Itens por caixa',
        help='Digite o nome da coluna como aparece no modelo/CSV final.',
    )
    fill_value = st.text_input(
        'Valor predefinido',
        key='custom_rule_fill_value',
        placeholder='Ex: 1',
        help='Esse valor será usado nessa coluna quando ela existir no CSV final.',
    )

    if st.button('Salvar regra de coluna', use_container_width=True, key='add_custom_rule_button'):
        if not target_column.strip():
            st.warning('Informe o nome da coluna/cabeçalho.')
            return
        add_custom_rule(target_column, target_column, fill_value, True)
        st.success('Regra de coluna salva.')
        st.rerun()


def render_rules_panel() -> None:
    """Painel lateral para padrões usados no CSV final."""
    rules = get_user_rules()

    with st.sidebar:
        with st.expander('⚙️ Padrões e regras do CSV final', expanded=False):
            st.caption('Use regras simples para preencher colunas específicas antes do download final.')

            _render_new_column_rule_form()
            _render_saved_column_rules(get_user_rules())

            st.divider()
            st.markdown('##### Padrões básicos')
            st.caption('Ajustes fixos usados somente quando esses campos existirem no CSV final e vierem vazios.')

            updated = dict(get_user_rules())
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
            updated['invalid_gtin_mode'] = 'limpar'
            updated['custom_rules'] = get_user_rules().get('custom_rules', [])

            col_save, col_reset = st.columns(2)
            with col_save:
                if st.button('Salvar padrões', use_container_width=True, key='save_user_rules'):
                    set_user_rules(updated)
                    st.success('Padrões salvos nesta sessão.')
                    st.rerun()
            with col_reset:
                if st.button('Restaurar', use_container_width=True, key='reset_user_rules'):
                    reset_user_rules()
                    st.success('Padrões restaurados.')
                    st.rerun()
