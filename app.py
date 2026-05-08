from __future__ import annotations

import traceback

import streamlit as st

from bling_app_zero.core.debug import add_debug, render_debug_panel
from bling_app_zero.ui.home import render_home


APP_VERSION = '3.0.9-AI-ONLY-SCRAPER'


def _register_critical_error(exc: Exception) -> str:
    """Registra o traceback completo para aparecer no arquivo baixado pelo painel Debug."""
    formatted = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    add_debug(f'Falha crítica: {exc}', origin='APP', level='ERRO')
    add_debug(formatted, origin='TRACEBACK', level='ERRO')
    return formatted


def main() -> None:
    st.set_page_config(
        page_title='IA Planilhas → Bling',
        page_icon='🚀',
        layout='wide',
        initial_sidebar_state='collapsed',
    )

    add_debug(f'Aplicação iniciada | versão {APP_VERSION}', origin='APP')

    try:
        render_home()
    except Exception as exc:
        formatted = _register_critical_error(exc)
        st.error('O app encontrou um erro interno, mas não caiu.')
        st.caption('Baixe o log debug na barra lateral para enviar o erro completo do BLINGFIX.')
        st.code(formatted)
    finally:
        render_debug_panel()


if __name__ == '__main__':
    main()
