from __future__ import annotations

import streamlit as st

AUTO_MAPPING_LABEL = 'Ativar mapeamento automático'
GLOBAL_AUTO_MAPPING_KEY = 'home_mapping_auto_enabled'
GLOBAL_AUTO_MAPPING_DECIDED_KEY = 'home_mapping_auto_user_decided'
GLOBAL_AUTO_MAPPING_SOURCE_KEY = 'home_mapping_auto_decision_source'
RESPONSIBLE_FILE = 'bling_app_zero/ui/mapping_auto_decision.py'


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
    """Entrega a decisão global para o toggle real do mapeamento sem sobrescrever escolha local já feita."""
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
    """Mostra a decisão do usuário antes do mapeamento e persiste para cadastro/estoque."""
    enabled = st.toggle(
        label,
        value=mapping_auto_decision(default=default),
        key=widget_key,
        help=(
            'Desligado: os campos começam vazios e você escolhe manualmente. '
            'Ligado: o sistema tenta sugerir as colunas automaticamente, mas você ainda revisa e confirma antes de enviar.'
        ),
    )
    set_mapping_auto_decision(bool(enabled), source=source)
    if enabled:
        st.caption('Mapeamento automático ligado: o próximo passo já abrirá com sugestões para revisão.')
    else:
        st.caption('Mapeamento automático desligado: o próximo passo abrirá sem ligar colunas sozinho.')
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
