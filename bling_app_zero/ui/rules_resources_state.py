from __future__ import annotations

from typing import Any

WATCHED_RESOURCES = [
    'clean_invalid_gtin',
    'normalize_image_separator',
    'limit_bling_images',
    'normalize_measures_to_meters',
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


def text_value(value: object, fallback: str = '') -> str:
    text = str(value if value is not None else '').strip()
    return text if text else fallback


def rule_key(value: object) -> str:
    return text_value(value).lower()


def make_rule_id(target_column: str) -> str:
    safe = ''.join(ch if ch.isalnum() else '_' for ch in str(target_column).strip().lower())
    safe = '_'.join(part for part in safe.split('_') if part)
    return f'sys_{safe or "rule"}'[:96]


def sync_system_default_rules(updated: dict[str, Any]) -> dict[str, Any]:
    """Sincroniza os padrões internos com regras de sistema invisíveis nas regras manuais."""
    custom_rules = updated.get('custom_rules', [])
    if not isinstance(custom_rules, list):
        custom_rules = []

    output: list[dict[str, Any]] = []
    seen_targets: set[str] = set()

    for raw_rule in custom_rules:
        if not isinstance(raw_rule, dict):
            continue
        rule = dict(raw_rule)
        target = text_value(rule.get('target_column') or rule.get('condition'))
        target_key = rule_key(target)
        system_key = ''
        for default_key, default_target in SYSTEM_DEFAULT_TARGETS.items():
            if target_key == default_target.lower():
                system_key = default_key
                break

        if system_key:
            target = SYSTEM_DEFAULT_TARGETS[system_key]
            rule['id'] = text_value(rule.get('id'), make_rule_id(target))
            rule['condition'] = target
            rule['target_column'] = target
            rule['fill_value'] = text_value(updated.get(system_key), DEFAULT_VALUES[system_key])
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
                'id': make_rule_id(target),
                'condition': target,
                'target_column': target,
                'fill_value': text_value(updated.get(default_key), DEFAULT_VALUES[default_key]),
                'only_when_empty': True,
                'enabled': False,
                'source': 'system',
            }
        )

    updated['custom_rules'] = output
    return updated


def resources_changed(original: dict[str, Any], updated: dict[str, Any]) -> bool:
    return any(bool(original.get(key, True)) != bool(updated.get(key, True)) for key in WATCHED_RESOURCES)


def defaults_changed(original: dict[str, Any], updated: dict[str, Any]) -> bool:
    return any(text_value(original.get(key), DEFAULT_VALUES[key]) != text_value(updated.get(key), DEFAULT_VALUES[key]) for key in WATCHED_DEFAULTS)


def should_save(original: dict[str, Any], updated: dict[str, Any]) -> bool:
    return resources_changed(original, updated) or defaults_changed(original, updated)


__all__ = [
    'DEFAULT_VALUES',
    'SYSTEM_DEFAULT_TARGETS',
    'WATCHED_DEFAULTS',
    'WATCHED_RESOURCES',
    'defaults_changed',
    'make_rule_id',
    'resources_changed',
    'rule_key',
    'should_save',
    'sync_system_default_rules',
    'text_value',
]
