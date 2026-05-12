from __future__ import annotations

from bling_app_zero.core.sidebar_rule_targets import SIDEBAR_RULE_DOT, append_sidebar_rule_dot, has_sidebar_rule, sidebar_rule_target_keys

SIDEBAR_RULE_FILTER_LABEL = f'{SIDEBAR_RULE_DOT} Regras/recursos'


def with_sidebar_rule_badge(target_label: str, target_keys: set[str] | None = None) -> str:
    """Adiciona a bolinha roxa no label do farol quando o campo tem regra/recurso."""
    return append_sidebar_rule_dot(target_label, target_keys)


def sidebar_rule_targets_from_columns(target_columns: list[str]) -> set[str]:
    return sidebar_rule_target_keys(target_columns)


def filter_sidebar_rule_targets(ordered_targets: list[str], target_keys: set[str]) -> list[str]:
    return [target for target in ordered_targets if has_sidebar_rule(target, target_keys)]


def sidebar_rule_count(ordered_targets: list[str], target_keys: set[str]) -> int:
    return len(filter_sidebar_rule_targets(ordered_targets, target_keys))


__all__ = [
    'SIDEBAR_RULE_DOT',
    'SIDEBAR_RULE_FILTER_LABEL',
    'filter_sidebar_rule_targets',
    'sidebar_rule_count',
    'sidebar_rule_targets_from_columns',
    'with_sidebar_rule_badge',
]
