from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None

RULES_SESSION_KEY = 'bling_user_rules'
RULES_SCHEMA_VERSION = 9
REMOVED_SYSTEM_RULE_COLUMNS = {'nome fornecedor', 'nome do fornecedor', 'unidade de medida', 'unidade medida'}
REMOVED_SYSTEM_RULE_PAIRS = {('fornecedor', 'não definido')}


def _make_rule_id(source: str, target_column: str) -> str:
    safe = ''.join(ch if ch.isalnum() else '_' for ch in str(target_column).strip().lower())
    safe = '_'.join(part for part in safe.split('_') if part)
    prefix = 'sys' if source == 'system' else 'usr'
    return f'{prefix}_{safe or "rule"}'[:96]


def _system_rule(target_column: str, fill_value: str) -> dict[str, Any]:
    return {
        'id': _make_rule_id('system', target_column),
        'condition': target_column,
        'target_column': target_column,
        'fill_value': fill_value,
        'only_when_empty': True,
        'enabled': True,
        'source': 'system',
    }


DEFAULT_CUSTOM_RULES: list[dict[str, Any]] = [
    _system_rule('Unidade', 'UN'),
    _system_rule('Altura', '2'),
    _system_rule('Largura', '11'),
    _system_rule('Profundidade', '18'),
    _system_rule('Comprimento', '18'),
    _system_rule('Itens por caixa', '1'),
]

DEFAULT_RULES: dict[str, Any] = {
    'schema_version': RULES_SCHEMA_VERSION,
    'measure_unit_default': 'UN',
    'height_default': '2',
    'width_default': '11',
    'depth_default': '18',
    'length_default': '18',
    'box_items_default': '1',
    'stock_available_default': '1000',
    'stock_low_default': '0',
    'stock_out_default': '0',
    'normalize_measures_to_meters': False,
    'clean_invalid_gtin': True,
    'normalize_image_separator': True,
    'invalid_gtin_mode': 'limpar',
    'image_separator': '|',
    'auto_product_code': True,
    'unique_product_code': True,
    'custom_rules': DEFAULT_CUSTOM_RULES,
}

