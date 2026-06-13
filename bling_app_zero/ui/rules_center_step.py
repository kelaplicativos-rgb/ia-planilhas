from __future__ import annotations

import streamlit as st

from bling_app_zero.core.user_rules import get_user_rules, set_user_rules
from bling_app_zero.ui.rules_center_state import RULES_CENTER_READY_KEY, rules_center_ready

RESPONSIBLE_FILE = 'bling_app_zero/ui/rules_center_step.py'
LEGACY_FINAL_PROTECTION_KEYS = (
    'clean_invalid_gtin',
    'normalize_image_separator',
    'auto_product_code',
    'unique_product_code',
)


def _disable_legacy_final_protections() -> dict:
    rules = dict(get_user_rules())
    for key in LEGACY_FINAL_PROTECTION_KEYS:
        rules[key] = False
    rules['custom_rules'] = []
    normalized = set_user_rules(rules)
    st.session_state[RULES_CENTER_READY_KEY] = True
    return normalized


def render_rules_center_step(key_scope: str = 'ia_real') -> None:
    """Mantém compatibilidade sem alterar o DataFrame final.

    O arquivo final agora obedece somente ao mapeamento e aos valores fixos
    escolhidos pelo usuário. As antigas proteções desta tela não podem limpar,
    preencher ou deduplicar dados depois do mapeamento.
    """
    _ = key_scope
    _disable_legacy_final_protections()
    st.markdown(
        '''
<style>
div[data-testid="stMarkdown"]:has(h4#ajustes-avancados-do-arquivo-final) {
    display: none;
}
</style>
''',
        unsafe_allow_html=True,
    )


__all__ = [
    'LEGACY_FINAL_PROTECTION_KEYS',
    'RULES_CENTER_READY_KEY',
    'render_rules_center_step',
    'rules_center_ready',
]
