from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/links_uteis.py'

LINKS = (
    ('Bling', 'https://www.bling.com.br/'),
    ('Importador de preços multiloja', 'https://www.bling.com.br/importador.precos.produtos.multiloja.php'),
    ('Central de ajuda Bling', 'https://ajuda.bling.com.br/'),
    ('Repositório do sistema', 'https://github.com/kelaplicativos-rgb/ia-planilhas'),
    ('App publicado', 'https://ia-planilhas.streamlit.app/'),
)


def render_links_uteis() -> None:
    add_audit_event(
        'links_uteis_rendered',
        area='LINKS_UTEIS',
        status='OK',
        details={'responsible_file': RESPONSIBLE_FILE, 'links_count': len(LINKS)},
    )

    st.markdown('### Links úteis')
    st.caption('Atalhos rápidos para usar depois de gerar os arquivos nos fluxos Universal, Bling e Preços.')

    cols = st.columns(2)
    for index, (label, url) in enumerate(LINKS):
        with cols[index % 2]:
            st.link_button(label, url, use_container_width=True)

    st.info('Use estes atalhos ao final dos fluxos para abrir o Bling, importar arquivos ou acessar o repositório do sistema.')


__all__ = ['render_links_uteis']
