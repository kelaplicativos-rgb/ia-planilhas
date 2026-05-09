from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.flows.site_operation_router import config_for_site_operation, run_site_engine
from bling_app_zero.ui.home_shared import load_site_pipeline, show_contract
from bling_app_zero.ui.site_models import (
    choose_site_cadastro_model_df,
    choose_site_estoque_model_df,
    choose_site_model_df,
    has_home_site_model_for_operation,
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


def _current_site_operation() -> str:
    for key in ('tipo_operacao_site', 'operacao_final', 'tipo_operacao_final'):
        value = str(st.session_state.get(key) or '').strip().lower()
        if value in {'cadastro', 'estoque'}:
            return value
    flow = str(_query_param('flow') or _query_param('operacao') or '').strip().lower()
    if flow in {'estoque', 'estoque_site', 'stock', 'stock_site', 'atualizacao_estoque', 'atualização de estoque'}:
        return 'estoque'
    return 'cadastro'


def _operation_label(operation: str) -> str:
    return 'estoque' if operation == 'estoque' else 'cadastro'


def _render_site_models_step(operation: str) -> tuple[object, pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None, list[str] | None]:
    has_home_model = has_home_site_model_for_operation(operation)
    if not has_home_model:
        st.markdown('#### 1. Modelo do Bling')
    upload = render_optional_site_model_upload(operation)
    df_modelo_cadastro = choose_site_cadastro_model_df(upload)
    df_modelo_estoque = choose_site_estoque_model_df(upload)
    df_modelo = choose_site_model_df(upload, operation)
    requested_columns = requested_columns_for_site_capture(operation, df_modelo_cadastro, df_modelo_estoque)

    if requested_columns:
        show_contract(requested_columns)
    else:
        st.info('Sem modelo da operação atual. A busca tentará capturar os campos principais e deixará vazios os não encontrados.')

    return upload, df_modelo_cadastro, df_modelo_estoque, df_modelo, requested_columns


def _render_urls_input(step_number: int) -> str:
    st.markdown(f'#### {step_number}. Links do fornecedor')
    return st.text_area(
        'Cole site, categoria ou produtos',
        value=_query_urls_default(),
        height=120,
        key='urls_site',
        placeholder='https://site.com.br/categoria\nhttps://site.com.br/produto-1',
        label_visibility='collapsed',
    )


def _run_site_capture(
    operation: str,
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
        operation=operation,
        pipeline=load_site_pipeline(),
        raw_urls=raw_urls,
        requested_columns=requested_columns,
        all_products=True,
        max_pages=ALL_PAGES_LIMIT,
        max_products=ALL_PRODUCTS_LIMIT,
        progress_callback=make_site_progress_callback(progress_bar, status_box),
    )
    save_site_source(df_site, raw_urls, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo, operation)
    st.session_state['df_site_bruto'] = df_site
    st.session_state['operation_site'] = operation
    st.session_state['tipo_operacao_site'] = operation
    st.session_state['operacao_final'] = operation
    st.session_state['origem_final'] = 'site'
    st.rerun()


def render_site_panel() -> None:
    operation = _current_site_operation()
    label = _operation_label(operation)

    st.markdown(f'### Criar planilha de {label} pelo site')
    st.caption('Informe os links. O sistema usa somente o modelo da operação escolhida para buscar as colunas necessárias.')

    config_for_site_operation(operation)
    _, df_modelo_cadastro, df_modelo_estoque, df_modelo, requested_columns = _render_site_models_step(operation)

    url_step_number = 1 if has_home_site_model_for_operation(operation) else 2
    raw_urls = _render_urls_input(url_step_number)

    create_step_number = url_step_number + 1
    st.markdown(f'#### {create_step_number}. Criar planilha')
    button_label = 'Criar planilha de estoque' if operation == 'estoque' else 'Criar planilha de cadastro'
    if st.button(button_label, use_container_width=True):
        _run_site_capture(operation, raw_urls, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo)

    df_site_bruto = st.session_state.get('df_site_bruto')
    if isinstance(df_site_bruto, pd.DataFrame) and not df_site_bruto.empty:
        render_generated_site_actions(
            df_site_bruto,
            raw_urls,
            requested_columns,
            df_modelo_cadastro,
            df_modelo_estoque,
            df_modelo,
            operation,
        )
