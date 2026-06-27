from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event

AUTO_MAPPING_LABEL = 'Mostrar sugestões de mapeamento'
GLOBAL_AUTO_MAPPING_KEY = 'home_mapping_auto_enabled'
GLOBAL_AUTO_MAPPING_DECIDED_KEY = 'home_mapping_auto_user_decided'
GLOBAL_AUTO_MAPPING_SOURCE_KEY = 'home_mapping_auto_decision_source'
RESPONSIBLE_FILE = 'bling_app_zero/ui/mapping_auto_decision.py'


def _audit_mapping_toggle(*, value: bool, source: str, widget_key: str) -> None:
    try:
        add_audit_event(
            'mapping_auto_toggle_rendered',
            area='MAPEAMENTO',
            status='OK',
            details={
                'value': bool(value),
                'source': source,
                'widget_key': widget_key,
                'manual_mode_means_blank_mapping': True,
                'suggestions_are_visual_only': True,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
    except Exception:
        pass


def mapping_auto_decision(default: bool = False) -> bool:
    return bool(st.session_state.get(GLOBAL_AUTO_MAPPING_KEY, default))


def mapping_auto_decision_is_set() -> bool:
    return bool(st.session_state.get(GLOBAL_AUTO_MAPPING_DECIDED_KEY, False))


def set_mapping_auto_decision(enabled: bool, *, source: str = '') -> None:
    st.session_state[GLOBAL_AUTO_MAPPING_KEY] = bool(enabled)
    st.session_state[GLOBAL_AUTO_MAPPING_DECIDED_KEY] = True
    if source:
        st.session_state[GLOBAL_AUTO_MAPPING_SOURCE_KEY] = source


def seed_mapping_toggle_from_global(widget_key: str, *, default: bool = False) -> bool:
    """Entrega a decisão global para o toggle real do mapeamento sem trocar escolha local já feita."""
    if widget_key not in st.session_state and mapping_auto_decision_is_set():
        st.session_state[widget_key] = mapping_auto_decision(default=default)
    return bool(st.session_state.get(widget_key, mapping_auto_decision(default=default)))


def render_mapping_auto_decision_toggle(
    *,
    widget_key: str = 'home_mapping_auto_decision_toggle',
    source: str = 'wizard',
    default: bool = False,
    label: str = AUTO_MAPPING_LABEL,
) -> bool:
    """Mostra sugestões sem aplicar colunas sozinho no modo manual."""
    enabled = st.toggle(
        label,
        value=mapping_auto_decision(default=default),
        key=widget_key,
        help=(
            'Desligado: os campos começam vazios e você escolhe manualmente. '
            'Ligado: o sistema mostra e ordena sugestões, mas cada campo continua dependendo da sua escolha.'
        ),
    )
    set_mapping_auto_decision(bool(enabled), source=source)
    _audit_mapping_toggle(value=bool(enabled), source=source, widget_key=widget_key)
    if enabled:
        st.caption('Sugestões ligadas: o sistema destaca opções prováveis, mas só usa o campo que você selecionar.')
    else:
        st.caption('Sugestões desligadas: os campos continuam vazios até você escolher manualmente.')
    return bool(enabled)


__all__ = [
    'AUTO_MAPPING_LABEL',
    'GLOBAL_AUTO_MAPPING_KEY',
    'mapping_auto_decision',
    'mapping_auto_decision_is_set',
    'render_mapping_auto_decision_toggle',
    'seed_mapping_toggle_from_global',
    'set_mapping_auto_decision',
]
