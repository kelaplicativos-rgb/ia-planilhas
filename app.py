from __future__ import annotations

import traceback

import streamlit as st

from bling_app_zero.core.debug import add_debug, render_debug_panel
from bling_app_zero.ui.home import render_home


APP_VERSION = '3.4.8-ANDROID-UPLOAD-FIX'


def _register_critical_error(exc: Exception) -> str:
    formatted = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    add_debug(f'Falha critica: {exc}', origin='APP', level='ERRO')
    add_debug(formatted, origin='TRACEBACK', level='ERRO')
    return formatted


def main() -> None:
    st.set_page_config(
        page_title='IA Planilhas -> Bling',
        page_icon='🚀',
        layout='wide',
        initial_sidebar_state='collapsed',
    )

    add_debug(f'Aplicacao iniciada | versao {APP_VERSION}', origin='APP')

    try:
        render_home()
    except Exception as exc:
        formatted = _register_critical_error(exc)
        st.error('O app encontrou um erro interno, mas nao caiu.')
        st.caption('Baixe o log debug na barra lateral para enviar o erro completo do BLINGFIX.')
        st.code(formatted)
    finally:
        render_debug_panel()


if __name__ == '__main__':
    main()
