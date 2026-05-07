from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.home_shared import (
    download_final,
    load_cadastro_pipeline,
    load_estoque_pipeline,
    load_requested_columns_from_model,
    load_site_pipeline,
    preview_df,
    show_contract,
    show_mapping,
)
from bling_app_zero.ui.smart_upload import render_smart_upload_box


def _choose_site_model_df(upload) -> pd.DataFrame | None:
    if isinstance(upload.model_df, pd.DataFrame):
        return upload.model_df
    if isinstance(upload.source_df, pd.DataFrame):
        return upload.source_df
    return None


def render_site_panel() -> None:
    st.info('Crawler inteligente independente será carregado somente ao clicar em buscar.')
    st.caption('Tecnologia ativa: FLASH AMPLO + extração orientada por contrato de colunas.')

    modo = st.radio('Modo da captura por site', ['Cadastro completo', 'Estoque orientado pelo modelo'], horizontal=True)
    operation = 'cadastro' if modo == 'Cadastro completo' else 'estoque'

    upload = render_smart_upload_box(
        title='📎 Modelo Bling do site',
        operation=operation,
        key='smart_upload_site_modelo',
        allow_model=True,
        required_model=operation == 'estoque',
        accepted_types=['xlsx', 'xls', 'csv'],
    )

    df_modelo = _choose_site_model_df(upload)
    requested_columns = None
    if isinstance(df_modelo, pd.DataFrame):
        requested_columns = [str(c) for c in df_modelo.columns]
        show_contract(requested_columns)
        if operation == 'estoque':
            requested_columns_from_model = load_requested_columns_from_model()
            requested_columns = requested_columns_from_model(df_modelo)

    deposito = ''
    if operation == 'estoque':
        deposito = st.text_input('Nome do depósito para estoque por site', value='Não definido')

    raw_urls = st.text_area('URL inicial, categoria, home ou links de produtos', height=180, key='urls_site')

    all_products = st.checkbox('FLASH AMPLO: varrer site/categoria e buscar todos os produtos encontrados', value=True)
    col_limit_a, col_limit_b = st.columns(2)
    max_pages = int(col_limit_a.number_input('Limite de páginas varridas', min_value=10, max_value=3000, value=250, step=50))
    max_products = int(col_limit_b.number_input('Limite de produtos capturados', min_value=10, max_value=10000, value=1000, step=100))

    if st.button('Buscar FLASH AMPLO e gerar Bling', use_container_width=True):
        run_site_pipeline = load_site_pipeline()
        with st.spinner('Varrendo site, descobrindo produtos e extraindo somente as colunas solicitadas...'):
            df_site = run_site_pipeline(
                raw_urls,
                requested_columns=requested_columns,
                all_products=all_products,
                max_pages=max_pages,
                max_products=max_products,
                operation=operation,
            )
        st.session_state['df_site_bruto'] = df_site

        if operation == 'estoque':
            run_estoque_pipeline = load_estoque_pipeline()
            df_final, mapping = run_estoque_pipeline(df_site, df_modelo, deposito=deposito)
        else:
            run_cadastro_pipeline = load_cadastro_pipeline()
            df_final, mapping = run_cadastro_pipeline(df_site, df_modelo)

        st.session_state['df_site_final'] = df_final
        st.session_state['mapping_site'] = mapping
        st.session_state['operation_site'] = operation

    df_site_bruto = st.session_state.get('df_site_bruto')
    if isinstance(df_site_bruto, pd.DataFrame):
        preview_df('Captura do site baseada apenas no contrato', df_site_bruto)

    df_final = st.session_state.get('df_site_final')
    mapping = st.session_state.get('mapping_site', {})
    operation_state = st.session_state.get('operation_site', operation)
    if isinstance(df_final, pd.DataFrame):
        show_mapping(mapping)
        preview_df('Preview final Bling gerado pelo site', df_final)
        download_final(df_final, operation_state, 'site')
