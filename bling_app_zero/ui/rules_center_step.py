from __future__ import annotations

from typing import Any

import streamlit as st

from bling_app_zero.core.user_rules import RULE_OPTIONS, get_user_rules
from bling_app_zero.ui.rules_center_state import RULES_CENTER_READY_KEY, mark_rules_ready, rules_center_ready
from bling_app_zero.ui.rules_resources_state import DEFAULT_VALUES, SYSTEM_DEFAULT_TARGETS, sync_system_default_rules, text_value

RESPONSIBLE_FILE = 'bling_app_zero/ui/rules_center_step.py'
LEGACY_FINAL_PROTECTION_KEYS = (
    'clean_invalid_gtin',
    'normalize_image_separator',
    'auto_product_code',
    'unique_product_code',
)


def _toggle_value(raw: dict[str, Any], key: str, default: object) -> bool:
    return bool(raw.get(key, default))


def _render_rule_toggles(rules: dict[str, Any], updated: dict[str, Any], key_scope: str) -> None:
    st.markdown('##### Proteções automáticas')
    st.caption('Funcionam sem IA e entram antes da prévia final.')
    for option in RULE_OPTIONS:
        updated[option.key] = st.toggle(
            option.label,
            value=_toggle_value(rules, option.key, option.default),
            help=option.description,
            key=f'{key_scope}_rule_toggle_{option.key}',
        )


def _render_default_resources(rules: dict[str, Any], updated: dict[str, Any], key_scope: str) -> None:
    st.markdown('##### Padrões inteligentes')
    st.caption('Preenchem campos vazios de forma determinística, sem chamar Inteligência Artificial.')
    for default_key, target in SYSTEM_DEFAULT_TARGETS.items():
        updated[default_key] = st.text_input(
            f'{target} padrão',
            value=text_value(rules.get(default_key), DEFAULT_VALUES[default_key]),
            key=f'{key_scope}_default_{default_key}',
        )


def render_rules_center_step(key_scope: str = 'rules_resources') -> None:
    """Renderiza Regras e Recursos Inteligentes como etapa independente da IA."""
    rules = dict(get_user_rules())
    updated: dict[str, Any] = dict(rules)

    st.info('Regras e Recursos Inteligentes agora são uma etapa independente. A Inteligência Artificial entra somente na próxima etapa do fluxo.')
    _render_rule_toggles(rules, updated, key_scope)
    _render_default_resources(rules, updated, key_scope)
    updated = sync_system_default_rules(updated)

    normalized = mark_rules_ready(updated, source=f'{key_scope}_autosave')
    st.session_state[RULES_CENTER_READY_KEY] = True
    active_count = sum(1 for option in RULE_OPTIONS if bool(normalized.get(option.key)))
    st.success(f'Regras e recursos salvos. Proteções ativas: {active_count}.')


__all__ = [
    'LEGACY_FINAL_PROTECTION_KEYS',
    'RULES_CENTER_READY_KEY',
    'render_rules_center_step',
    'rules_center_ready',
]
