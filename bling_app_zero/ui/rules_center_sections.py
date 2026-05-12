from __future__ import annotations

from typing import Any

import streamlit as st

from bling_app_zero.core.rule_value_validator import rule_value_warning

PROTECTION_FIELDS = [
    ('clean_invalid_gtin', 'GTIN inválido', 'GTIN fora do padrão sai vazio no arquivo final.'),
    ('normalize_image_separator', 'Imagens por |', 'Múltiplas imagens saem como img1|img2|img3.'),
    ('auto_product_code', 'Código automático', 'Preenche código/SKU somente quando o campo estiver vazio.'),
    ('unique_product_code', 'Código único', 'Ajusta códigos repetidos quando o recurso estiver ativo.'),
]

MEASURE_DEFAULT_FIELDS = [
    ('A', 'Altura', 'height_default', '2'),
    ('L', 'Largura', 'width_default', '11'),
]

BASIC_DEFAULT_FIELDS = [
    ('Unidade', 'measure_unit_default', 'UN'),
    ('Itens por caixa', 'box_items_default', '1'),
]

EXTRA_DEFAULT_RULES = [
    ('Categoria', 'Vazio'),
    ('Clonar dados do pai', 'Não'),
    ('Condição do produto', 'Novo'),
    ('Descrição Complementar', 'Vazio'),
    ('Frete Grátis', 'Não'),
    ('Informações Adicionais', 'Vazio'),
    ('Situação', 'Ativo'),
    ('Vídeo', 'Vazio'),
    ('Volumes', '1'),
]


def rule_id(target_column: str) -> str:
    safe = ''.join(ch if ch.isalnum() else '_' for ch in str(target_column).strip().lower())
    safe = '_'.join(part for part in safe.split('_') if part)
    return f'sys_{safe or "rule"}'[:96]


def render_rule_value_warning(target: str, value: Any) -> None:
    warning = rule_value_warning(target, value)
    if warning:
        st.warning(warning)


def clean_number_text(value: Any, fallback: str = '') -> str:
    text = str(value if value is not None else '').strip().replace(',', '.')
    if not text:
        return fallback
    try:
        number = float(text)
    except Exception:
        return text.replace('.', ',')
    if number.is_integer():
        return str(int(number))
    return f'{number:.3f}'.rstrip('0').rstrip('.').replace('.', ',')


