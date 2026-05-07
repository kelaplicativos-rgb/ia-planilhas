from __future__ import annotations

import traceback

import streamlit as st

from bling_app_zero.core.debug import add_debug, render_debug_panel
from bling_app_zero.ui.home import render_home


APP_VERSION = '3.0.1-BLINGCREATOR'


def main() -> None:
    st.set_page_config(
        page_title='IA Planilhas → Bling',
        page_icon='🚀',
        layout='wide',
        initial_sidebar_state='collapsed',
    )

    add_debug(f'Aplicação iniciada | versão {APP_VERSION}', origin='APP')
    render_debug_panel()

    try:
        render_home()
    except Exception as exc:
        add_debug(f'Falha crítica: {exc}', origin='APP', level='ERRO')
        st.error('O app encontrou um erro interno, mas não caiu.')
        st.code(''.join(traceback.format_exception(type(exc), exc, exc.__traceback__)))


if __name__ == '__main__':
    main()
