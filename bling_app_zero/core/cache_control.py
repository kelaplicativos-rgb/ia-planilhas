from __future__ import annotations

from datetime import datetime

import streamlit as st

CACHE_BOOT_VERSION_KEY = 'bling_cache_boot_version'
CACHE_LAST_CLEAR_KEY = 'bling_cache_last_clear_reason'
CACHE_GLOBAL_CLEAR_ALLOWED_KEY = 'bling_allow_global_cache_clear'
CACHE_VERSION_CHANGED_KEY = 'bling_cache_version_changed_at'


def _scoped_key(name: str) -> str:
    try:
        from bling_app_zero.v2.session_store import state_key

        return state_key(name)
    except Exception:
        return name


def _safe_audit(action: str, *, status: str = 'INFO', details: dict | None = None) -> None:
    try:
        from bling_app_zero.core.audit import add_audit_event

        add_audit_event(
            action,
            area='APP',
            status=status,
            details={
                'responsible_file': 'bling_app_zero/core/cache_control.py',
                **(details or {}),
            },
        )
    except Exception:
        pass


def clear_session_state(reason: str = 'manual', *, preserve_core: bool = True) -> int:
    """Limpa apenas o estado da sessão atual.

    Em ambiente multiusuário, esta é a limpeza segura para botões de Home/Reboot.
    Ela não chama st.cache_data.clear() nem st.cache_resource.clear(), pois esses caches são globais.
    """
    preserved = set()
    if preserve_core:
        preserved.update(
            {
                _scoped_key(CACHE_BOOT_VERSION_KEY),
                _scoped_key(CACHE_LAST_CLEAR_KEY),
                _scoped_key(CACHE_VERSION_CHANGED_KEY),
                CACHE_BOOT_VERSION_KEY,
                CACHE_LAST_CLEAR_KEY,
                CACHE_VERSION_CHANGED_KEY,
            }
        )
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
        _safe_audit('streamlit_global_cache_cleared', status='OK', details={'reason': reason})
        return

    removed = clear_session_state(reason=f'session_only:{reason}', preserve_core=True)
    _safe_audit('session_state_cache_cleared', status='OK', details={'reason': reason, 'removed_keys': removed})


def clear_cache_once_per_version(app_version: str) -> None:
    """Força troca limpa de sessão quando o BLINGFIX muda a versão do app.

    O diagnóstico anterior mostrou a sessão presa em versão antiga. Por isso, quando
    APP_VERSION muda, limpamos o estado da sessão atual antes de gravar a nova versão.
    Não limpamos cache global por padrão para não interferir em outros usuários.
    """
    current_version = str(app_version or '').strip()
    key = _scoped_key(CACHE_BOOT_VERSION_KEY)
    reason_key = _scoped_key(CACHE_LAST_CLEAR_KEY)
    changed_key = _scoped_key(CACHE_VERSION_CHANGED_KEY)
    previous_version = str(st.session_state.get(key) or '').strip()

    if previous_version == current_version:
        st.session_state[reason_key] = f'version_seen:{current_version}'
        return

    removed = 0
    if previous_version:
        removed = clear_session_state(
            reason=f'version_changed:{previous_version}->{current_version}',
            preserve_core=True,
        )

    st.session_state[key] = current_version
    st.session_state[reason_key] = f'version_active:{current_version}'
    st.session_state[changed_key] = datetime.utcnow().isoformat(timespec='seconds') + 'Z'
    _safe_audit(
        'app_version_cache_checkpoint',
        status='OK',
        details={
            'previous_version': previous_version,
            'current_version': current_version,
            'removed_session_keys': removed,
            'global_cache_cleared': False,
        },
    )


__all__ = ['clear_cache_once_per_version', 'clear_session_state', 'clear_streamlit_cache']
