from __future__ import annotations

import streamlit as st

from bling_app_zero.core.measurements import NORMALIZE_MEASURES_RESOURCE_KEY
from bling_app_zero.core.user_rules import get_user_rules, set_user_rules

WATCHED_RESOURCES = ['clean_invalid_gtin', 'normalize_image_separator', 'auto_product_code', 'unique_product_code']


def _bool_label(value: bool) -> str:
    return 'Sim' if value else 'Não'


def _save_if_changed(original: dict, updated: dict) -> None:
    changed = any(bool(original.get(key, True)) != bool(updated.get(key, True)) for key in WATCHED_RESOURCES)
    if changed:
        set_user_rules(updated)
        st.session_state['resources_saved_notice'] = True
        st.rerun()


def _resource_toggle(label: str, value: bool, key: str, help_text: str | None = None) -> bool:
    return st.toggle(
        f'{label}: {_bool_label(value)}',
        value=value,
        key=key,
        help=help_text,
    )


def _render_measure_normalizer_toggle() -> None:
    if NORMALIZE_MEASURES_RESOURCE_KEY not in st.session_state:
        st.session_state[NORMALIZE_MEASURES_RESOURCE_KEY] = True

    current = bool(st.session_state.get(NORMALIZE_MEASURES_RESOURCE_KEY, True))
    st.session_state[NORMALIZE_MEASURES_RESOURCE_KEY] = _resource_toggle(
        'Normalizar medidas para metro',
        current,
        'resource_normalize_measures_toggle',
        'Quando ligado, somente colunas de dimensão como Altura, Largura, Comprimento e Profundidade convertem 18 para 0,018 e 676 para 0,676 no CSV final.',
    )


def render_resources_tab() -> None:
    original = get_user_rules()
    updated = dict(original)

    st.caption('Tratamentos automáticos aplicados antes do download final.')

    if st.session_state.pop('resources_saved_notice', False):
        st.caption('✅ Recursos atualizados.')

    updated['clean_invalid_gtin'] = _resource_toggle(
        'Limpar GTIN inválido',
        bool(updated.get('clean_invalid_gtin', True)),
        'resource_clean_invalid_gtin',
    )
    updated['normalize_image_separator'] = _resource_toggle(
        'Separar imagens por |',
        bool(updated.get('normalize_image_separator', True)),
        'resource_normalize_images',
    )
    _render_measure_normalizer_toggle()
    updated['auto_product_code'] = _resource_toggle(
        'Gerar código automático',
        bool(updated.get('auto_product_code', True)),
        'rule_auto_product_code',
    )
    updated['unique_product_code'] = _resource_toggle(
        'Evitar código duplicado',
        bool(updated.get('unique_product_code', True)),
        'rule_unique_product_code',
    )

    updated['invalid_gtin_mode'] = 'limpar'
    updated['image_separator'] = '|'
    updated['custom_rules'] = get_user_rules().get('custom_rules', [])

    _save_if_changed(original, updated)
