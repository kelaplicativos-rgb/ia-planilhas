from __future__ import annotations

from typing import Any

RESPONSIBLE_FILE = 'bling_app_zero/core/dimension_unit_defaults_runtime.py'
DIMENSION_UNIT_TARGET = 'Unidade das medidas'
DIMENSION_UNIT_DEFAULT = 'Centímetros'
PATCH_FLAG = '_dimension_unit_defaults_runtime_installed'


def _norm(value: Any) -> str:
    text = str(value or '').strip().lower()
    for old, new in {
        'í': 'i', 'é': 'e', 'ê': 'e', 'ã': 'a', 'á': 'a', 'à': 'a', 'â': 'a',
        'ô': 'o', 'ó': 'o', 'õ': 'o', 'ú': 'u', 'ç': 'c',
    }.items():
        text = text.replace(old, new)
    return ' '.join(text.split())


def normalize_dimension_unit(value: Any) -> str:
    key = _norm(value)
    if key in {'', 'centimetro', 'centimetros', 'cm'}:
        return 'Centímetros'
    if key in {'metro', 'metros', 'm'}:
        return 'Metros'
    if key in {'milimetro', 'milimetros', 'mm'}:
        return 'Milímetros'
    if key in {'vazio', '#vazio', '__vazio__', 'em branco', 'branco'}:
        return 'VAZIO'
    return str(value or DIMENSION_UNIT_DEFAULT).strip() or DIMENSION_UNIT_DEFAULT


def _make_rule(target: str, value: str, *, enabled: bool = True) -> dict[str, Any]:
    safe = ''.join(ch if ch.isalnum() else '_' for ch in target.strip().lower())
    safe = '_'.join(part for part in safe.split('_') if part)
    return {
        'id': f'sys_{safe or "rule"}'[:96],
        'condition': target,
        'target_column': target,
        'fill_value': value,
        'only_when_empty': True,
        'enabled': bool(enabled),
        'source': 'system',
    }


def _ensure_dimension_unit_rule(rules: dict[str, Any]) -> dict[str, Any]:
    out = dict(rules or {})
    out['measure_unit_name_default'] = normalize_dimension_unit(out.get('measure_unit_name_default'))
    custom_rules = list(out.get('custom_rules') or [])
    found = False
    updated_rules: list[dict[str, Any]] = []
    for raw in custom_rules:
        if not isinstance(raw, dict):
            continue
        rule = dict(raw)
        target = str(rule.get('target_column') or rule.get('condition') or '').strip()
        if target.lower() == DIMENSION_UNIT_TARGET.lower():
            rule['id'] = str(rule.get('id') or _make_rule(DIMENSION_UNIT_TARGET, DIMENSION_UNIT_DEFAULT)['id'])
            rule['condition'] = DIMENSION_UNIT_TARGET
            rule['target_column'] = DIMENSION_UNIT_TARGET
            rule['fill_value'] = normalize_dimension_unit(rule.get('fill_value') or out['measure_unit_name_default'])
            rule['only_when_empty'] = True
            rule['enabled'] = bool(rule.get('enabled', True))
            rule['source'] = 'system'
            out['measure_unit_name_default'] = str(rule['fill_value'])
            found = True
        updated_rules.append(rule)
    if not found:
        updated_rules.append(_make_rule(DIMENSION_UNIT_TARGET, out['measure_unit_name_default'], enabled=True))
    out['custom_rules'] = updated_rules
    return out


def _patch_user_rules() -> None:
    from bling_app_zero.core import user_rules

    if getattr(user_rules, PATCH_FLAG, False):
        return

    try:
        user_rules.DEFAULT_RULES['measure_unit_name_default'] = DIMENSION_UNIT_DEFAULT
    except Exception:
        pass
    try:
        if not any(str(rule.get('target_column') or '').strip().lower() == DIMENSION_UNIT_TARGET.lower() for rule in user_rules.DEFAULT_CUSTOM_RULES):
            user_rules.DEFAULT_CUSTOM_RULES.append(_make_rule(DIMENSION_UNIT_TARGET, DIMENSION_UNIT_DEFAULT, enabled=True))
    except Exception:
        pass

    original_normalize_rules = user_rules.normalize_rules

    def normalize_rules_with_dimension_unit(raw: dict[str, Any] | None) -> dict[str, Any]:
        return _ensure_dimension_unit_rule(original_normalize_rules(raw))

    user_rules.normalize_rules = normalize_rules_with_dimension_unit
    user_rules._dimension_unit_defaults_runtime_installed = True


def _patch_resources_state() -> None:
    try:
        from bling_app_zero.ui import rules_resources_state as state
    except Exception:
        return
    if 'measure_unit_name_default' not in state.WATCHED_DEFAULTS:
        state.WATCHED_DEFAULTS.append('measure_unit_name_default')
    state.SYSTEM_DEFAULT_TARGETS['measure_unit_name_default'] = DIMENSION_UNIT_TARGET
    state.DEFAULT_VALUES['measure_unit_name_default'] = DIMENSION_UNIT_DEFAULT


def _patch_rules_center_sections() -> None:
    try:
        from bling_app_zero.ui import rules_center_sections as sections
    except Exception:
        return
    sections.DIMENSION_UNIT_TARGET = DIMENSION_UNIT_TARGET
    sections.DIMENSION_UNIT_DEFAULT = DIMENSION_UNIT_DEFAULT
    original_all_default_targets = getattr(sections, '_all_default_targets', None)
    if callable(original_all_default_targets) and not getattr(original_all_default_targets, PATCH_FLAG, False):
        def _all_default_targets_with_dimension_unit() -> list[tuple[str, str]]:
            targets = list(original_all_default_targets())
            normalized = [str(target).strip().lower() for target, _value in targets]
            if DIMENSION_UNIT_TARGET.lower() not in normalized:
                targets.append((DIMENSION_UNIT_TARGET, DIMENSION_UNIT_DEFAULT))
            return [(target, normalize_dimension_unit(value) if str(target).strip().lower() == DIMENSION_UNIT_TARGET.lower() else value) for target, value in targets]
        _all_default_targets_with_dimension_unit._dimension_unit_defaults_runtime_installed = True  # type: ignore[attr-defined]
        sections._all_default_targets = _all_default_targets_with_dimension_unit


def install_dimension_unit_defaults_runtime() -> bool:
    _patch_user_rules()
    _patch_resources_state()
    _patch_rules_center_sections()
    return True


__all__ = [
    'DIMENSION_UNIT_DEFAULT',
    'DIMENSION_UNIT_TARGET',
    'RESPONSIBLE_FILE',
    'install_dimension_unit_defaults_runtime',
    'normalize_dimension_unit',
]
