from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.cache_control import clear_streamlit_cache


def render_cache_panel() -> None:
    with st.sidebar:
        with st.expander('Cache do sistema', expanded=False):
            st.caption('Limpa cache interno do Streamlit sem apagar o fluxo atual do usuário.')
            if st.button('Limpar cache agora', use_container_width=True, key='bling_clear_cache_now'):
                clear_streamlit_cache(reason='manual_sidebar')
                add_audit_event('cache_cleared_manually', area='CACHE', details={'source': 'sidebar'})
                st.success('Cache limpo. Recarregando...')
                st.rerun()


__all__ = ['render_cache_panel']
