from __future__ import annotations

import streamlit as st

from bling_app_zero.core.user_rules import get_user_rules, set_user_rules
from bling_app_zero.ui.category_conference_step import category_conference_ready, render_category_conference_step
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
    """Renderiza guardas finais sem alterar valores fora das decisões explícitas do usuário."""
    _ = key_scope
    render_category_conference_step()
    if not category_conference_ready():
        st.info('Para seguir com segurança, aplique a conferência de categorias ou pule explicitamente esta etapa.')
        return

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
