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

    st.markdown('### Sistema')
    st.caption('Atalhos do sistema. Links referentes ao Bling ficam somente na aba Bling.')

    for label, url in SYSTEM_LINKS:
        st.link_button(label, url, use_container_width=True)

    st.info('Use esta área apenas para acessar o app publicado ou o repositório. Para Bling, abra a aba Bling na home.')


__all__ = ['render_links_uteis']
