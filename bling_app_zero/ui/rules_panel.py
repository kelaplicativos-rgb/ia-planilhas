from __future__ import annotations

from typing import Any

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.user_rules import get_user_rules
from bling_app_zero.ui.home_wizard_constants import STEP_REGRAS, WIZARD_STEP_KEY
from bling_app_zero.ui.rules_center_step import render_rules_center_step


PROTECTION_LABELS = {
    'clean_invalid_gtin': 'GTIN inválido',
    'normalize_image_separator': 'Imagens por |',
    'normalize_measures_to_meters': 'Medidas',
    'auto_product_code': 'Código automático',
    'unique_product_code': 'Código único',
}


def _active_custom_rules(rules: dict[str, Any]) -> list[dict[str, Any]]:
    custom_rules = rules.get('custom_rules', [])
    if not isinstance(custom_rules, list):
        return []
    return [dict(rule) for rule in custom_rules if isinstance(rule, dict) and bool(rule.get('enabled', False))]


def _active_protection_labels(rules: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for key, label in PROTECTION_LABELS.items():
        if bool(rules.get(key, False)):
            labels.append(label)
    return labels


def _go_to_rules_step() -> None:
    st.session_state[WIZARD_STEP_KEY] = STEP_REGRAS
    st.session_state['sidebar_open_rules_center_inline'] = True
    st.session_state['sidebar_rules_center_requested'] = True
    add_audit_event(
        'sidebar_rules_center_opened',
        area='SIDEBAR',
        step=STEP_REGRAS,
        details={
            'target_step': STEP_REGRAS,
            'wizard_step_key': WIZARD_STEP_KEY,
            'fallback_inline_sidebar': True,
            'responsible_file': 'bling_app_zero/ui/rules_panel.py',
        },
    )
    st.rerun()


def _render_rules_summary(rules: dict[str, Any], active_rules: list[dict[str, Any]], active_protections: list[str]) -> None:
    st.caption('Resumo somente leitura. Use o botão abaixo para abrir a central completa.')
    st.metric('Padrões ativos', len(active_rules))
    st.metric('Proteções ativas', len(active_protections))

    if active_protections:
        st.caption('Proteções: ' + ', '.join(active_protections))
    else:
        st.caption('Nenhuma proteção ativa.')

    if active_rules:
        preview = []
        for rule in active_rules[:6]:
            column = str(rule.get('target_column') or rule.get('condition') or 'Coluna').strip()
            value = str(rule.get('fill_value') or '').strip()
            preview.append(f'{column}: {value if value else "vazio"}')
        st.caption('Padrões: ' + ' · '.join(preview))
        if len(active_rules) > 6:
            st.caption(f'+ {len(active_rules) - 6} outro(s) padrão(ões).')
    else:
        st.caption('Nenhum padrão ativo.')

    if st.button('Abrir Central de Regras', use_container_width=True, key='sidebar_open_rules_center'):
        _go_to_rules_step()


def render_rules_panel() -> None:
    """Resumo lateral das regras com atalho funcional para a Central de Regras."""
    rules = get_user_rules()
    active_rules = _active_custom_rules(rules)
    active_protections = _active_protection_labels(rules)
    show_inline_center = bool(st.session_state.get('sidebar_open_rules_center_inline', False))

    with st.sidebar:
        with st.expander('Regras e padrões', expanded=True):
            _render_rules_summary(rules, active_rules, active_protections)

            if show_inline_center:
                st.divider()
                st.caption('Central aberta também aqui na sidebar para não depender da etapa atual do fluxo.')
                if st.button('Fechar central na sidebar', use_container_width=True, key='sidebar_close_rules_center_inline'):
                    st.session_state['sidebar_open_rules_center_inline'] = False
                    add_audit_event(
                        'sidebar_rules_center_closed',
                        area='SIDEBAR',
                        details={'responsible_file': 'bling_app_zero/ui/rules_panel.py'},
                    )
                    st.rerun()
                render_rules_center_step()


__all__ = ['render_rules_panel']
