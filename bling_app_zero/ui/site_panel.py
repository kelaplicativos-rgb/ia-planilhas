from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.flows.site_as_source import set_site_source_as_planilha
from bling_app_zero.ui.home_shared import (
    load_requested_columns_from_model,
    load_site_pipeline,
    preview_df,
    show_contract,
)
from bling_app_zero.ui.model_upload import render_model_upload_box


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


def _unique_columns(columns: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for column in columns:
        text = str(column or '').strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _columns_from_df(df: pd.DataFrame | None) -> list[str]:
    if isinstance(df, pd.DataFrame) and len(df.columns):
        return [str(c) for c in df.columns]
    return []


def _choose_site_model_df(upload, operation: str) -> pd.DataFrame | None:
    if operation == 'estoque' and isinstance(upload.estoque_model_df, pd.DataFrame):
        return upload.estoque_model_df
    if operation == 'cadastro' and isinstance(upload.cadastro_model_df, pd.DataFrame):
        return upload.cadastro_model_df
    if isinstance(upload.model_df, pd.DataFrame):
        return upload.model_df
    return None


def _choose_site_cadastro_model_df(upload) -> pd.DataFrame | None:
    if isinstance(upload.cadastro_model_df, pd.DataFrame):
        return upload.cadastro_model_df
    if isinstance(upload.model_df, pd.DataFrame):
        return upload.model_df
    return None


def _choose_site_estoque_model_df(upload) -> pd.DataFrame | None:
    if isinstance(upload.estoque_model_df, pd.DataFrame):
        return upload.estoque_model_df
    return None


def _requested_columns_for_site_capture(
    operation: str,
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
    df_modelo_operacao: pd.DataFrame | None,
) -> list[str] | None:
    if operation == 'cadastro':
        cadastro_columns = _columns_from_df(df_modelo_cadastro)
        estoque_columns = _columns_from_df(df_modelo_estoque)
        merged = _unique_columns(cadastro_columns + estoque_columns)
        return merged or None
    return _columns_from_df(df_modelo_operacao) or None


def _operation_from_query(default_operation: str = 'cadastro') -> str:
    flow = _query_param('flow').lower().strip()
    operation = _query_param('operation').lower().strip()
    if flow == 'estoque_site' or operation == 'estoque':
        return 'estoque'
    if flow == 'cadastro_site' or operation == 'cadastro':
        return 'cadastro'
    return default_operation


def _go_to_main_operation(operation: str) -> None:
    try:
        st.query_params['flow'] = operation
    except Exception:
        pass
    st.session_state['tipo_operacao'] = operation


def _save_site_source(
    df_site: pd.DataFrame,
    operation: str,
    raw_urls: str,
    requested_columns: list[str] | None,
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
    df_modelo: pd.DataFrame | None,
) -> None:
    set_site_source_as_planilha(
        df=df_site,
        operation=operation,
        raw_urls=raw_urls,
        requested_columns=requested_columns,
        cadastro_model_df=df_modelo_cadastro,
        estoque_model_df=df_modelo_estoque,
        operation_model_df=df_modelo,
    )


def render_site_panel() -> None:
    st.info('A busca por site agora prepara uma ORIGEM DE DADOS. Depois da captura, ela segue o mesmo fluxo da origem por planilha.')
    st.caption('Tecnologia ativa: IA prioritária + complemento Flash/XML/Sitemaps para saldo real quando o contrato pedir estoque.')

    default_operation = _operation_from_query('cadastro')
    operation_options = ['Cadastro de Produtos', 'Atualização de Estoque']
    default_index = 0 if default_operation == 'cadastro' else 1
    modo = st.radio('Operação que receberá esta origem site', operation_options, index=default_index, horizontal=True)
    operation = 'cadastro' if modo == 'Cadastro de Produtos' else 'estoque'

    upload = render_model_upload_box(
        title='📎 Planilhas modelo Bling',
        operation=operation,
        key='model_upload_site',
        required_model=operation == 'estoque',
    )

    df_modelo_cadastro = _choose_site_cadastro_model_df(upload)
    df_modelo_estoque = _choose_site_estoque_model_df(upload)
    df_modelo = _choose_site_model_df(upload, operation)

    requested_columns = _requested_columns_for_site_capture(
        operation=operation,
        df_modelo_cadastro=df_modelo_cadastro,
        df_modelo_estoque=df_modelo_estoque,
        df_modelo_operacao=df_modelo,
    )

    if requested_columns:
        if operation == 'estoque' and isinstance(df_modelo, pd.DataFrame):
            requested_columns_from_model = load_requested_columns_from_model()
            requested_columns = requested_columns_from_model(df_modelo)
        show_contract(requested_columns)
    else:
        st.warning('Sem modelo anexado, a IA usará colunas padrão da operação. Para contrato rígido, anexe o modelo do Bling antes de buscar.')

    raw_urls = st.text_area(
        'URL inicial, categoria, home ou links de produtos',
        value=_query_urls_default(),
        height=180,
        key='urls_site',
    )

    all_products = st.checkbox('Varrer site/categoria e buscar todos os produtos encontrados', value=True)
    col_limit_a, col_limit_b = st.columns(2)
    max_pages = int(col_limit_a.number_input('Limite de páginas/feeds analisados', min_value=10, max_value=3000, value=250, step=50))
    max_products = int(col_limit_b.number_input('Limite de produtos capturados', min_value=10, max_value=10000, value=1000, step=100))

    if st.button('Capturar origem por site e continuar no fluxo da planilha', use_container_width=True):
        run_site_pipeline = load_site_pipeline()
        with st.spinner('Capturando origem por site com IA e complementando saldo real via XML/Sitemaps quando solicitado...'):
            df_site = run_site_pipeline(
                raw_urls,
                requested_columns=requested_columns,
                all_products=all_products,
                max_pages=max_pages,
                max_products=max_products,
                operation=operation,
            )
        _save_site_source(
            df_site=df_site,
            operation=operation,
            raw_urls=raw_urls,
            requested_columns=requested_columns,
            df_modelo_cadastro=df_modelo_cadastro,
            df_modelo_estoque=df_modelo_estoque,
            df_modelo=df_modelo,
        )
        st.session_state['df_site_bruto'] = df_site
        st.session_state['operation_site'] = operation
        st.success('Origem por site capturada. Ela agora será usada no mesmo fluxo da origem por planilha.')
        preview_df('Origem por site capturada', df_site)
        _go_to_main_operation(operation)
        st.rerun()

    df_site_bruto = st.session_state.get('df_site_bruto')
    if isinstance(df_site_bruto, pd.DataFrame) and not df_site_bruto.empty:
        preview_df('Última origem por site capturada', df_site_bruto)
        if st.button('Usar esta origem no fluxo da planilha', use_container_width=True, key='usar_ultima_origem_site'):
            _save_site_source(
                df_site=df_site_bruto,
                operation=operation,
                raw_urls=raw_urls,
                requested_columns=requested_columns,
                df_modelo_cadastro=df_modelo_cadastro,
                df_modelo_estoque=df_modelo_estoque,
                df_modelo=df_modelo,
            )
            _go_to_main_operation(operation)
            st.rerun()
