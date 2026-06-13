from __future__ import annotations

from typing import Any

import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/oauth_link_guard.py'
READY_KEY = 'home_bling_auth_ready_url'
HOME_FLOW_SCHEMA_KEY = 'home_source_first_flow_schema_v1'
HOME_FLOW_SCHEMA_VERSION = 'source_first_origin_start_v5_no_render_oauth_20260613'
BACKEND_STATUS_KEY = 'home_bling_backend_last_status'


def _clean_url(value: object) -> str:
    return str(value or '').strip().replace('&amp;', '&')


def oauth_url_looks_unsafe(url: object) -> bool:
    text = _clean_url(url).lower()
    if not text:
        return False

    # A URL correta do Bling pode conter /Api/v3/oauth/authorize.
    # Por isso, quando for authorize oficial e não for host técnico/backend, mantemos segura.
    if 'api.bling.com.br' in text:
        return True
    if 'onrender.com/auth/bling' in text:
        return True
    if '/auth/bling/start' in text or '/auth/bling/callback' in text:
        return True
    if '/oauth2/views/login.php' in text:
        return True
    if '/oauth/token' in text:
        return True
    if '/oauth/authorize' in text:
        return False
    if 'bling.com.br/api/' in text or 'bling.com.br/api?' in text or 'bling.com.br/api/v' in text:
        return True
    return False


def _discard_ready_link(reason: str, url: object) -> None:
    st.session_state.pop(READY_KEY, None)
    st.session_state.pop(BACKEND_STATUS_KEY, None)
    add_audit_event(
        'bling_oauth_unsafe_cached_link_discarded',
        area='BLING_OAUTH',
        status='CORRIGIDO',
        details={
            'reason': reason,
            'url_preview': _clean_url(url)[:140],
            'schema_version': HOME_FLOW_SCHEMA_VERSION,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def install_oauth_link_guard() -> None:
    try:
        from bling_app_zero.ui import home_router
    except Exception as exc:
        add_audit_event(
            'bling_oauth_link_guard_import_failed',
            area='BLING_OAUTH',
            status='AVISO',
            details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE},
        )
        return

    # Força novo schema para a Home executar a limpeza de sessão antiga.
    try:
        home_router.HOME_FLOW_SCHEMA_VERSION = HOME_FLOW_SCHEMA_VERSION
    except Exception:
        pass

    # Garante que a chave do link preparado entre na limpeza, mesmo se o módulo antigo estiver carregado.
    try:
        keys = tuple(getattr(home_router, 'STALE_FLOW_KEYS', ()))
        if READY_KEY not in keys:
            home_router.STALE_FLOW_KEYS = (*keys, READY_KEY)
    except Exception:
        pass

    # Troca o validador da Home sem regravar o arquivo inteiro.
    try:
        home_router._oauth_url_looks_unsafe = oauth_url_looks_unsafe
    except Exception:
        pass

    ready_url = st.session_state.get(READY_KEY)
    if oauth_url_looks_unsafe(ready_url):
        _discard_ready_link('cached_ready_url_points_to_backend_or_api', ready_url)
        # Se o schema já estava marcado como válido, removemos para a Home resetar nesta renderização.
        st.session_state.pop(HOME_FLOW_SCHEMA_KEY, None)

    add_audit_event(
        'bling_oauth_link_guard_installed',
        area='BLING_OAUTH',
        status='OK',
        details={
            'schema_version': HOME_FLOW_SCHEMA_VERSION,
            'patched_home_validator': True,
            'ready_link_present': bool(st.session_state.get(READY_KEY)),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


__all__ = ['install_oauth_link_guard', 'oauth_url_looks_unsafe']
