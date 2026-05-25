from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/modelos_bling.py'
BLING_LINKS = (
    ('Abrir Bling', 'https://www.bling.com.br/'),
    ('Importador de preços multiloja', 'https://www.bling.com.br/importador.precos.produtos.multiloja.php'),
    ('Central de ajuda Bling', 'https://ajuda.bling.com.br/'),
)


def _csv_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.StringIO()
    df.to_csv(buffer, sep=';', index=False)
    return buffer.getvalue().encode('utf-8-sig')


def _modelo_cadastro() -> pd.DataFrame:
    return pd.DataFrame(columns=['Codigo', 'Descricao', 'Preco unitario', 'Unidade', 'GTIN EAN', 'Marca', 'Categoria', 'URL imagens'])


def _modelo_estoque() -> pd.DataFrame:
    return pd.DataFrame(columns=['Codigo', 'Descricao', 'Deposito', 'Quantidade', 'Observacoes'])


def _modelo_precos() -> pd.DataFrame:
    return pd.DataFrame(columns=['Codigo', 'Descricao', 'Loja', 'Preco atual', 'Novo preco', 'Margem'])


def _render_bling_links() -> None:
    st.markdown('#### Atalhos Bling')
    st.caption('Todos os links referentes ao Bling ficam concentrados nesta aba.')
    cols = st.columns(1)
    for label, url in BLING_LINKS:
        with cols[0]:
            st.link_button(label, url, use_container_width=True)


def _render_model_downloads(cadastro: pd.DataFrame, estoque: pd.DataFrame, precos: pd.DataFrame) -> None:
    st.markdown('#### Modelos base')
    st.caption('Baixe modelos base para cadastro, estoque e atualização de preços.')

    st.download_button('Baixar cadastro', data=_csv_bytes(cadastro), file_name='modelo_bling_cadastro.csv', mime='text/csv', use_container_width=True)
    st.download_button('Baixar estoque', data=_csv_bytes(estoque), file_name='modelo_bling_estoque.csv', mime='text/csv', use_container_width=True)
    st.download_button('Baixar preços', data=_csv_bytes(precos), file_name='modelo_bling_precos.csv', mime='text/csv', use_container_width=True)


def render_modelos_bling() -> None:
    add_audit_event(
        'modelos_bling_rendered',
        area='MODELOS_BLING',
        status='OK',
        details={'responsible_file': RESPONSIBLE_FILE},
    )

    st.markdown('### Bling')
    st.caption('Área exclusiva para modelos, atalhos e informações referentes ao Bling.')

    cadastro = _modelo_cadastro()
    estoque = _modelo_estoque()
    precos = _modelo_precos()

    _render_bling_links()
    st.markdown('---')
    _render_model_downloads(cadastro, estoque, precos)

    with st.expander('Ver colunas dos modelos', expanded=False):
        st.caption('Cadastro')
        st.dataframe(cadastro, use_container_width=True, hide_index=True)
        st.caption('Estoque')
        st.dataframe(estoque, use_container_width=True, hide_index=True)
        st.caption('Preços')
        st.dataframe(precos, use_container_width=True, hide_index=True)

    st.warning('Esses modelos são bases internas. Quando você anexar um modelo oficial no fluxo Universal, o sistema deve respeitar o arquivo anexado.')


__all__ = ['render_modelos_bling']
