from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/links_uteis.py'

SYSTEM_LINKS = (
    ('Repositório do sistema', 'https://github.com/kelaplicativos-rgb/ia-planilhas'),
    ('App publicado', 'https://ia-planilhas.streamlit.app/'),
)


def render_links_uteis() -> None:
    add_audit_event(
        'links_uteis_rendered',
        area='LINKS_SISTEMA',
        status='OK',
        details={'responsible_file': RESPONSIBLE_FILE, 'links_count': len(SYSTEM_LINKS)},
    )

    st.markdown('### Links do sistema')
    st.caption('Área auxiliar apenas para abrir o app publicado e o repositório do projeto.')

    for label, url in SYSTEM_LINKS:
        st.link_button(label, url, use_container_width=True)

    st.info(
        'Links de importação do Bling não ficam nesta área. Para gerar CSV de importação, use o caminho Bling CSV. '
        'Para envio direto, use o caminho Bling API, que envia pela API e não usa link de importador.',
        icon='ℹ️',
    )


__all__ = ['render_links_uteis']
