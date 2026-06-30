from __future__ import annotations

import streamlit as st

from bling_app_zero.core.android_collector_link import android_collector_apk_source, android_collector_apk_url
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.production.production_config import (
    PRODUCTION_MODE_KEY,
    get_production_config,
)
from bling_app_zero.production.user_context import clear_current_user, get_current_user, set_demo_user
from bling_app_zero.ui.home_wizard_rerun import safe_rerun

RESPONSIBLE_FILE = 'bling_app_zero/ui/production_sidebar.py'


def _render_android_collector_download() -> None:
    url = android_collector_apk_url()
    source = android_collector_apk_source()
    st.markdown('##### 📱 Coletor Android')
    st.link_button('Baixar APK do coletor', url, use_container_width=True)
    st.caption('Para captura automática em Android quando não houver computador disponível.')
    add_audit_event(
        'sidebar_android_collector_apk_link_rendered',
        area='SIDEBAR',
        status='INFO',
        details={'source': source, 'responsible_file': RESPONSIBLE_FILE},
    )


def render_production_sidebar() -> None:
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

            _render_android_collector_download()

            st.markdown('##### Usuário')
            if user.authenticated:
                st.success(f'Logado: {user.email}')
                if st.button('Sair do usuário demo', use_container_width=True, key='mapeiaai_clear_demo_user'):
                    clear_current_user()
                    safe_rerun('production_sidebar_demo_user_cleared')
            else:
                st.caption('Sem usuário autenticado nesta sessão.')
                if st.button('Entrar como demo', use_container_width=True, key='mapeiaai_set_demo_user'):
                    set_demo_user()
                    safe_rerun('production_sidebar_demo_user_set')

            st.caption('Produção real: substituir usuário demo por Supabase Auth/Clerk/Auth0.')


__all__ = ['render_production_sidebar']
