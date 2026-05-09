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


def _has_columns(columns: list[str] | None) -> bool:
    return bool([str(column).strip() for column in (columns or [])])


def _render_site_models_inline(operation: str) -> tuple[object, pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None, list[str] | None]:
    upload = render_optional_site_model_upload(operation)
    df_modelo_cadastro = choose_site_cadastro_model_df(upload)
    df_modelo_estoque = choose_site_estoque_model_df(upload)
    df_modelo = choose_site_model_df(upload, operation)
    requested_columns = requested_columns_for_site_capture(operation, df_modelo_cadastro, df_modelo_estoque)

    if requested_columns:
        show_contract(requested_columns)
    elif operation == 'estoque':
        st.error('Para estoque por site, envie primeiro o modelo de estoque do Bling. A busca só será feita nas colunas desse modelo.')
    else:
        st.info('Sem modelo desta operação. Vou capturar os campos principais e deixar vazio o que não encontrar.')

    return upload, df_modelo_cadastro, df_modelo_estoque, df_modelo, requested_columns


def _render_urls_input() -> str:
    return st.text_area(
        'Links do fornecedor',
        value=_query_urls_default(),
        height=120,
        key='urls_site',
        placeholder='https://site.com.br/categoria\nhttps://site.com.br/produto-1',
        help='Cole um ou mais links: categoria, busca ou produtos individuais.',
    )


def _run_site_capture(
    operation: str,
    raw_urls: str,
    requested_columns: list[str] | None,
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
    df_modelo: pd.DataFrame | None,
) -> None:
    if operation == 'estoque' and not _has_columns(requested_columns):
        st.error('Busca bloqueada: carregue o modelo de estoque para definir exatamente quais colunas serão preenchidas.')
        return

    reset_site_progress()
    progress_bar = st.progress(0, text='Buscando produtos no site...')
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
    _ = _operation_label(operation)

    st.markdown(
        """
        <section class="bling-flow-card bling-inline-card">
            <div class="bling-flow-card-kicker">Entrada por site</div>
            <h2 class="bling-flow-card-title">Cole os links do fornecedor</h2>
            <p class="bling-flow-card-text">A captura acontece aqui mesmo. Depois da busca, o mapeamento, preview e download aparecem logo abaixo.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    config_for_site_operation(operation)
    _, df_modelo_cadastro, df_modelo_estoque, df_modelo, requested_columns = _render_site_models_inline(operation)
    raw_urls = _render_urls_input()

    button_label = 'Buscar no site e gerar origem de estoque' if operation == 'estoque' else 'Buscar no site e gerar origem de cadastro'
    button_disabled = operation == 'estoque' and not _has_columns(requested_columns)
    if button_disabled:
        st.caption('O botão será liberado quando o modelo de estoque estiver carregado.')

    if st.button(button_label, use_container_width=True, disabled=button_disabled):
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
