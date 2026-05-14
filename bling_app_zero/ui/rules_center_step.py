from __future__ import annotations

import streamlit as st

from bling_app_zero.core.user_rules import get_user_rules, set_user_rules
from bling_app_zero.ui.rules_center_sections import render_protection_rules
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


def _render_rules_header() -> None:
    st.markdown('### Proteções do arquivo final')
    st.caption(
        'Aqui ficam somente proteções globais. Preenchimento de campo agora é feito no mapeamento: '
        'escolher coluna, escrever valor fixo ou deixar vazio.'
    )


def _strip_fill_rules(rules: dict) -> dict:
    updated = dict(rules or {})
    updated['custom_rules'] = []
    return updated


def render_rules_center_step() -> None:
    original_rules = _strip_fill_rules(get_user_rules())
    previous_signature = rules_signature(original_rules)
    st.session_state.setdefault(RULES_CENTER_AUTOSAVE_SIGNATURE_KEY, previous_signature)

    with st.container(border=True):
        _render_rules_header()
        rules = render_protection_rules(original_rules)
        rules = _strip_fill_rules(rules)
        normalized = set_user_rules(rules)
        auto_save_rules_if_changed(normalized, previous_signature)

        st.info('Valores padrão como Altura, Unidade, Situação ou Clonar dados do pai devem ser definidos em “escrever valor fixo” no mapeamento.')

        st.divider()
        col_save, col_reset = st.columns(2)
        with col_save:
            if st.button('Salvar proteções', use_container_width=True, key='rules_center_save'):
                mark_rules_ready(_strip_fill_rules(normalized), source='save_button')
                clear_mapping_rule_cache()
                st.success('Proteções salvas para esta sessão.')
        with col_reset:
            if st.button('Restaurar proteções padrão', use_container_width=True, key='rules_center_reset'):
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
