from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None

RULES_SESSION_KEY = 'bling_user_rules'

DEFAULT_RULES: dict[str, Any] = {
    'supplier_default': 'Não definido',
    'measure_unit_default': 'Centímetro',
    'height_default': '2',
    'width_default': '11',
    'depth_default': '18',
    'length_default': '18',
    'invalid_gtin_mode': 'limpar',
    'image_separator': '|',
    'auto_product_code': True,
    'unique_product_code': True,
    'custom_rules': [],
}

CUSTOM_RULE_KEYS = {
    'condition': '',
    'target_column': '',
    'fill_value': '',
    'only_when_empty': True,
    'enabled': True,
}


@dataclass(frozen=True)
class RuleOption:
    key: str
    label: str
    description: str
    default: Any


RULE_OPTIONS: list[RuleOption] = [
    RuleOption('supplier_default', 'Fornecedor padrão', 'Usado quando a coluna de fornecedor vier vazia.', DEFAULT_RULES['supplier_default']),
    RuleOption('measure_unit_default', 'Unidade de medida padrão', 'Usada quando existir coluna de unidade de medida.', DEFAULT_RULES['measure_unit_default']),
    RuleOption('height_default', 'Altura padrão', 'Usada quando altura vier vazia ou zero.', DEFAULT_RULES['height_default']),
    RuleOption('width_default', 'Largura padrão', 'Usada quando largura vier vazia ou zero.', DEFAULT_RULES['width_default']),
    RuleOption('depth_default', 'Profundidade padrão', 'Usada quando profundidade vier vazia ou zero.', DEFAULT_RULES['depth_default']),
    RuleOption('length_default', 'Comprimento padrão', 'Usado quando comprimento vier vazio ou zero.', DEFAULT_RULES['length_default']),
    RuleOption('invalid_gtin_mode', 'GTIN inválido', 'Modo atual: limpar e deixar vazio.', DEFAULT_RULES['invalid_gtin_mode']),
    RuleOption('image_separator', 'Separador de imagens', 'Separador usado no CSV final.', DEFAULT_RULES['image_separator']),
    RuleOption('auto_product_code', 'Gerar código quando vazio', 'Gera SKU/código automático quando o campo estiver vazio.', DEFAULT_RULES['auto_product_code']),
    RuleOption('unique_product_code', 'Evitar código duplicado', 'Ajusta códigos repetidos para ficarem únicos.', DEFAULT_RULES['unique_product_code']),
]


def default_rules() -> dict[str, Any]:
    rules = dict(DEFAULT_RULES)
    rules['custom_rules'] = []
    return rules


def _safe_text(value: Any, fallback: str = '') -> str:
    text = str(value if value is not None else '').strip()
    return text if text else fallback


def normalize_custom_rule(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    rule = dict(CUSTOM_RULE_KEYS)
    for key in rule:
        if key in raw:
            rule[key] = raw[key]

    rule['condition'] = _safe_text(rule.get('condition'))
    rule['target_column'] = _safe_text(rule.get('target_column'))
    rule['fill_value'] = _safe_text(rule.get('fill_value'))
    rule['only_when_empty'] = bool(rule.get('only_when_empty', True))
    rule['enabled'] = bool(rule.get('enabled', True))

    if not rule['condition'] or not rule['target_column']:
        return None
    return rule


def normalize_custom_rules(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in raw:
        rule = normalize_custom_rule(item)
        if not rule:
            continue
        key = (
            rule['condition'].lower(),
            rule['target_column'].lower(),
            rule['fill_value'].lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        normalized.append(rule)
    return normalized[:30]


def normalize_rules(raw: dict[str, Any] | None) -> dict[str, Any]:
    rules = default_rules()
    if isinstance(raw, dict):
        for key in rules:
            if key in raw:
                rules[key] = raw[key]

    rules['supplier_default'] = _safe_text(rules.get('supplier_default'), DEFAULT_RULES['supplier_default'])
    rules['measure_unit_default'] = _safe_text(rules.get('measure_unit_default'), DEFAULT_RULES['measure_unit_default'])
    rules['height_default'] = _safe_text(rules.get('height_default'), DEFAULT_RULES['height_default'])
    rules['width_default'] = _safe_text(rules.get('width_default'), DEFAULT_RULES['width_default'])
    rules['depth_default'] = _safe_text(rules.get('depth_default'), DEFAULT_RULES['depth_default'])
    rules['length_default'] = _safe_text(rules.get('length_default'), DEFAULT_RULES['length_default'])

    rules['invalid_gtin_mode'] = 'limpar'
    rules['auto_product_code'] = bool(rules.get('auto_product_code', True))
    rules['unique_product_code'] = bool(rules.get('unique_product_code', True))
    rules['image_separator'] = '|'
    rules['custom_rules'] = normalize_custom_rules(rules.get('custom_rules'))
    return rules


def get_user_rules() -> dict[str, Any]:
    if st is None:
        return default_rules()
    current = st.session_state.get(RULES_SESSION_KEY)
    rules = normalize_rules(current if isinstance(current, dict) else None)
    st.session_state[RULES_SESSION_KEY] = rules
    return rules


def set_user_rules(rules: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_rules(rules)
    if st is not None:
        st.session_state[RULES_SESSION_KEY] = normalized
    return normalized


def reset_user_rules() -> dict[str, Any]:
    return set_user_rules(default_rules())


def add_custom_rule(condition: str, target_column: str, fill_value: str, only_when_empty: bool = True) -> dict[str, Any]:
    current = get_user_rules()
    custom_rules = list(current.get('custom_rules', []))
    rule = normalize_custom_rule(
        {
            'condition': condition,
            'target_column': target_column,
            'fill_value': fill_value,
            'only_when_empty': only_when_empty,
            'enabled': True,
        }
    )
    if rule:
        custom_rules.append(rule)
    current['custom_rules'] = custom_rules
    return set_user_rules(current)


def remove_custom_rule(index: int) -> dict[str, Any]:
    current = get_user_rules()
    custom_rules = list(current.get('custom_rules', []))
    if 0 <= index < len(custom_rules):
        custom_rules.pop(index)
    current['custom_rules'] = custom_rules
    return set_user_rules(current)


def measure_defaults_from_rules(rules: dict[str, Any] | None = None) -> dict[str, str]:
    current = normalize_rules(rules)
    return {
        'altura': str(current['height_default']),
        'largura': str(current['width_default']),
        'profundidade': str(current['depth_default']),
        'comprimento': str(current['length_default']),
    }


def custom_rules_from_rules(rules: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    current = normalize_rules(rules)
    return list(current.get('custom_rules', []))
