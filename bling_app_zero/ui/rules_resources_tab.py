from __future__ import annotations

from typing import Any

import streamlit as st

from bling_app_zero.core.measurements import NORMALIZE_MEASURES_RESOURCE_KEY
from bling_app_zero.core.user_rules import get_user_rules, set_user_rules
from bling_app_zero.ui.rules_post_mapping_defaults_tab import render_post_mapping_defaults_tab
from bling_app_zero.ui.rules_resources_state import DEFAULT_VALUES, should_save, sync_system_default_rules, text_value


def _bool_label(value: bool) -> str:
    return 'Sim' if value else 'Não'


def _resource_checkbox(label: str, value: bool, key: str, help_text: str | None = None) -> bool:
    return st.checkbox(
        f'{label}: {_bool_label(value)}',
        value=bool(value),
        key=key,
        help=help_text,
    )


def _save_if_changed(original: dict[str, Any], updated: dict[str, Any]) -> None:
    if should_save(original, updated):
        set_user_rules(sync_system_default_rules(updated))
        st.session_state['resources_saved_notice'] = True
        st.rerun()


def _render_measure_normalizer(updated: dict[str, Any]) -> None:
    current = bool(updated.get('normalize_measures_to_meters', True))
    if NORMALIZE_MEASURES_RESOURCE_KEY not in st.session_state:
        st.session_state[NORMALIZE_MEASURES_RESOURCE_KEY] = current

    selected = _resource_checkbox(
        'Normalizar medidas para metro',
        current,
        'resource_normalize_measures_checkbox',
        'Converte somente colunas de dimensão física: 18 vira 0,018 e 676 vira 0,676 no CSV final.',
    )
    updated['normalize_measures_to_meters'] = bool(selected)
    st.session_state[NORMALIZE_MEASURES_RESOURCE_KEY] = bool(selected)


def _render_resource_flags(updated: dict[str, Any]) -> None:
    updated['clean_invalid_gtin'] = _resource_checkbox(
        'Limpar GTIN inválido',
        bool(updated.get('clean_invalid_gtin', True)),
        'resource_clean_invalid_gtin_checkbox',
    )
    updated['normalize_image_separator'] = _resource_checkbox(
        'Separar imagens por |',
        bool(updated.get('normalize_image_separator', True)),
        'resource_normalize_images_checkbox',
    )
    _render_measure_normalizer(updated)
    updated['auto_product_code'] = _resource_checkbox(
        'Gerar código automático',
        bool(updated.get('auto_product_code', True)),
        'rule_auto_product_code_checkbox',
    )
    updated['unique_product_code'] = _resource_checkbox(
        'Evitar código duplicado',
        bool(updated.get('unique_product_code', True)),
        'rule_unique_product_code_checkbox',
    )


def _text_input_default(updated: dict[str, Any], field: str, label: str, key: str) -> None:
    updated[field] = st.text_input(
        label,
        value=text_value(updated.get(field), DEFAULT_VALUES[field]),
        key=key,
    )


def _render_internal_defaults_summary(updated: dict[str, Any]) -> None:
    unit = text_value(updated.get('measure_unit_default'), DEFAULT_VALUES['measure_unit_default'])
    height = text_value(updated.get('height_default'), DEFAULT_VALUES['height_default'])
    width = text_value(updated.get('width_default'), DEFAULT_VALUES['width_default'])
    depth = text_value(updated.get('depth_default'), DEFAULT_VALUES['depth_default'])
    length = text_value(updated.get('length_default'), DEFAULT_VALUES['length_default'])
    box = text_value(updated.get('box_items_default'), DEFAULT_VALUES['box_items_default'])
    st.caption(f'Unidade {unit} · Medidas {height}/{width}/{depth}/{length} · Caixa {box}')


def _render_internal_defaults(updated: dict[str, Any]) -> None:
    st.divider()
    st.markdown('##### Padrões internos')
    _render_internal_defaults_summary(updated)

    with st.expander('Editar padrões internos', expanded=False):
        st.caption('Valores usados apenas como padrão. Não envolve IA.')
        _text_input_default(updated, 'measure_unit_default', 'Unidade', 'resource_default_unit')
        _text_input_default(updated, 'height_default', 'Altura', 'resource_default_height')
        _text_input_default(updated, 'width_default', 'Largura', 'resource_default_width')
        _text_input_default(updated, 'depth_default', 'Profundidade', 'resource_default_depth')
        _text_input_default(updated, 'length_default', 'Comprimento', 'resource_default_length')
        _text_input_default(updated, 'box_items_default', 'Itens por caixa', 'resource_default_box_items')


def render_resources_tab() -> None:
    original = get_user_rules()
    updated = dict(original)

    st.caption('Tratamentos automáticos aplicados antes do download final.')

    if st.session_state.pop('resources_saved_notice', False):
        st.caption('✅ Recursos atualizados.')

    _render_resource_flags(updated)
    _render_internal_defaults(updated)
    render_post_mapping_defaults_tab()

    updated['invalid_gtin_mode'] = 'limpar'
    updated['image_separator'] = '|'
    updated['custom_rules'] = original.get('custom_rules', [])

    _save_if_changed(original, updated)


__all__ = ['render_resources_tab']
