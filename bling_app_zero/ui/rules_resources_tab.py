from __future__ import annotations

from typing import Any

import streamlit as st

from bling_app_zero.core.measurements import NORMALIZE_MEASURES_RESOURCE_KEY
from bling_app_zero.core.user_rules import get_user_rules, set_user_rules

WATCHED_RESOURCES = [
    'clean_invalid_gtin',
    'normalize_image_separator',
    'auto_product_code',
    'unique_product_code',
]

WATCHED_DEFAULTS = [
    'measure_unit_default',
    'height_default',
    'width_default',
    'depth_default',
    'length_default',
    'box_items_default',
]

SYSTEM_DEFAULT_TARGETS = {
    'measure_unit_default': 'Unidade',
    'height_default': 'Altura',
    'width_default': 'Largura',
    'depth_default': 'Profundidade',
    'length_default': 'Comprimento',
    'box_items_default': 'Itens por caixa',
}

DEFAULT_VALUES = {
    'measure_unit_default': 'UN',
    'height_default': '2',
    'width_default': '11',
    'depth_default': '18',
    'length_default': '18',
    'box_items_default': '1',
}


def _bool_label(value: bool) -> str:
    return 'Sim' if value else 'Não'


def _text(value: object, fallback: str = '') -> str:
    text = str(value if value is not None else '').strip()
    return text if text else fallback


def _rule_key(value: object) -> str:
    return _text(value).lower()


def _resource_toggle(label: str, value: bool, key: str, help_text: str | None = None) -> bool:
    return st.toggle(
        f'{label}: {_bool_label(value)}',
        value=value,
        key=key,
        help=help_text,
    )


def _make_rule_id(target_column: str) -> str:
    safe = ''.join(ch if ch.isalnum() else '_' for ch in str(target_column).strip().lower())
    safe = '_'.join(part for part in safe.split('_') if part)
    return f'sys_{safe or "rule"}'[:96]


def _sync_system_default_rules(updated: dict[str, Any]) -> dict[str, Any]:
    """Mantém os padrões internos visíveis no sidebar e fora das regras manuais.

    Esses itens continuam sendo regras de sistema desativadas por padrão. A sidebar
    passa a ser a única fonte para editar os valores, evitando regra fantasma.
    """
    custom_rules = updated.get('custom_rules', [])
    if not isinstance(custom_rules, list):
        custom_rules = []

    output: list[dict[str, Any]] = []
    seen_targets: set[str] = set()

    for raw_rule in custom_rules:
        if not isinstance(raw_rule, dict):
            continue
        rule = dict(raw_rule)
        target = _text(rule.get('target_column') or rule.get('condition'))
        target_key = _rule_key(target)
        system_key = ''
        for default_key, default_target in SYSTEM_DEFAULT_TARGETS.items():
            if target_key == default_target.lower():
                system_key = default_key
                break

        if system_key:
            target = SYSTEM_DEFAULT_TARGETS[system_key]
            rule['id'] = _text(rule.get('id'), _make_rule_id(target))
            rule['condition'] = target
            rule['target_column'] = target
            rule['fill_value'] = _text(updated.get(system_key), DEFAULT_VALUES[system_key])
            rule['only_when_empty'] = True
            rule['source'] = 'system'
            rule['enabled'] = bool(rule.get('enabled', False))
            seen_targets.add(target.lower())

        output.append(rule)

    for default_key, target in SYSTEM_DEFAULT_TARGETS.items():
        if target.lower() in seen_targets:
            continue
        output.append(
            {
                'id': _make_rule_id(target),
                'condition': target,
                'target_column': target,
                'fill_value': _text(updated.get(default_key), DEFAULT_VALUES[default_key]),
                'only_when_empty': True,
                'enabled': False,
                'source': 'system',
            }
        )

    updated['custom_rules'] = output
    return updated


def _save_if_changed(original: dict[str, Any], updated: dict[str, Any]) -> None:
    resource_changed = any(bool(original.get(key, True)) != bool(updated.get(key, True)) for key in WATCHED_RESOURCES)
    default_changed = any(_text(original.get(key), DEFAULT_VALUES[key]) != _text(updated.get(key), DEFAULT_VALUES[key]) for key in WATCHED_DEFAULTS)
    if resource_changed or default_changed:
        set_user_rules(_sync_system_default_rules(updated))
        st.session_state['resources_saved_notice'] = True
        st.rerun()


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


def _render_internal_defaults(updated: dict[str, Any]) -> None:
    st.divider()
    st.markdown('##### Padrões internos')
    st.caption('Valores usados pelo exportador quando o campo correspondente precisar de padrão. Não envolve IA.')

    updated['measure_unit_default'] = st.text_input(
        'Unidade',
        value=_text(updated.get('measure_unit_default'), DEFAULT_VALUES['measure_unit_default']),
        key='resource_default_unit',
    )
    updated['height_default'] = st.text_input(
        'Altura',
        value=_text(updated.get('height_default'), DEFAULT_VALUES['height_default']),
        key='resource_default_height',
    )
    updated['width_default'] = st.text_input(
        'Largura',
        value=_text(updated.get('width_default'), DEFAULT_VALUES['width_default']),
        key='resource_default_width',
    )
    updated['depth_default'] = st.text_input(
        'Profundidade',
        value=_text(updated.get('depth_default'), DEFAULT_VALUES['depth_default']),
        key='resource_default_depth',
    )
    updated['length_default'] = st.text_input(
        'Comprimento',
        value=_text(updated.get('length_default'), DEFAULT_VALUES['length_default']),
        key='resource_default_length',
    )
    updated['box_items_default'] = st.text_input(
        'Itens por caixa',
        value=_text(updated.get('box_items_default'), DEFAULT_VALUES['box_items_default']),
        key='resource_default_box_items',
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

    _render_internal_defaults(updated)

    updated['invalid_gtin_mode'] = 'limpar'
    updated['image_separator'] = '|'
    updated['custom_rules'] = original.get('custom_rules', [])

    _save_if_changed(original, updated)
