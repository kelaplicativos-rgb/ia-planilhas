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
    return dict(DEFAULT_RULES)


def normalize_rules(raw: dict[str, Any] | None) -> dict[str, Any]:
    rules = default_rules()
    if isinstance(raw, dict):
        for key in rules:
            if key in raw:
                rules[key] = raw[key]

    for key in ['supplier_default', 'measure_unit_default', 'height_default', 'width_default', 'depth_default', 'length_default', 'image_separator']:
        rules[key] = str(rules.get(key, DEFAULT_RULES[key]) or '').strip()

    rules['invalid_gtin_mode'] = 'limpar'
    rules['auto_product_code'] = bool(rules.get('auto_product_code', True))
    rules['unique_product_code'] = bool(rules.get('unique_product_code', True))
    if not rules['image_separator']:
        rules['image_separator'] = '|'
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


def measure_defaults_from_rules(rules: dict[str, Any] | None = None) -> dict[str, str]:
    current = normalize_rules(rules)
    return {
        'altura': str(current['height_default']),
        'largura': str(current['width_default']),
        'profundidade': str(current['depth_default']),
        'comprimento': str(current['length_default']),
    }
