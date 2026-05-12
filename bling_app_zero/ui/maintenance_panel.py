from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.cache_control import clear_streamlit_cache
from bling_app_zero.core.debug import LOG_SESSION_KEY


def _logs_to_text(logs: list[dict]) -> str:
    return '\n'.join(
        f"[{item.get('hora')}] [{item.get('nivel')}] [{item.get('origem')}] {item.get('mensagem')}"
        for item in logs
    )


def _render_cache_tools() -> None:
    st.markdown('###### Cache')
    st.caption('Limpa cache interno do Streamlit sem apagar o fluxo atual do usuário.')
    if st.button('Limpar cache agora', use_container_width=True, key='maintenance_clear_cache_now'):
        clear_streamlit_cache(reason='manual_sidebar_maintenance')
        add_audit_event('cache_cleared_manually', area='CACHE', details={'source': 'maintenance_panel'})
        st.success('Cache limpo. Recarregando...')
        st.rerun()


def _render_log_tools() -> None:
    logs = list(st.session_state.get(LOG_SESSION_KEY, []))
    st.markdown('###### Logs técnicos')
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button('Limpar logs', use_container_width=True, key='maintenance_clear_logs'):
            st.session_state[LOG_SESSION_KEY] = []
            add_audit_event('technical_logs_cleared_manually', area='LOGS', details={'source': 'maintenance_panel'})
            st.success('Logs limpos.')
            st.rerun()
    with col_b:
        st.download_button(
            'Baixar log debug',
            data=_logs_to_text(logs).encode('utf-8'),
            file_name='bling_debug.log',
            mime='text/plain; charset=utf-8',
            use_container_width=True,
            key=f'maintenance_download_debug_log_{len(logs)}',
            disabled=not bool(logs),
        )

    st.caption(f'{len(logs)} evento(s) técnico(s) registrado(s).')
    show_logs = st.toggle('Ver eventos técnicos', value=False, key='maintenance_show_recent_logs')
    if show_logs and logs:
        with st.container(border=True):
            for item in logs[-25:]:
                level = item.get('nivel', 'INFO')
                origin = item.get('origem', 'SISTEMA')
                message = item.get('mensagem', '')
                st.caption(f'[{level}] {origin}: {message}')


def render_maintenance_panel() -> None:
    with st.sidebar:
        with st.expander('Manutenção do sistema', expanded=True):
            _render_cache_tools()
            st.divider()
            _render_log_tools()


__all__ = ['render_maintenance_panel']
