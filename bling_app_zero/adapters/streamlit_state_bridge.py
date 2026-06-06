from __future__ import annotations

from typing import Any

import streamlit as st
from streamlit.errors import StreamlitAPIException

from bling_app_zero.core.app_state import AppState
from bling_app_zero.core.navigation_controller import NavigationState

RESPONSIBLE_FILE = 'bling_app_zero/adapters/streamlit_state_bridge.py'

# Chaves de controle do sidebar/bottom nav: são estado real do sistema, não widgets.
# BLINGSCAN: antes elas eram bloqueadas pelo prefixo "bottom_nav_", então os botões
# "Atalhos" e "Diagnóstico" mudavam o AppState, mas o sync nunca gravava no
# st.session_state. Resultado visual: o usuário clicava e parecia não funcionar.
PERSISTENT_CONTROL_KEYS = (
    'bottom_nav_fluxos_open',
    'bottom_nav_logs_open',
    'bottom_nav_last_refresh_at',
    'bottom_nav_last_safe_clear_at',
)

WIDGET_ACTION_KEY_PREFIXES = (
    'home_light_',
    'nav_',
    'sidebar_system_action_',
    'sidebar_shortcut_',
    'sidebar_hard_reset_',
    'support_diagnostic_',
)

WIDGET_ACTION_KEY_SUFFIXES = (
    '_button',
    '_btn',
)


def _is_persistent_control_key(key: object) -> bool:
    text = str(key or '')
    return text in PERSISTENT_CONTROL_KEYS


def _is_widget_action_key(key: object) -> bool:
    text = str(key or '')
    if not text:
        return False
    if _is_persistent_control_key(text):
        return False
    if text.startswith(WIDGET_ACTION_KEY_PREFIXES):
        return True
    return text.endswith(WIDGET_ACTION_KEY_SUFFIXES)


def _filtered_streamlit_state() -> dict[str, Any]:
    """Retorna session_state sem chaves de widgets/ações.

    Keys de widgets pertencem ao Streamlit. Elas não devem entrar no AppState
    neutro, porque depois o sync tentaria escrever nelas novamente e o
    Streamlit bloqueia quando o widget já foi instanciado.

    As chaves listadas em PERSISTENT_CONTROL_KEYS são exceções: apesar do nome
    começar com bottom_nav_, elas são estado persistente usado para abrir/fechar
    os menus de Atalhos e Diagnóstico.
    """
    data: dict[str, Any] = {}
    for key, value in dict(st.session_state).items():
        if _is_widget_action_key(key):
            continue
        data[str(key)] = value
    return data


def _safe_set_session_value(key: str, value: Any) -> None:
    """Atualiza session_state sem sobrescrever widgets já instanciados."""
    if _is_widget_action_key(key):
        return
    try:
        if st.session_state.get(key) == value:
            return
    except Exception:
        pass
    try:
        st.session_state[key] = value
    except StreamlitAPIException:
        return
    except Exception:
        return


def app_state_from_streamlit() -> AppState:
    return AppState.from_mapping(_filtered_streamlit_state())


def sync_app_state_to_streamlit(state: AppState) -> None:
    current_keys = set(str(key) for key in st.session_state.keys())
    raw_next_values = state.snapshot()
    next_values = {str(key): value for key, value in raw_next_values.items() if not _is_widget_action_key(key)}
    next_keys = set(next_values.keys())

    for key in current_keys - next_keys:
        if _is_widget_action_key(key):
            continue
        try:
            st.session_state.pop(key, None)
        except Exception:
            pass
    for key, value in next_values.items():
        _safe_set_session_value(key, value)


def navigation_state_from_streamlit() -> NavigationState:
    params: dict[str, str] = {}
    try:
        for key, value in dict(st.query_params).items():
            if isinstance(value, list):
                params[str(key)] = str(value[0] if value else '')
            else:
                params[str(key)] = str(value or '')
    except Exception:
        params = {}
    return NavigationState(params)


def sync_navigation_to_streamlit(navigation: NavigationState) -> None:
    target = navigation.snapshot()
    try:
        for key in list(st.query_params.keys()):
            if key not in target:
                st.query_params.pop(key, None)
        for key, value in target.items():
            if value:
                st.query_params[key] = value
            else:
                st.query_params.pop(key, None)
    except Exception:
        pass


def streamlit_state_mapping() -> dict[str, Any]:
    return _filtered_streamlit_state()


__all__ = [
    'app_state_from_streamlit',
    'navigation_state_from_streamlit',
    'streamlit_state_mapping',
    'sync_app_state_to_streamlit',
    'sync_navigation_to_streamlit',
]
