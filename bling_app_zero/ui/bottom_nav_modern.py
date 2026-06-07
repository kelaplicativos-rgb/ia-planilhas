from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.adapters.streamlit_action_executor import FLOW_MENU_KEY, LOG_MENU_KEY, execute_app_action, hard_reset_session
from bling_app_zero.adapters.streamlit_shortcut_executor import execute_shortcut, go_home
from bling_app_zero.core.app_actions import BOTTOM_BAR_ACTIONS
from bling_app_zero.core.diagnostics_model import build_diagnostic_snapshot
from bling_app_zero.ui.support_diagnostic_panel import render_support_diagnostic_panel_content

RESPONSIBLE_FILE = 'bling_app_zero/ui/bottom_nav_modern.py'


def _run_sidebar_action(action: object) -> None:
    result = execute_app_action(action)
    if result.needs_rerun:
        st.rerun()


def _render_sidebar_action_buttons() -> None:
    st.caption('Ferramentas rápidas do sistema.')
    for action in BOTTOM_BAR_ACTIONS:
        if st.button(action.title, use_container_width=True, key=f'sidebar_system_action_{action.key}'):
            _run_sidebar_action(action.key)


def _render_shortcuts_menu() -> None:
    if not bool(st.session_state.get(FLOW_MENU_KEY)):
        return
    with st.expander('⚡ Atalhos rápidos', expanded=True):
        st.caption('Acesse rapidamente as principais ações do sistema.')
        from bling_app_zero.core.app_shortcuts import grouped_shortcuts

        for group, shortcuts in grouped_shortcuts():
            st.markdown(f'##### {group}')
            columns = st.columns(min(2, max(1, len(shortcuts))))
            for index, shortcut in enumerate(shortcuts):
                with columns[index % len(columns)]:
                    if st.button(shortcut.title, use_container_width=True, key=f'sidebar_shortcut_{shortcut.key}'):
                        result = execute_shortcut(shortcut, home_callback=go_home)
                        if result.needs_rerun:
                            st.rerun()


def _render_diagnostic_menu() -> None:
    if not bool(st.session_state.get(LOG_MENU_KEY)):
        return
    with st.expander('🧪 Diagnóstico', expanded=True):
        render_support_diagnostic_panel_content(namespace='bottom_nav')
        st.divider()
        snapshot = build_diagnostic_snapshot(dict(st.session_state))
        st.caption(
            f'Caminho atual: {snapshot.active_flow} · Etapa: {snapshot.step} · '
            f'Operação: {snapshot.operation} · Origem: {snapshot.origin}'
        )
        rows = [{'dado': item.label, 'tamanho': item.value} for item in snapshot.data_items]
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.caption('Nenhum dado principal carregado nesta sessão.')
        if st.button('🧹 Limpeza total da sessão', use_container_width=True, key='sidebar_hard_reset_confirm'):
            hard_reset_session(after_reset=go_home)
            st.rerun()


def render_bottom_nav() -> None:
    """Renderiza ações rápidas no sidebar.

    O nome público foi mantido por compatibilidade, mas a barra inferior fixa
    foi removida. O sidebar agora usa botões nativos, sem links/query param.
    """
    with st.sidebar:
        st.markdown('### Sistema')
        _render_sidebar_action_buttons()
        _render_shortcuts_menu()
        _render_diagnostic_menu()


__all__ = ['render_bottom_nav']
