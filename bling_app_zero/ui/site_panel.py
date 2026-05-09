from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.flows.site_operation_router import config_for_site_operation, run_site_engine
from bling_app_zero.ui.home_shared import load_site_pipeline, show_contract
from bling_app_zero.ui.site_models import (
    choose_site_cadastro_model_df,
    choose_site_estoque_model_df,
    choose_site_model_df,
    render_optional_site_model_upload,
    requested_columns_for_site_capture,
)
from bling_app_zero.ui.site_outputs import render_generated_site_actions, save_site_source
from bling_app_zero.ui.site_progress import make_site_progress_callback, reset_site_progress

ALL_PAGES_LIMIT = 1_000_000
ALL_PRODUCTS_LIMIT = 1_000_000


def _query_param(name: str) -> str:
    try:
        value = st.query_params.get(name, '')
        if isinstance(value, list):
            return str(value[0] if value else '')
        return str(value or '')
    except Exception:
        return ''


def _query_urls_default() -> str:
    return _query_param('urls') or _query_param('url')


def _render_site_models_step() -> tuple[object, pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None, list[str] | None]:
    st.markdown('#### 1. Modelos do Bling')
    upload = render_optional_site_model_upload()
    df_modelo_cadastro = choose_site_cadastro_model_df(upload)
    df_modelo_estoque = choose_site_estoque_model_df(upload)
    df_modelo = choose_site_model_df(upload)
    requested_columns = requested_columns_for_site_capture(df_modelo_cadastro, df_modelo_estoque)

    if requested_columns:
        show_contract(requested_columns)

    return upload, df_modelo_cadastro, df_modelo_estoque, df_modelo, requested_columns


def _render_urls_input() -> str:
    st.markdown('#### 2. Links do fornecedor')
    return st.text_area(
        'Cole site, categoria ou produtos',
        value=_query_urls_default(),
        height=120,
        key='urls_site',
        placeholder='https://site.com.br/categoria\nhttps://site.com.br/produto-1',
        label_visibility='collapsed',
    )


def _run_site_capture(
    raw_urls: str,
    requested_columns: list[str] | None,
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
    df_modelo: pd.DataFrame | None,
) -> None:
    reset_site_progress()
    progress_bar = st.progress(0, text='Iniciando busca...')
    status_box = st.empty()
    df_site = run_site_engine(
        operation='cadastro',
        pipeline=load_site_pipeline(),
        raw_urls=raw_urls,
        requested_columns=requested_columns,
        all_products=True,
        max_pages=ALL_PAGES_LIMIT,
        max_products=ALL_PRODUCTS_LIMIT,
        progress_callback=make_site_progress_callback(progress_bar, status_box),
    )
    save_site_source(df_site, raw_urls, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo)
    st.session_state['df_site_bruto'] = df_site
    st.session_state['operation_site'] = 'cadastro'
    st.rerun()


def render_site_panel() -> None:
    st.markdown('### Criar planilha pelo site')
    st.caption('Informe os links. O sistema usa os modelos do Bling para buscar só as colunas necessárias.')

    config_for_site_operation('cadastro')
    _, df_modelo_cadastro, df_modelo_estoque, df_modelo, requested_columns = _render_site_models_step()
    raw_urls = _render_urls_input()

    st.markdown('#### 3. Criar planilha')
    if st.button('Criar planilha', use_container_width=True):
        _run_site_capture(raw_urls, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo)

    df_site_bruto = st.session_state.get('df_site_bruto')
    if isinstance(df_site_bruto, pd.DataFrame) and not df_site_bruto.empty:
        render_generated_site_actions(df_site_bruto, raw_urls, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo)
