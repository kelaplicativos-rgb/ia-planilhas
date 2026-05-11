from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.flows.site_operation_router import run_site_engine
from bling_app_zero.ui.home_shared import load_site_pipeline, show_contract
from bling_app_zero.ui.site_models import (
    choose_site_estoque_model_df,
    choose_site_model_df,
    render_optional_site_model_upload,
    requested_columns_for_site_capture,
)
from bling_app_zero.ui.site_outputs import render_site_source_summary, save_site_source
from bling_app_zero.ui.site_progress import make_site_progress_callback, reset_site_progress

ALL_PAGES_LIMIT = 1_000_000
ALL_PRODUCTS_LIMIT = 1_000_000
OPERATION = 'estoque'
STOCK_SITE_DF_KEY = 'df_site_bruto_estoque'


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


def _has_columns(columns: list[str] | None) -> bool:
    return bool([str(column).strip() for column in (columns or [])])


def _get_stock_site_df() -> pd.DataFrame | None:
    df_current = st.session_state.get(STOCK_SITE_DF_KEY)
    if isinstance(df_current, pd.DataFrame):
        return df_current

    df_legacy = st.session_state.get('df_site_bruto')
    legacy_operation = str(
        st.session_state.get('operation_site')
        or st.session_state.get('tipo_operacao_site')
        or ''
    ).strip().lower()
    if legacy_operation == OPERATION and isinstance(df_legacy, pd.DataFrame):
        return df_legacy
    return None


def _store_stock_site_df(df_site: pd.DataFrame) -> None:
    clean_df = df_site.copy().fillna('') if isinstance(df_site, pd.DataFrame) else pd.DataFrame()
    st.session_state[STOCK_SITE_DF_KEY] = clean_df
    st.session_state['df_site_bruto'] = clean_df
    st.session_state.pop('df_site_bruto_cadastro', None)
    st.session_state['operation_site'] = OPERATION
    st.session_state['tipo_operacao_site'] = OPERATION
    st.session_state['operacao_final'] = OPERATION
    st.session_state['tipo_operacao_final'] = OPERATION
    st.session_state['origem_final'] = 'site'
    st.session_state['home_slim_flow_operation'] = OPERATION
    st.session_state['home_slim_flow_origin'] = 'site'


def _render_stock_model_contract() -> tuple[pd.DataFrame | None, list[str] | None]:
    upload = render_optional_site_model_upload(OPERATION)
    df_modelo_estoque = choose_site_estoque_model_df(upload)
    df_modelo = choose_site_model_df(upload, OPERATION)
    requested_columns = requested_columns_for_site_capture(
        OPERATION,
        df_modelo_cadastro=None,
        df_modelo_estoque=df_modelo_estoque,
    )

    if requested_columns:
        with st.expander('Campos que serão buscados', expanded=False):
            show_contract(requested_columns)
        st.caption('A busca de estoque por site vai tentar preencher somente as colunas acima. O que não for encontrado fica vazio.')
    else:
        st.error('Para estoque por site, carregue o modelo de estoque do Bling. A busca só será feita nas colunas desse modelo.')

    return df_modelo, requested_columns


def _render_urls_input() -> str:
    return st.text_area(
        'Links para buscar estoque',
        value=_query_urls_default(),
        height=120,
        key='urls_site_estoque_independente',
        placeholder='https://site.com.br/categoria\nhttps://site.com.br/produto-1',
        help='Cole links de categoria, busca ou produto. Este painel pertence somente ao fluxo de atualização de estoque.',
    )


def _run_stock_site_capture(
    raw_urls: str,
    requested_columns: list[str] | None,
    df_modelo_estoque: pd.DataFrame | None,
) -> None:
    if not _has_columns(requested_columns):
        st.error('Busca bloqueada: o modelo de estoque precisa definir exatamente quais colunas serão preenchidas.')
        return

    reset_site_progress()
    progress_bar = st.progress(0, text='Buscando dados de estoque no site...')
    status_box = st.empty()
    df_site = run_site_engine(
        operation=OPERATION,
        pipeline=load_site_pipeline(),
        raw_urls=raw_urls,
        requested_columns=requested_columns,
        all_products=True,
        max_pages=ALL_PAGES_LIMIT,
        max_products=ALL_PRODUCTS_LIMIT,
        progress_callback=make_site_progress_callback(progress_bar, status_box),
    )
    save_site_source(
        df_site=df_site,
        raw_urls=raw_urls,
        requested_columns=requested_columns,
        df_modelo_cadastro=None,
        df_modelo_estoque=df_modelo_estoque,
        df_modelo=df_modelo_estoque,
        operation=OPERATION,
    )
    _store_stock_site_df(df_site)
    st.rerun()


def render_estoque_site_panel() -> None:
    st.markdown(
        """
        <section class="bling-flow-card bling-inline-card">
            <div class="bling-flow-card-kicker">Entrada de estoque por site</div>
            <h2 class="bling-flow-card-title">Motor independente de estoque</h2>
            <p class="bling-flow-card-text">Este painel não usa a busca de cadastro. Ele lê o modelo de estoque e procura somente os campos pedidos nele.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.info('Motor ativo: ESTOQUE POR SITE independente. Cadastro de produtos não entra neste fluxo.')

    df_modelo_estoque, requested_columns = _render_stock_model_contract()
    raw_urls = _render_urls_input()

    button_disabled = not _has_columns(requested_columns)
    if button_disabled:
        st.caption('O botão será liberado quando o modelo de estoque estiver carregado.')

    if st.button(
        'Buscar somente estoque no site',
        use_container_width=True,
        disabled=button_disabled,
        key='buscar_site_estoque_independente',
    ):
        _run_stock_site_capture(raw_urls, requested_columns, df_modelo_estoque)

    df_site_bruto = _get_stock_site_df()
    if isinstance(df_site_bruto, pd.DataFrame) and not df_site_bruto.empty:
        render_site_source_summary(df_site_bruto, OPERATION, show_history=False)
        st.success('Origem de estoque por site pronta. Continue para gerar o preview de estoque.')


__all__ = ['render_estoque_site_panel']
