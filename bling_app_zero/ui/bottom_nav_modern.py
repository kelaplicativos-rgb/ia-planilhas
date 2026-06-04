from __future__ import annotations

from urllib.parse import urlencode

import pandas as pd
import streamlit as st

from bling_app_zero.adapters.streamlit_action_executor import FLOW_MENU_KEY, LOG_MENU_KEY, execute_app_action, hard_reset_session
from bling_app_zero.adapters.streamlit_shortcut_executor import execute_shortcut, go_home
from bling_app_zero.core.app_actions import ACTION_PARAM, BOTTOM_BAR_ACTIONS
from bling_app_zero.core.app_shortcuts import grouped_shortcuts
from bling_app_zero.core.diagnostics_model import build_diagnostic_snapshot

RESPONSIBLE_FILE = 'bling_app_zero/ui/bottom_nav_modern.py'


def _query_value(name: str) -> str:
    try:
        value = st.query_params.get(name, '')
        if isinstance(value, list):
            return str(value[0] if value else '').strip()
        return str(value or '').strip()
    except Exception:
        return ''


def _remove_action_param() -> None:
    try:
        st.query_params.pop(ACTION_PARAM, None)
    except Exception:
        pass


def _href_for_action(action: str) -> str:
    params: dict[str, object] = {}
    try:
        for key, value in dict(st.query_params).items():
            if key == ACTION_PARAM:
                continue
            params[str(key)] = value
    except Exception:
        params = {}
    params[ACTION_PARAM] = action
    return '?' + urlencode(params, doseq=True)


def _handle_sidebar_action() -> None:
    action = _query_value(ACTION_PARAM)
    if not action:
        return
    _remove_action_param()
    result = execute_app_action(action)
    if result.needs_rerun:
        st.rerun()


def _render_sidebar_css() -> None:
    st.markdown(
        '''
<style>
.bling-sidebar-actions-note{font-size:.78rem;color:#64748b;line-height:1.25;margin:.15rem 0 .55rem 0;}
.bling-sidebar-action-grid{display:grid;grid-template-columns:1fr;gap:.42rem;margin:.4rem 0 .2rem 0;}
.bling-sidebar-action-grid a{display:flex;align-items:center;justify-content:center;min-height:2.45rem;padding:.56rem .7rem;border-radius:12px;border:1px solid rgba(15,23,42,.16);background:#fff;color:#0f172a!important;text-decoration:none!important;font-weight:850;font-size:.9rem;box-shadow:0 1px 4px rgba(15,23,42,.06);}
.bling-sidebar-action-grid a:active{transform:translateY(1px);}
</style>
''',
        unsafe_allow_html=True,
    )


def _render_sidebar_action_links() -> None:
    links = '\n'.join(f'    <a href="{_href_for_action(action.key)}">{action.title}</a>' for action in BOTTOM_BAR_ACTIONS)
    st.markdown(
        f'''
<div class="bling-sidebar-actions-note">Ações do sistema sem ocupar a tela principal.</div>
<div class="bling-sidebar-action-grid">
{links}
</div>
''',
        unsafe_allow_html=True,
    )


def _render_shortcuts_menu() -> None:
    if not bool(st.session_state.get(FLOW_MENU_KEY)):
        return
    with st.expander('⚡ Atalhos rápidos', expanded=True):
        st.caption('Acesse rapidamente as principais ações do sistema.')
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
    with st.expander('🧪 Diagnóstico rápido', expanded=True):
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

    O nome público foi mantido para compatibilidade com imports antigos, mas a
    barra inferior fixa foi removida para evitar conflito no mobile, menu nativo
    do Streamlit e navegador do celular.
    """
    _handle_sidebar_action()
    with st.sidebar:
        _render_sidebar_css()
        st.markdown('### Sistema')
        _render_sidebar_action_links()
        _render_shortcuts_menu()
        _render_diagnostic_menu()


__all__ = ['render_bottom_nav']
