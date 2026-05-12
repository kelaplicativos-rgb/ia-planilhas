from __future__ import annotations

import streamlit as st

CACHE_BOOT_VERSION_KEY = 'bling_cache_boot_version'
CACHE_LAST_CLEAR_KEY = 'bling_cache_last_clear_reason'


def clear_streamlit_cache(reason: str = 'manual') -> None:
    """Limpa caches do Streamlit sem apagar o session_state do usuário."""
    try:
        st.cache_data.clear()
    except Exception:
        pass
    try:
        st.cache_resource.clear()
    except Exception:
        pass
    st.session_state[CACHE_LAST_CLEAR_KEY] = reason


def clear_cache_once_per_version(app_version: str) -> None:
    """Limpa cache uma única vez quando a versão do app muda.

    Não limpa a cada rerun para não apagar o fluxo do usuário enquanto ele trabalha.
    """
    current_version = str(app_version or '').strip()
    previous_version = str(st.session_state.get(CACHE_BOOT_VERSION_KEY) or '').strip()
    if previous_version == current_version:
        return
    clear_streamlit_cache(reason=f'auto_version:{current_version}')
    st.session_state[CACHE_BOOT_VERSION_KEY] = current_version


__all__ = ['clear_cache_once_per_version', 'clear_streamlit_cache']
