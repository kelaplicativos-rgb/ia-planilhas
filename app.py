from __future__ import annotations

import streamlit as st

from bling_app_zero.core import APP_VERSION, PAGE_CONFIG, register_critical_error
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.debug import add_debug
from bling_app_zero.ui.home import render_home
from bling_app_zero.ui.layout import inject_streamlit_toolbar_fix
from bling_app_zero.ui.sidebar_tools import render_sidebar_tools


def main() -> None:
    st.set_page_config(**PAGE_CONFIG)
    inject_streamlit_toolbar_fix()

    add_debug(f'Aplicacao iniciada | versao {APP_VERSION}', origin='APP')
    add_audit_event('app_started', area='APP', details={'version': APP_VERSION})

    try:
        render_home()
        add_audit_event('home_rendered', area='APP')
        render_sidebar_tools()
    except Exception as exc:
        formatted = register_critical_error(exc)
        add_audit_event('app_critical_error', area='APP', status='ERRO', details={'error': str(exc)})
        st.error('Encontrei um erro interno, mas o aplicativo continuou aberto.')
        st.caption('Abra a barra lateral, baixe o log debug e envie para o próximo BLINGFIX.')
        with st.expander('Ver detalhe técnico do erro', expanded=False):
            st.code(formatted)


if __name__ == '__main__':
    main()