CUSTOM_RULE_KEYS = {
    'id': '',
    'condition': '',
    'target_column': '',
    'fill_value': '',
    'only_when_empty': False,
    'enabled': False,
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


def _column_key(value: Any) -> str:
    return _safe_text(value).lower()


def _safe_schema_version(raw: dict[str, Any] | None) -> int:
    if not isinstance(raw, dict):
        return 0
    try:
        return int(raw.get('schema_version') or 0)
    except Exception:
        return 0


def _default_source_for_column(target_column: str) -> str:
    key = target_column.strip().lower()
    system_keys = {str(rule.get('target_column', '')).strip().lower() for rule in DEFAULT_CUSTOM_RULES}
    return 'system' if key in system_keys else 'user'


def _is_removed_system_rule(rule: dict[str, Any]) -> bool:
    source = _safe_text(rule.get('source')).lower()
    column = _column_key(rule.get('target_column'))
    value = _column_key(rule.get('fill_value'))
    return source == 'system' and (column in REMOVED_SYSTEM_RULE_COLUMNS or (column, value) in REMOVED_SYSTEM_RULE_PAIRS)


def _is_removed_supplier_default_rule(rule: dict[str, Any]) -> bool:
    column = _column_key(rule.get('target_column') or rule.get('condition'))
    value = _column_key(rule.get('fill_value'))
    return (column, value) in REMOVED_SYSTEM_RULE_PAIRS


def _enable_system_auto_fill_rules(custom_rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enabled: list[dict[str, Any]] = []
    system_columns = {str(rule.get('target_column', '')).strip().lower() for rule in DEFAULT_CUSTOM_RULES}
    for rule in custom_rules:
        current = dict(rule)
        if str(current.get('target_column', '')).strip().lower() in system_columns:
            current['enabled'] = True
        enabled.append(current)
    return enabled


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
    rule['enabled'] = bool(rule.get('enabled', False))

    source = _safe_text(rule.get('source'))
    rule['source'] = source if source in {'system', 'user'} else _default_source_for_column(rule['target_column'])
    if rule['source'] == 'system':
        rule['only_when_empty'] = True
    rule['id'] = _safe_text(rule.get('id'), _make_rule_id(rule['source'], rule['target_column']))

    if not rule['target_column'] or _is_removed_system_rule(rule) or _is_removed_supplier_default_rule(rule):
        return None
    return rule


def normalize_custom_rules(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    normalized: list[dict[str, Any]] = []
    seen_columns: set[str] = set()
    seen_ids: set[str] = set()
    for item in raw:
        rule = normalize_custom_rule(item)
        if not rule:
            continue
        column_key = rule['target_column'].lower()
        if column_key in seen_columns:
            continue
        rule_id = str(rule.get('id') or _make_rule_id(rule.get('source', 'user'), rule['target_column']))
        if rule_id in seen_ids:
            suffix = len(seen_ids) + 1
            rule_id = f'{rule_id}_{suffix}'[:96]
            rule['id'] = rule_id
        seen_columns.add(column_key)
        seen_ids.add(rule_id)
        normalized.append(rule)
    return normalized[:80]


def _merge_missing_default_rules(custom_rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = [dict(rule) for rule in custom_rules if not _is_removed_system_rule(dict(rule)) and not _is_removed_supplier_default_rule(dict(rule))]
    existing = {str(rule.get('target_column', '')).strip().lower() for rule in merged}
    for default_rule in DEFAULT_CUSTOM_RULES:
        key = str(default_rule.get('target_column', '')).strip().lower()
        if key and key not in existing:
            merged.append(dict(default_rule))
            existing.add(key)
    return normalize_custom_rules(merged)


def normalize_rules(raw: dict[str, Any] | None) -> dict[str, Any]:
    incoming_schema_version = _safe_schema_version(raw)
    rules = default_rules()
    if isinstance(raw, dict):
        for key in rules:
            if key in raw:
                rules[key] = raw[key]

    rules['schema_version'] = RULES_SCHEMA_VERSION
    rules['measure_unit_default'] = _safe_text(rules.get('measure_unit_default'), DEFAULT_RULES['measure_unit_default'])
    rules['height_default'] = _safe_text(rules.get('height_default'), DEFAULT_RULES['height_default'])
    rules['width_default'] = _safe_text(rules.get('width_default'), DEFAULT_RULES['width_default'])
    rules['depth_default'] = _safe_text(rules.get('depth_default'), DEFAULT_RULES['depth_default'])
    rules['length_default'] = _safe_text(rules.get('length_default'), DEFAULT_RULES['length_default'])
    rules['box_items_default'] = _safe_text(rules.get('box_items_default'), DEFAULT_RULES['box_items_default'])
    rules['stock_available_default'] = _safe_text(rules.get('stock_available_default'), DEFAULT_RULES['stock_available_default'])
    rules['stock_low_default'] = _safe_text(rules.get('stock_low_default'), DEFAULT_RULES['stock_low_default'])
    rules['stock_out_default'] = _safe_text(rules.get('stock_out_default'), DEFAULT_RULES['stock_out_default'])
    rules['normalize_measures_to_meters'] = False
    rules['clean_invalid_gtin'] = bool(rules.get('clean_invalid_gtin', True))
    rules['normalize_image_separator'] = bool(rules.get('normalize_image_separator', True))
    rules['invalid_gtin_mode'] = 'limpar'
    rules['image_separator'] = '|'
    rules['auto_product_code'] = bool(rules.get('auto_product_code', True))
    rules['unique_product_code'] = bool(rules.get('unique_product_code', True))
    rules['custom_rules'] = _merge_missing_default_rules(normalize_custom_rules(rules.get('custom_rules')))

    if incoming_schema_version < RULES_SCHEMA_VERSION:
        rules['custom_rules'] = _enable_system_auto_fill_rules(rules['custom_rules'])

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
    target = target_column or condition
    rule = normalize_custom_rule(
        {
            'id': _make_rule_id('user', target),
            'condition': target,
            'target_column': target,
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


def update_custom_rule_by_id(rule_id: str, target_column: str, fill_value: str, only_when_empty: bool = False) -> dict[str, Any]:
    current = get_user_rules()
    custom_rules = list(current.get('custom_rules', []))
    for index, old_rule in enumerate(custom_rules):
        if str(old_rule.get('id')) != str(rule_id):
            continue
        rule = normalize_custom_rule(
            {
                'id': old_rule.get('id') or rule_id,
                'condition': target_column,
                'target_column': target_column,
                'fill_value': fill_value,
                'only_when_empty': only_when_empty,
                'enabled': bool(old_rule.get('enabled', True)),
                'source': old_rule.get('source') or 'user',
            }
        )
        if rule:
            custom_rules[index] = rule
        break
    current['custom_rules'] = custom_rules
    return set_user_rules(current)


def set_custom_rule_enabled(rule_id: str, enabled: bool) -> dict[str, Any]:
    current = get_user_rules()
    custom_rules = list(current.get('custom_rules', []))
    for rule in custom_rules:
        if str(rule.get('id')) == str(rule_id):
            rule['enabled'] = bool(enabled)
            break
    current['custom_rules'] = custom_rules
    return set_user_rules(current)


def remove_custom_rule_by_id(rule_id: str) -> dict[str, Any]:
    current = get_user_rules()
    custom_rules = [rule for rule in current.get('custom_rules', []) if str(rule.get('id')) != str(rule_id)]
    current['custom_rules'] = custom_rules
    return set_user_rules(current)


def update_custom_rule(index: int, target_column: str, fill_value: str, only_when_empty: bool = False) -> dict[str, Any]:
    current = get_user_rules()
    custom_rules = list(current.get('custom_rules', []))
    if not 0 <= index < len(custom_rules):
        return set_user_rules(current)
    return update_custom_rule_by_id(str(custom_rules[index].get('id')), target_column, fill_value, only_when_empty)


def remove_custom_rule(index: int) -> dict[str, Any]:
    current = get_user_rules()
    custom_rules = list(current.get('custom_rules', []))
    if not 0 <= index < len(custom_rules):
        return set_user_rules(current)
    return remove_custom_rule_by_id(str(custom_rules[index].get('id')))


def measure_defaults_from_rules(rules: dict[str, Any] | None = None) -> dict[str, str]:
    current = normalize_rules(rules)
    return {
        'altura': str(current['height_default']),
        'largura': str(current['width_default']),
        'profundidade': str(current['depth_default']),
        'comprimento': str(current['length_default']),
        'itens_por_caixa': str(current['box_items_default']),
    }


def stock_defaults_from_rules(rules: dict[str, Any] | None = None) -> dict[str, str]:
    current = normalize_rules(rules)
    return {
        'disponivel': str(current['stock_available_default']),
        'baixo': str(current['stock_low_default']),
        'esgotado': str(current['stock_out_default']),
    }


def custom_rules_from_rules(rules: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    current = normalize_rules(rules)
    return list(current.get('custom_rules', []))
