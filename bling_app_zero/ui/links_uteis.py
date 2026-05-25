from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/links_uteis.py'


def render_links_uteis() -> None:
    add_audit_event(
        'links_uteis_rendered',
        area='LINKS_UTEIS',
        status='OK',
        details={'responsible_file': RESPONSIBLE_FILE},
    )

    st.markdown('### Links uteis')
    st.caption('Central de atalhos do sistema. Use esta tela para organizar acessos rapidos.')

    st.markdown('#### Atalhos sugeridos')
    st.write('- Bling')
    st.write('- Central de ajuda Bling')
    st.write('- Repositorio do sistema')
    st.write('- App publicado')

    st.info('Os links clicaveis podem ser ajustados depois conforme os modulos definitivos do sistema forem evoluindo.')


__all__ = ['render_links_uteis']
