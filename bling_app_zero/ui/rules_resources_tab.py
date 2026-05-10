from __future__ import annotations

import streamlit as st

from bling_app_zero.core.user_rules import get_user_rules, reset_user_rules, set_user_rules
from bling_app_zero.ui.sidebar_skin import sidebar_header, sidebar_mini_label, sidebar_pills

WATCHED_RESOURCES = ['clean_invalid_gtin', 'normalize_image_separator', 'auto_product_code', 'unique_product_code']


def _bool_label(value: bool) -> str:
    return 'Ativo' if value else 'Desligado'


def _save_if_changed(original: dict, updated: dict) -> None:
    changed = any(bool(original.get(key, True)) != bool(updated.get(key, True)) for key in WATCHED_RESOURCES)
    if changed:
        set_user_rules(updated)
        st.session_state['resources_saved_notice'] = True
        st.rerun()


def _resource_toggle(label: str, description: str, value: bool, key: str) -> bool:
    with st.container(border=True):
        sidebar_mini_label(label)
        st.caption(description)
        sidebar_pills((_bool_label(value), value))
        return st.toggle(
            f'{label}: {_bool_label(value)}',
            value=value,
            key=key,
            label_visibility='collapsed',
        )


def render_resources_tab() -> None:
    original = get_user_rules()
    updated = dict(original)

    sidebar_header(
        'Recursos automáticos',
        'Tratamentos fixos aplicados antes do download final do CSV.',
    )

    if st.session_state.pop('resources_saved_notice', False):
        st.caption('✅ Recursos atualizados.')

    updated['clean_invalid_gtin'] = _resource_toggle(
        'Limpar GTIN inválido',
        'Quando o GTIN não for válido, o campo sai vazio no CSV final.',
        bool(updated.get('clean_invalid_gtin', True)),
        'resource_clean_invalid_gtin',
    )
    updated['normalize_image_separator'] = _resource_toggle(
        'Separar imagens por |',
        'Mantém múltiplas imagens no padrão aceito pelo Bling.',
        bool(updated.get('normalize_image_separator', True)),
        'resource_normalize_images',
    )
    updated['auto_product_code'] = _resource_toggle(
        'Gerar código automático',
        'Cria código quando a origem não trouxe SKU ou código.',
        bool(updated.get('auto_product_code', True)),
        'rule_auto_product_code',
    )
    updated['unique_product_code'] = _resource_toggle(
        'Evitar código duplicado',
        'Ajusta códigos repetidos antes do download.',
        bool(updated.get('unique_product_code', True)),
        'rule_unique_product_code',
    )

    updated['invalid_gtin_mode'] = 'limpar'
    updated['image_separator'] = '|'
    updated['custom_rules'] = original.get('custom_rules', [])

    _save_if_changed(original, updated)

    st.divider()
    st.caption('Alterações são salvas automaticamente.')

    if st.button('↩️ Restaurar recursos padrão', use_container_width=True, key='reset_user_resources'):
        reset_user_rules()
        st.session_state['resources_saved_notice'] = True
        st.rerun()
