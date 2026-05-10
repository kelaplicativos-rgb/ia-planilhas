from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None

RULES_SESSION_KEY = 'bling_user_rules'

# REGRAS = valores escritos em colunas do CSV final.
DEFAULT_CUSTOM_RULES: list[dict[str, Any]] = [
    {'condition': 'Fornecedor', 'target_column': 'Fornecedor', 'fill_value': 'Não definido', 'only_when_empty': False, 'enabled': True, 'source': 'system'},
    {'condition': 'Nome fornecedor', 'target_column': 'Nome fornecedor', 'fill_value': 'Não definido', 'only_when_empty': False, 'enabled': True, 'source': 'system'},
    {'condition': 'Unidade', 'target_column': 'Unidade', 'fill_value': 'UN', 'only_when_empty': False, 'enabled': True, 'source': 'system'},
    {'condition': 'Unidade de medida', 'target_column': 'Unidade de medida', 'fill_value': 'UN', 'only_when_empty': False, 'enabled': True, 'source': 'system'},
    {'condition': 'Altura', 'target_column': 'Altura', 'fill_value': '2', 'only_when_empty': False, 'enabled': True, 'source': 'system'},
    {'condition': 'Largura', 'target_column': 'Largura', 'fill_value': '11', 'only_when_empty': False, 'enabled': True, 'source': 'system'},
    {'condition': 'Profundidade', 'target_column': 'Profundidade', 'fill_value': '18', 'only_when_empty': False, 'enabled': True, 'source': 'system'},
    {'condition': 'Comprimento', 'target_column': 'Comprimento', 'fill_value': '18', 'only_when_empty': False, 'enabled': True, 'source': 'system'},
    {'condition': 'Itens por caixa', 'target_column': 'Itens por caixa', 'fill_value': '1', 'only_when_empty': False, 'enabled': True, 'source': 'system'},
]

DEFAULT_RULES: dict[str, Any] = {
    'supplier_default': 'Não definido',
    'measure_unit_default': 'UN',
    'height_default': '2',
    'width_default': '11',
    'depth_default': '18',
    'length_default': '18',
    'clean_invalid_gtin': True,
    'normalize_image_separator': True,
    'invalid_gtin_mode': 'limpar',
    'image_separator': '|',
    'auto_product_code': True,
    'unique_product_code': True,
    'custom_rules': DEFAULT_CUSTOM_RULES,
}

CUSTOM_RULE_KEYS = {
    'condition': '',
    'target_column': '',
    'fill_value': '',
    'only_when_empty': False,
    'enabled': True,
    'source': 'user',
}


@dataclass(frozen=True)
class RuleOption:
    key: str
    label: str
    description: str
    default: Any


RULE_OPTIONS: list[RuleOption] = [
    RuleOption('clean_invalid_gtin', 'Limpar GTIN inválido', 'GTIN fora do padrão sai vazio antes do download final.', DEFAULT_RULES['clean_invalid_gtin']),
    RuleOption('normalize_image_separator', 'Separar imagens por |', 'Múltiplas imagens saem como img1|img2|img3.', DEFAULT_RULES['normalize_image_separator']),
    RuleOption('auto_product_code', 'Gerar código quando vazio', 'Gera SKU/código automático quando o campo estiver vazio.', DEFAULT_RULES['auto_product_code']),
    RuleOption('unique_product_code', 'Evitar código duplicado', 'Ajusta códigos repetidos para ficarem únicos.', DEFAULT_RULES['unique_product_code']),
]


def default_rules() -> dict[str, Any]:
    rules = dict(DEFAULT_RULES)
    rules['custom_rules'] = [dict(rule) for rule in DEFAULT_CUSTOM_RULES]
    return rules


def _safe_text(value: Any, fallback: str = '') -> str:
    text = str(value if value is not None else '').strip()
    return text if text else fallback


def _default_source_for_column(target_column: str) -> str:
    key = target_column.strip().lower()
    system_keys = {str(rule.get('target_column', '')).strip().lower() for rule in DEFAULT_CUSTOM_RULES}
    return 'system' if key in system_keys else 'user'


def normalize_custom_rule(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None

    rule = dict(CUSTOM_RULE_KEYS)
    for key in rule:
        if key in raw:
            rule[key] = raw[key]

    rule['target_column'] = _safe_text(rule.get('target_column'))
    rule['fill_value'] = _safe_text(rule.get('fill_value'))
    rule['condition'] = _safe_text(rule.get('condition'), rule['target_column'])
    rule['only_when_empty'] = bool(rule.get('only_when_empty', False))
    rule['enabled'] = bool(rule.get('enabled', True))
    source = _safe_text(rule.get('source'))
    rule['source'] = source if source in {'system', 'user'} else _default_source_for_column(rule['target_column'])

    if not rule['target_column']:
        return None
    return rule


def normalize_custom_rules(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        rule = normalize_custom_rule(item)
        if not rule:
            continue
        key = rule['target_column'].lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(rule)
    return normalized[:80]


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
    rules['clean_invalid_gtin'] = bool(rules.get('clean_invalid_gtin', True))
    rules['normalize_image_separator'] = bool(rules.get('normalize_image_separator', True))
    rules['invalid_gtin_mode'] = 'limpar'
    rules['image_separator'] = '|'
    rules['auto_product_code'] = bool(rules.get('auto_product_code', True))
    rules['unique_product_code'] = bool(rules.get('unique_product_code', True))
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


def add_custom_rule(condition: str, target_column: str, fill_value: str, only_when_empty: bool = False) -> dict[str, Any]:
    current = get_user_rules()
    custom_rules = list(current.get('custom_rules', []))
    rule = normalize_custom_rule(
        {
            'condition': target_column or condition,
            'target_column': target_column or condition,
            'fill_value': fill_value,
            'only_when_empty': only_when_empty,
            'enabled': True,
            'source': 'user',
        }
    )
    if rule:
        custom_rules = [r for r in custom_rules if str(r.get('target_column', '')).strip().lower() != rule['target_column'].lower()]
        custom_rules.append(rule)
    current['custom_rules'] = custom_rules
    return set_user_rules(current)


def update_custom_rule(index: int, target_column: str, fill_value: str, only_when_empty: bool = False) -> dict[str, Any]:
    current = get_user_rules()
    custom_rules = list(current.get('custom_rules', []))
    if not 0 <= index < len(custom_rules):
        return set_user_rules(current)

    old_source = str(custom_rules[index].get('source') or 'user')
    rule = normalize_custom_rule(
        {
            'condition': target_column,
            'target_column': target_column,
            'fill_value': fill_value,
            'only_when_empty': only_when_empty,
            'enabled': True,
            'source': old_source,
        }
    )
    if not rule:
        return set_user_rules(current)

    custom_rules[index] = rule
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in custom_rules:
        key = str(item.get('target_column', '')).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    current['custom_rules'] = deduped
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
