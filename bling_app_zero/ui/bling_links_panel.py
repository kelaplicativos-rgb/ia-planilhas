from __future__ import annotations

import streamlit as st

RESPONSIBLE_FILE = 'bling_app_zero/ui/bling_links_panel.py'

USEFUL_BLING_LINKS = [
    {
        'label': 'Importar e atualizar estoque Bling',
        'url': 'https://www.bling.com.br/importador.saldos.estoque.php',
    },
    {
        'label': 'Importar e atualizar produtos',
        'url': 'https://www.bling.com.br/importador.produtos.php',
    },
    {
        'label': 'Importar e atualizar vínculo produtos multiloja',
        'url': 'https://www.bling.com.br/importador.precos.produtos.multiloja.php',
    },
]


def render_bling_links_panel() -> None:
    """Mostra links úteis fixos para importação no Bling.

    BLINGFIX: removido o painel antigo de próximos passos, links personalizados
    e textos comerciais. No final do fluxo ficam apenas os atalhos úteis.
    """
    st.markdown('#### Links úteis')
    for item in USEFUL_BLING_LINKS:
        st.link_button(item['label'], item['url'], use_container_width=True)


__all__ = ['USEFUL_BLING_LINKS', 'render_bling_links_panel']
