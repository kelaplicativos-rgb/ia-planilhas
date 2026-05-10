from __future__ import annotations

import streamlit as st

from bling_app_zero.core.user_rules import get_user_rules, reset_user_rules, set_user_rules


def _bool_label(value: bool) -> str:
    return 'Sim' if value else 'Não'


def _save_if_changed(original: dict, updated: dict) -> None:
    watched = ['clean_invalid_gtin', 'normalize_image_separator', 'auto_product_code', 'unique_product_code']
    changed = any(bool(original.get(key, True)) != bool(updated.get(key, True)) for key in watched)
    if changed:
        set_user_rules(updated)
        st.success('Recursos atualizados automaticamente.')
        st.rerun()


def render_resources_tab() -> None:
    original = get_user_rules()
    updated = dict(original)

    st.markdown('##### Recursos automáticos')
    st.caption('Recursos são motores internos. O usuário só liga ou desliga.')

    updated['clean_invalid_gtin'] = st.toggle(
        f'Limpar GTIN inválido: {_bool_label(bool(updated.get("clean_invalid_gtin", True)))}',
        value=bool(updated.get('clean_invalid_gtin', True)),
        key='resource_clean_invalid_gtin',
    )
    updated['normalize_image_separator'] = st.toggle(
        f'Separar imagens por |: {_bool_label(bool(updated.get("normalize_image_separator", True)))}',
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
    updated['custom_rules'] = original.get('custom_rules', [])

    _save_if_changed(original, updated)

    st.caption('Alterações nos recursos são salvas automaticamente.')

    if st.button('Restaurar padrão', use_container_width=True, key='reset_user_resources'):
        reset_user_rules()
        st.success('Padrão restaurado.')
        st.rerun()
