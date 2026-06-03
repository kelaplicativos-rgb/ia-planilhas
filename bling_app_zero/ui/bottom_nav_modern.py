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


def _handle_bottom_action() -> None:
    action = _query_value(ACTION_PARAM)
    if not action:
        return
    _remove_action_param()
    result = execute_app_action(action)
    if result.needs_rerun:
        st.rerun()


def _render_fixed_css() -> None:
    st.markdown(
        '''
<style>
.bling-bottom-fixed-spacer{height:110px;}
.bling-bottom-fixed{position:fixed;left:0;right:0;bottom:0;z-index:2147483000;padding:8px 10px calc(8px + env(safe-area-inset-bottom));background:rgba(255,255,255,.97);border-top:1px solid rgba(15,23,42,.12);box-shadow:0 -10px 30px rgba(15,23,42,.12);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);}
.bling-bottom-fixed-label{max-width:860px;margin:0 auto 5px auto;color:#475569;font-size:.72rem;font-weight:700;text-align:center;line-height:1.1;}
.bling-bottom-fixed-grid{max-width:860px;margin:0 auto;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;}
.bling-bottom-fixed-grid a{display:flex;align-items:center;justify-content:center;min-height:38px;padding:7px 5px;border-radius:12px;border:1px solid rgba(15,23,42,.16);background:#fff;color:#0f172a!important;text-decoration:none!important;font-weight:800;font-size:.84rem;box-shadow:0 1px 4px rgba(15,23,42,.08);white-space:nowrap;}
.bling-bottom-fixed-grid a:active{transform:translateY(1px);}
@media (max-width:520px){.bling-bottom-fixed{padding-left:7px;padding-right:7px;}.bling-bottom-fixed-grid{gap:4px;}.bling-bottom-fixed-grid a{font-size:.74rem;min-height:36px;padding-left:3px;padding-right:3px;border-radius:10px;}.bling-bottom-fixed-label{font-size:.68rem;}}
</style>
<div class="bling-bottom-fixed-spacer"></div>
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
            columns = st.columns(min(3, max(1, len(shortcuts))))
            for index, shortcut in enumerate(shortcuts):
                with columns[index % len(columns)]:
                    if st.button(shortcut.title, use_container_width=True, key=f'bottom_shortcut_{shortcut.key}'):
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
        if st.button('🧹 Limpeza total da sessão', use_container_width=True, key='bottom_hard_reset_confirm'):
            hard_reset_session(after_reset=go_home)
            st.rerun()


def _render_html_bottom_bar() -> None:
    links = '\n'.join(f'    <a href="{_href_for_action(action.key)}">{action.title}</a>' for action in BOTTOM_BAR_ACTIONS)
    st.markdown(
        f'''
<div class="bling-bottom-fixed">
  <div class="bling-bottom-fixed-label">Ações rápidas · atualizar · limpar · diagnosticar</div>
  <div class="bling-bottom-fixed-grid">
{links}
  </div>
</div>
''',
        unsafe_allow_html=True,
    )


def render_bottom_nav() -> None:
    _handle_bottom_action()
    _render_fixed_css()
    _render_shortcuts_menu()
    _render_diagnostic_menu()
    _render_html_bottom_bar()


__all__ = ['render_bottom_nav']