def custom_rules_by_column(rules: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for rule in rules.get('custom_rules', []) or []:
        if not isinstance(rule, dict):
            continue
        target = str(rule.get('target_column') or rule.get('condition') or '').strip()
        if target:
            out[target.lower()] = dict(rule)
    return out


def _value_or_fallback(rule: dict[str, Any], fallback: str) -> str:
    value = str(rule.get('fill_value', '') if rule else '').strip()
    return value if value else fallback


def upsert_system_rule(custom_rules: list[dict[str, Any]], target_column: str, fill_value: str, enabled: bool) -> list[dict[str, Any]]:
    target_key = target_column.strip().lower()
    updated: list[dict[str, Any]] = []
    found = False
    for rule in custom_rules:
        if not isinstance(rule, dict):
            continue
        current_target = str(rule.get('target_column') or rule.get('condition') or '').strip()
        if current_target.lower() == target_key:
            current = dict(rule)
            current['id'] = str(current.get('id') or rule_id(target_column))
            current['condition'] = target_column
            current['target_column'] = target_column
            current['fill_value'] = str(fill_value or '')
            current['only_when_empty'] = True
            current['enabled'] = bool(enabled)
            current['source'] = 'system'
            updated.append(current)
            found = True
        else:
            updated.append(dict(rule))
    if not found:
        updated.append(
            {
                'id': rule_id(target_column),
                'condition': target_column,
                'target_column': target_column,
                'fill_value': str(fill_value or ''),
                'only_when_empty': True,
                'enabled': bool(enabled),
                'source': 'system',
            }
        )
    return updated


def render_protection_rules(rules: dict[str, Any]) -> dict[str, Any]:
    st.markdown('#### Proteções do CSV final')
    st.caption('Ligue ou desligue os recursos que tratam o arquivo final.')
    updated = dict(rules)
    cols = st.columns(4)
    for index, (key, label, help_text) in enumerate(PROTECTION_FIELDS):
        with cols[index % 4]:
            updated[key] = st.toggle(label, value=bool(updated.get(key, True)), help=help_text, key=f'rules_center_{key}')
    updated['normalize_measures_to_meters'] = False
    updated['invalid_gtin_mode'] = 'limpar'
    updated['image_separator'] = '|'
    return updated


def render_measure_rules(rules: dict[str, Any], custom_rules: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    st.markdown('#### Medidas padrão do produto')
    st.caption('Campos editáveis com liga/desliga real. P/C alimenta Profundidade e Comprimento.')
    updated = dict(rules)
    measure_enabled = st.toggle('Usar medidas padrão quando a coluna existir e estiver vazia', value=True, key='rules_center_measure_defaults_enabled')
    unit_measure_enabled = st.toggle('Usar unidade das medidas', value=True, key='rules_center_measure_unit_enabled')
    cols = st.columns(4)

    for index, (short_label, target_label, key, fallback) in enumerate(MEASURE_DEFAULT_FIELDS):
        current_value = clean_number_text(updated.get(key), fallback)
        with cols[index]:
            value = st.text_input(short_label, value=current_value, key=f'rules_center_measure_value_{key}', help=target_label)
            render_rule_value_warning(target_label, value)
        value = clean_number_text(value, fallback)
        updated[key] = value
        custom_rules = upsert_system_rule(custom_rules, target_label, value, measure_enabled)

    depth_value = clean_number_text(updated.get('depth_default'), '18')
    length_value = clean_number_text(updated.get('length_default'), depth_value or '18')
    pc_value = depth_value if depth_value == length_value else depth_value or length_value or '18'
    with cols[2]:
        pc_value = st.text_input('P/C', value=pc_value, key='rules_center_measure_value_depth_length_default', help='Profundidade e Comprimento')
        render_rule_value_warning('Profundidade/Comprimento', pc_value)
    pc_value = clean_number_text(pc_value, '18')
    updated['depth_default'] = pc_value
    updated['length_default'] = pc_value
    custom_rules = upsert_system_rule(custom_rules, 'Profundidade', pc_value, measure_enabled)
    custom_rules = upsert_system_rule(custom_rules, 'Comprimento', pc_value, measure_enabled)

    with cols[3]:
        unit_name = st.text_input(
            'Unidade medidas',
            value=str(updated.get('measure_unit_name_default') or 'Centímetro'),
            key='rules_center_measure_unit_name_value',
            help='Unidade das dimensões: Centímetro, Metro, Milímetro ou VAZIO',
        )
        render_rule_value_warning('Unidade das medidas', unit_name)
    updated['measure_unit_name_default'] = str(unit_name or '').strip()
    custom_rules = upsert_system_rule(custom_rules, 'Unidade das medidas', updated['measure_unit_name_default'], unit_measure_enabled)
    updated['normalize_measures_to_meters'] = False
    return updated, custom_rules


def render_basic_defaults(rules: dict[str, Any], custom_rules: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    st.markdown('#### Padrões básicos')
    st.caption('Preenchem somente se a coluna existir e estiver vazia.')
    updated = dict(rules)
    custom_by_column = custom_rules_by_column({'custom_rules': custom_rules})
    cols = st.columns(2)
    for index, (label, key, fallback) in enumerate(BASIC_DEFAULT_FIELDS):
        current_value = str(updated.get(key) or fallback)
        rule = custom_by_column.get(label.lower(), {})
        if rule:
            current_value = _value_or_fallback(rule, current_value)
        with cols[index % 2]:
            enabled = st.toggle(f'Usar {label}', value=bool(rule.get('enabled', True)), key=f'rules_center_basic_enabled_{key}')
            value = st.text_input(label, value=current_value, key=f'rules_center_basic_value_{key}')
            render_rule_value_warning(label, value)
        updated[key] = value
        custom_rules = upsert_system_rule(custom_rules, label, value, enabled)
    return updated, custom_rules


def render_extra_default_rules(custom_rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    st.markdown('#### Padrões finais')
    st.caption('Campos extras do modelo Bling. Ficam visíveis para revisão e só preenchem células vazias.')
    custom_by_column = custom_rules_by_column({'custom_rules': custom_rules})
    for row_start in range(0, len(EXTRA_DEFAULT_RULES), 2):
        cols = st.columns(2)
        for col_index, (target, fallback) in enumerate(EXTRA_DEFAULT_RULES[row_start:row_start + 2]):
            rule = custom_by_column.get(target.lower(), {})
            with cols[col_index]:
                enabled = st.toggle(f'Usar {target}', value=bool(rule.get('enabled', True)), key=f'rules_center_extra_enabled_{rule_id(target)}')
                value = st.text_input(target, value=_value_or_fallback(rule, fallback), key=f'rules_center_extra_value_{rule_id(target)}')
                render_rule_value_warning(target, value)
            custom_rules = upsert_system_rule(custom_rules, target, value, enabled)
    return custom_rules


def render_default_rules(rules: dict[str, Any]) -> dict[str, Any]:
    updated = dict(rules)
    custom_rules = list(updated.get('custom_rules', []) or [])
    updated, custom_rules = render_measure_rules(updated, custom_rules)
    st.divider()
    updated, custom_rules = render_basic_defaults(updated, custom_rules)
    st.divider()
    custom_rules = render_extra_default_rules(custom_rules)
    updated['custom_rules'] = custom_rules
    return updated


__all__ = [
    'render_basic_defaults',
    'render_default_rules',
    'render_extra_default_rules',
    'render_measure_rules',
    'render_protection_rules',
]
