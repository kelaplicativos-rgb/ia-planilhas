from __future__ import annotations

import streamlit as st

from bling_app_zero.core.user_rules import RULE_OPTIONS, default_rules, get_user_rules, reset_user_rules, set_user_rules


def _bool_label(value: bool) -> str:
    return 'Sim' if value else 'Não'


def render_rules_panel() -> None:
    """Painel lateral para padrões usados no CSV final."""
    rules = get_user_rules()

    with st.sidebar:
        with st.expander('⚙️ Padrões do CSV final', expanded=False):
            st.caption('Ajuste valores que entram automaticamente quando algum campo vier vazio.')

            updated = dict(rules)
            updated['supplier_default'] = st.text_input(
                'Fornecedor quando vier vazio',
                value=str(rules.get('supplier_default', 'Não definido')),
                key='rule_supplier_default',
                help='Exemplo: Não definido. Usado quando o fornecedor não vier na origem.',
            )
            updated['measure_unit_default'] = st.text_input(
                'Unidade quando vier vazia',
                value=str(rules.get('measure_unit_default', 'Centímetro')),
                key='rule_measure_unit_default',
                help='Usado somente se existir coluna de unidade no modelo do Bling.',
            )

            st.markdown('##### Medidas padrão')
            st.caption('Usadas apenas quando essas colunas existirem e estiverem vazias.')
            col_a, col_b = st.columns(2)
            updated['height_default'] = col_a.text_input('Altura', value=str(rules.get('height_default', '2')), key='rule_height_default')
            updated['width_default'] = col_b.text_input('Largura', value=str(rules.get('width_default', '11')), key='rule_width_default')
            col_c, col_d = st.columns(2)
            updated['depth_default'] = col_c.text_input('Profundidade', value=str(rules.get('depth_default', '18')), key='rule_depth_default')
            updated['length_default'] = col_d.text_input('Comprimento', value=str(rules.get('length_default', '18')), key='rule_length_default')

            updated['image_separator'] = st.text_input(
                'Separador entre imagens',
                value=str(rules.get('image_separator', '|')),
                key='rule_image_separator',
                help='Para o Bling, mantenha | quando houver várias imagens no mesmo produto.',
            )

            updated['auto_product_code'] = st.toggle(
                f'Gerar código se vier vazio: {_bool_label(bool(rules.get("auto_product_code", True)))}',
                value=bool(rules.get('auto_product_code', True)),
                key='rule_auto_product_code',
            )
            updated['unique_product_code'] = st.toggle(
                f'Evitar código duplicado: {_bool_label(bool(rules.get("unique_product_code", True)))}',
                value=bool(rules.get('unique_product_code', True)),
                key='rule_unique_product_code',
            )

            st.text_input(
                'GTIN inválido',
                value='limpar e deixar vazio',
                disabled=True,
                key='rule_invalid_gtin_mode_visual',
                help='Por segurança, GTIN inválido não vai para o CSV final.',
            )
            updated['invalid_gtin_mode'] = 'limpar'

            col_save, col_reset = st.columns(2)
            with col_save:
                if st.button('Salvar padrões', use_container_width=True, key='save_user_rules'):
                    set_user_rules(updated)
                    st.success('Padrões salvos nesta sessão.')
            with col_reset:
                if st.button('Restaurar', use_container_width=True, key='reset_user_rules'):
                    reset_user_rules()
                    st.success('Padrões restaurados.')
                    st.rerun()

            st.markdown('##### Padrões atuais')
            current = get_user_rules()
            for option in RULE_OPTIONS:
                value = current.get(option.key, default_rules().get(option.key, ''))
                label = option.label.replace(' padrão', '')
                st.caption(f'{label}: {value}')
