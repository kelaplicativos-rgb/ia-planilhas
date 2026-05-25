from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/modelos_bling.py'


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


def render_modelos_bling() -> None:
    add_audit_event(
        'modelos_bling_rendered',
        area='MODELOS_BLING',
        status='OK',
        details={'responsible_file': RESPONSIBLE_FILE},
    )

    st.markdown('### Modelos Bling')
    st.caption('Baixe modelos base para cadastro, estoque e atualizacao de precos.')

    cadastro = _modelo_cadastro()
    estoque = _modelo_estoque()
    precos = _modelo_precos()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button('Baixar cadastro', data=_csv_bytes(cadastro), file_name='modelo_bling_cadastro.csv', mime='text/csv', use_container_width=True)
    with col2:
        st.download_button('Baixar estoque', data=_csv_bytes(estoque), file_name='modelo_bling_estoque.csv', mime='text/csv', use_container_width=True)
    with col3:
        st.download_button('Baixar precos', data=_csv_bytes(precos), file_name='modelo_bling_precos.csv', mime='text/csv', use_container_width=True)

    with st.expander('Ver colunas dos modelos', expanded=False):
        st.caption('Cadastro')
        st.dataframe(cadastro, use_container_width=True, hide_index=True)
        st.caption('Estoque')
        st.dataframe(estoque, use_container_width=True, hide_index=True)
        st.caption('Precos')
        st.dataframe(precos, use_container_width=True, hide_index=True)

    st.warning('Esses modelos sao bases internas. Quando voce anexar um modelo oficial no fluxo Universal, o sistema deve respeitar o arquivo anexado.')


__all__ = ['render_modelos_bling']
