from __future__ import annotations

import streamlit as st

from bling_app_zero.core.user_rules import get_user_rules, set_user_rules
from bling_app_zero.ui.rules_center_sections import PROTECTION_FIELDS
from bling_app_zero.ui.rules_center_state import (
    RULES_CENTER_AUTOSAVE_SIGNATURE_KEY,
    RULES_CENTER_READY_KEY,
    auto_save_rules_if_changed,
    clear_mapping_rule_cache,
    mark_rules_ready,
    rules_center_ready,
    rules_signature,
)

RESPONSIBLE_FILE = 'bling_app_zero/ui/rules_center_step.py'


def _safe_widget_scope(value: object) -> str:
    text = str(value or '').strip().lower()
    safe = ''.join(ch if ch.isalnum() else '_' for ch in text)
    safe = '_'.join(part for part in safe.split('_') if part)
    return safe or 'ia_real'


def _render_rules_header() -> None:
    st.markdown('### Proteções do arquivo final')
    st.caption(
        'Aqui ficam somente proteções globais da IA Real antes do preview final. '
        'Preenchimento de campo agora é feito no mapeamento: escolher coluna, escrever valor fixo ou deixar vazio.'
    )


def _strip_fill_rules(rules: dict) -> dict:
    updated = dict(rules or {})
    updated['custom_rules'] = []
    return updated


def _render_protection_rules_scoped(rules: dict, widget_scope: str) -> dict:
    updated = dict(rules or {})
    prefix = f'rules_center_{_safe_widget_scope(widget_scope)}'
    cols = st.columns(4)
    for index, (key, label, help_text) in enumerate(PROTECTION_FIELDS):
        with cols[index % 4]:
            updated[key] = st.toggle(
                label,
                value=bool(updated.get(key, True)),
                help=help_text,
                key=f'{prefix}_{key}',
            )
    updated['normalize_measures_to_meters'] = False
    updated['invalid_gtin_mode'] = 'limpar'
    updated['image_separator'] = '|'
    return updated


def render_rules_center_step(key_scope: str = 'ia_real') -> None:
    widget_scope = _safe_widget_scope(key_scope)
    original_rules = _strip_fill_rules(get_user_rules())
    previous_signature = rules_signature(original_rules)
    st.session_state.setdefault(RULES_CENTER_AUTOSAVE_SIGNATURE_KEY, previous_signature)

    with st.container(border=True):
        _render_rules_header()
        rules = _render_protection_rules_scoped(original_rules, widget_scope)
        rules = _strip_fill_rules(rules)
        normalized = set_user_rules(rules)
        auto_save_rules_if_changed(normalized, previous_signature)

        st.info('Valores padrão como Altura, Unidade, Situação ou Clonar dados do pai devem ser definidos em “escrever valor fixo” no mapeamento.')

        st.divider()
        col_save, col_reset = st.columns(2)
        with col_save:
            if st.button('Salvar proteções', use_container_width=True, key=f'rules_center_{widget_scope}_save'):
                mark_rules_ready(_strip_fill_rules(normalized), source='save_button')
                clear_mapping_rule_cache()
                st.success('Proteções salvas para esta sessão.')
        with col_reset:
            if st.button('Restaurar proteções padrão', use_container_width=True, key=f'rules_center_{widget_scope}_reset'):
                restored = _strip_fill_rules(get_user_rules())
                restored['clean_invalid_gtin'] = True
                restored['normalize_image_separator'] = True
                restored['auto_product_code'] = True
                restored['unique_product_code'] = True
                normalized = set_user_rules(restored)
                st.session_state[RULES_CENTER_AUTOSAVE_SIGNATURE_KEY] = rules_signature(normalized)
                st.session_state[RULES_CENTER_READY_KEY] = True
                clear_mapping_rule_cache()
                st.success('Proteções padrão restauradas.')
                st.rerun()

    st.caption('Use Avançar para seguir. O que for escolhido no mapeamento terá prioridade no CSV final.')


__all__ = [
    'RULES_CENTER_READY_KEY',
    'render_rules_center_step',
    'rules_center_ready',
]
