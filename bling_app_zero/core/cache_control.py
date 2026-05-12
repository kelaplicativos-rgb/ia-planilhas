from __future__ import annotations

import streamlit as st

CACHE_BOOT_VERSION_KEY = 'bling_cache_boot_version'
CACHE_LAST_CLEAR_KEY = 'bling_cache_last_clear_reason'
CACHE_GLOBAL_CLEAR_ALLOWED_KEY = 'bling_allow_global_cache_clear'


def _scoped_key(name: str) -> str:
    try:
        from bling_app_zero.v2.session_store import state_key

        return state_key(name)
    except Exception:
        return name


def clear_session_state(reason: str = 'manual', *, preserve_core: bool = True) -> int:
    """Limpa apenas o estado da sessão atual.

    Em ambiente multiusuário, esta é a limpeza segura para botões de Home/Reboot.
    Ela não chama st.cache_data.clear() nem st.cache_resource.clear(), pois esses caches são globais.
    """
    preserved = set()
    if preserve_core:
        preserved.update({CACHE_BOOT_VERSION_KEY, CACHE_LAST_CLEAR_KEY})
        try:
            from bling_app_zero.v2.user_context import USER_CONTEXT_KEY

            preserved.add(USER_CONTEXT_KEY)
        except Exception:
            pass

    removed = 0
    for key in list(st.session_state.keys()):
        if key in preserved:
            continue
        st.session_state.pop(key, None)
        removed += 1
    st.session_state[_scoped_key(CACHE_LAST_CLEAR_KEY)] = reason
    return removed


def clear_streamlit_cache(reason: str = 'manual', *, global_clear: bool = False) -> None:
    """Limpa cache com proteção multiusuário.

    Por padrão, NÃO limpa o cache global do Streamlit. Para limpeza global administrativa,
    chame com global_clear=True ou defina a chave administrativa no session_state.
    """
    allowed = bool(global_clear or st.session_state.get(CACHE_GLOBAL_CLEAR_ALLOWED_KEY, False))
    if allowed:
        try:
            st.cache_data.clear()
        except Exception:
            pass
        try:
            st.cache_resource.clear()
        except Exception:
            pass
        st.session_state[_scoped_key(CACHE_LAST_CLEAR_KEY)] = f'global:{reason}'
        return

    clear_session_state(reason=f'session_only:{reason}', preserve_core=True)


def clear_cache_once_per_version(app_version: str) -> None:
    """Marca versão por sessão sem limpar cache global automaticamente."""
    current_version = str(app_version or '').strip()
    key = _scoped_key(CACHE_BOOT_VERSION_KEY)
    previous_version = str(st.session_state.get(key) or '').strip()
    if previous_version == current_version:
        return
    st.session_state[key] = current_version
    st.session_state[_scoped_key(CACHE_LAST_CLEAR_KEY)] = f'version_seen:{current_version}'


__all__ = ['clear_cache_once_per_version', 'clear_session_state', 'clear_streamlit_cache']
