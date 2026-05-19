from __future__ import annotations

import streamlit as st

RESPONSIBLE_FILE = 'bling_app_zero/ui/bling_links_panel.py'

USEFUL_BLING_LINKS = [
    {
        'label': 'Importar e atualizar produtos',
        'url': 'https://www.bling.com.br/importador.produtos.php',
        'hint': 'Use este link quando o arquivo final for para cadastro/atualização de produtos.',
    },
    {
        'label': 'Importar e atualizar estoque Bling',
        'url': 'https://www.bling.com.br/importador.saldos.estoque.php',
        'hint': 'Use este link quando o arquivo final for para saldo/estoque.',
    },
    {
        'label': 'Importar e atualizar vínculo produtos multiloja',
        'url': 'https://www.bling.com.br/importador.precos.produtos.multiloja.php',
        'hint': 'Próximo fluxo sugerido para atualizar preços/vínculos por loja ou canal.',
    },
]


def render_bling_links_panel() -> None:
    """Mostra links úteis fixos para importação no Bling no final do fluxo."""
    st.markdown('### Links úteis')
    st.caption('Depois de baixar a planilha final, use o importador correspondente no Bling ou siga para o próximo fluxo.')

    for item in USEFUL_BLING_LINKS:
        st.link_button(item['label'], item['url'], use_container_width=True)
        st.caption(item['hint'])


__all__ = ['USEFUL_BLING_LINKS', 'render_bling_links_panel']
