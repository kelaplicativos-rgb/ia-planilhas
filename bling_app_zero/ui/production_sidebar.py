from __future__ import annotations

import streamlit as st

from bling_app_zero.production.production_config import (
    ADMIN_PASSWORD_INPUT_KEY,
    PRODUCTION_MODE_KEY,
    admin_key,
    admin_mode_enabled,
    get_production_config,
    set_admin_mode,
)
from bling_app_zero.production.user_context import clear_current_user, get_current_user, set_demo_user

RESPONSIBLE_FILE = 'bling_app_zero/ui/production_sidebar.py'


def _try_enable_admin_mode() -> None:
    expected_key = admin_key()
    typed_key = str(st.session_state.get(ADMIN_PASSWORD_INPUT_KEY) or '').strip()
    if not expected_key:
        st.warning('Chave admin não configurada.')
        return
    if typed_key != expected_key:
        st.warning('Chave admin inválida.')
        return
    set_admin_mode(True)
    st.session_state.pop(ADMIN_PASSWORD_INPUT_KEY, None)
    st.rerun()


def _render_admin_login() -> None:
    with st.sidebar:
        with st.expander('🔒 Admin / Diagnóstico', expanded=False):
            st.caption('Área técnica protegida. Use somente para suporte, debug ou BLINGFIX.')
            st.text_input(
                'Chave admin',
                type='password',
                key=ADMIN_PASSWORD_INPUT_KEY,
                placeholder='Informe a chave de suporte',
            )
            if st.button('Liberar painel técnico', use_container_width=True, key='mapeiaai_enable_admin_mode'):
                _try_enable_admin_mode()


def render_production_sidebar() -> None:
    if not admin_mode_enabled():
        _render_admin_login()
        return

    with st.sidebar:
        with st.expander('🚀 Produção MapeiaAI', expanded=False):
            config = get_production_config()
            user = get_current_user()
            st.toggle('Modo produção', key=PRODUCTION_MODE_KEY, value=bool(st.session_state.get(PRODUCTION_MODE_KEY, False)))
            st.caption(f'Domínio: {config.app_domain}')
            st.caption(f'Ambiente: {config.environment}')
            st.caption(f'Auth: {config.auth_provider} · Pagamento: {config.payment_provider}')
            if config.database_url:
                st.success('Banco configurado.')
            else:
                st.warning('Banco ainda não configurado.')
            if config.webhook_secret_configured:
                st.success('Webhook secret configurado.')
            else:
                st.warning('Webhook secret ainda não configurado.')

            st.markdown('##### Usuário')
            if user.authenticated:
                st.success(f'Logado: {user.email}')
                if st.button('Sair do usuário demo', use_container_width=True, key='mapeiaai_clear_demo_user'):
                    clear_current_user()
                    st.rerun()
            else:
                st.caption('Sem usuário autenticado nesta sessão.')
                if st.button('Entrar como demo', use_container_width=True, key='mapeiaai_set_demo_user'):
                    set_demo_user()
                    st.rerun()

            st.caption('Produção real: substituir usuário demo por Supabase Auth/Clerk/Auth0.')
            if st.button('Bloquear painel técnico', use_container_width=True, key='mapeiaai_disable_admin_mode'):
                set_admin_mode(False)
                st.rerun()


__all__ = ['render_production_sidebar']
