from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.flows.site_as_source import set_site_source_as_planilha
from bling_app_zero.flows.site_operation_router import (
    config_for_site_operation,
    normalize_site_operation,
    run_site_engine,
)
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
    return normalize_site_operation(default_operation)


def _go_to_main_operation(operation: str) -> None:
    operation = normalize_site_operation(operation)
    try:
        st.query_params['flow'] = operation
    except Exception:
        pass
    st.session_state['tipo_operacao'] = operation
    st.session_state['home_slim_flow_step'] = 'estoque' if operation == 'estoque' else 'planilha'
    st.session_state['home_slim_active_panel'] = 'estoque' if operation == 'estoque' else 'planilha'


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
        operation=normalize_site_operation(operation),
        raw_urls=raw_urls,
        requested_columns=requested_columns,
        cadastro_model_df=df_modelo_cadastro,
        estoque_model_df=df_modelo_estoque,
        operation_model_df=df_modelo,
    )


def _source_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.fillna('').to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')


def _render_generated_origin_actions(
    df_site: pd.DataFrame,
    operation: str,
    raw_urls: str,
    requested_columns: list[str] | None,
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
    df_modelo: pd.DataFrame | None,
) -> None:
    if not isinstance(df_site, pd.DataFrame) or df_site.empty:
        return

    config = config_for_site_operation(operation)
    preview_df('Origem gerada', df_site)
    st.download_button(
        'Baixar origem',
        data=_source_csv_bytes(df_site),
        file_name=config.output_filename,
        mime='text/csv; charset=utf-8',
        use_container_width=True,
        key=f'download_origem_site_{config.operation}_{len(df_site)}_{len(df_site.columns)}',
    )

    if st.button('Usar origem', use_container_width=True, key='continuar_fluxo_planilha_site'):
        _save_site_source(
            df_site=df_site,
            operation=config.operation,
            raw_urls=raw_urls,
            requested_columns=requested_columns,
            df_modelo_cadastro=df_modelo_cadastro,
            df_modelo_estoque=df_modelo_estoque,
            df_modelo=df_modelo,
        )
        _go_to_main_operation(config.operation)
        st.rerun()


def render_site_panel() -> None:
    st.markdown('### Scraper')

    default_operation = _operation_from_query('cadastro')
    operation_options = ['Cadastro', 'Estoque']
    default_index = 0 if default_operation == 'cadastro' else 1
    modo = st.radio(
        'Destino',
        operation_options,
        index=default_index,
        horizontal=True,
        key='site_operation_radio',
    )
    operation = 'cadastro' if modo == 'Cadastro' else 'estoque'
    config = config_for_site_operation(operation)

    upload = render_model_upload_box(
        title='Modelo',
        operation=config.operation,
        key='model_upload_site',
        required_model=config.required_model,
    )

    df_modelo_cadastro = _choose_site_cadastro_model_df(upload)
    df_modelo_estoque = _choose_site_estoque_model_df(upload)
    df_modelo = _choose_site_model_df(upload, config.operation)

    requested_columns = _requested_columns_for_site_capture(
        operation=config.operation,
        df_modelo_cadastro=df_modelo_cadastro,
        df_modelo_estoque=df_modelo_estoque,
        df_modelo_operacao=df_modelo,
    )

    if requested_columns:
        if config.operation == 'estoque' and isinstance(df_modelo, pd.DataFrame):
            requested_columns_from_model = load_requested_columns_from_model()
            requested_columns = requested_columns_from_model(df_modelo)
        show_contract(requested_columns)
    elif config.operation == 'estoque':
        st.warning('Anexe o modelo.')

    raw_urls = st.text_area(
        'Links',
        value=_query_urls_default(),
        height=120,
        key='urls_site',
        placeholder='https://site.com.br/categoria\nhttps://site.com.br/produto-1',
    )

    all_products = st.checkbox('Varrer todos', value=True)
    with st.expander('Limites', expanded=False):
        col_limit_a, col_limit_b = st.columns(2)
        max_pages = int(col_limit_a.number_input('Páginas', min_value=10, max_value=1000, value=config.default_max_pages, step=20))
        max_products = int(col_limit_b.number_input('Produtos', min_value=10, max_value=5000, value=config.default_max_products, step=50))

    if config.required_model and not isinstance(df_modelo, pd.DataFrame):
        can_run = False
    else:
        can_run = True

    if st.button('Gerar origem', use_container_width=True, disabled=not can_run):
        run_site_pipeline = load_site_pipeline()
        with st.spinner('Buscando...'):
            df_site = run_site_engine(
                operation=config.operation,
                pipeline=run_site_pipeline,
                raw_urls=raw_urls,
                requested_columns=requested_columns,
                all_products=all_products,
                max_pages=max_pages,
                max_products=max_products,
            )
        _save_site_source(
            df_site=df_site,
            operation=config.operation,
            raw_urls=raw_urls,
            requested_columns=requested_columns,
            df_modelo_cadastro=df_modelo_cadastro,
            df_modelo_estoque=df_modelo_estoque,
            df_modelo=df_modelo,
        )
        st.session_state['df_site_bruto'] = df_site
        st.session_state['operation_site'] = config.operation
        st.success('Origem gerada.')

    df_site_bruto = st.session_state.get('df_site_bruto')
    operation_state = str(st.session_state.get('operation_site') or config.operation)
    if isinstance(df_site_bruto, pd.DataFrame) and not df_site_bruto.empty:
        _render_generated_origin_actions(
            df_site=df_site_bruto,
            operation=operation_state,
            raw_urls=raw_urls,
            requested_columns=requested_columns,
            df_modelo_cadastro=df_modelo_cadastro,
            df_modelo_estoque=df_modelo_estoque,
            df_modelo=df_modelo,
        )
