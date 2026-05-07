from __future__ import annotations

import streamlit as st


OPERACOES = {
    'Cadastro de Produtos': 'cadastro',
    'Atualização de Estoque': 'estoque',
    'Busca Inteligente por Site': 'site',
}


def render_home() -> None:
    st.title('🚀 IA Planilhas → Bling')

    st.markdown('### Plataforma inteligente de integração com o ERP Bling')

    escolha = st.radio(
        'O que você deseja fazer?',
        list(OPERACOES.keys()),
        horizontal=True,
    )

    operacao = OPERACOES[escolha]
    st.session_state['tipo_operacao'] = operacao

    if operacao == 'cadastro':
        render_cadastro()

    elif operacao == 'estoque':
        render_estoque()

    elif operacao == 'site':
        render_site()


def render_cadastro() -> None:
    st.success('Motor independente de CADASTRO carregado.')

    st.file_uploader(
        'Anexe planilha, XML, PDF ou modelo fornecedor',
        type=['xlsx', 'xls', 'csv', 'xml', 'pdf'],
        key='upload_cadastro',
    )

    st.info('Fluxo preparado para ETL completo → Bling.')


def render_estoque() -> None:
    st.warning('Motor independente de ESTOQUE carregado.')

    st.file_uploader(
        'Anexe o modelo de estoque do Bling',
        type=['xlsx', 'xls', 'csv'],
        key='upload_estoque',
    )

    st.info('Este fluxo busca SOMENTE os campos solicitados pela planilha.')


def render_site() -> None:
    st.info('Crawler inteligente estilo Instant Data Scraper carregado.')

    st.text_area(
        'Links dos produtos/sites',
        height=180,
        key='urls_site',
    )

    st.info('Captura automática: preço, GTIN, imagens, estoque, SKU, categoria e descrição.')
