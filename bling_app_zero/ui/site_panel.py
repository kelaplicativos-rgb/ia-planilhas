from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.flows.site_as_source import set_site_source_as_planilha
from bling_app_zero.flows.site_operation_router import (
    config_for_site_operation,
    run_site_engine,
)
from bling_app_zero.ui.home_shared import (
    load_site_pipeline,
    preview_df,
    show_contract,
)
from bling_app_zero.ui.model_upload import render_model_upload_box

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


def _choose_site_model_df(upload) -> pd.DataFrame | None:
    if isinstance(upload.cadastro_model_df, pd.DataFrame):
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
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
) -> list[str] | None:
    cadastro_columns = _columns_from_df(df_modelo_cadastro)
    estoque_columns = _columns_from_df(df_modelo_estoque)
    merged = _unique_columns(cadastro_columns + estoque_columns)
    return merged or None


def _go_to_main_flow() -> None:
    try:
        st.query_params['flow'] = 'planilha'
    except Exception:
        pass
    st.session_state['tipo_operacao'] = 'cadastro'
    st.session_state['home_slim_flow_step'] = 'planilha'
    st.session_state['home_slim_active_panel'] = 'planilha'


def _save_site_source(
    df_site: pd.DataFrame,
    raw_urls: str,
    requested_columns: list[str] | None,
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
    df_modelo: pd.DataFrame | None,
) -> None:
    set_site_source_as_planilha(
        df=df_site,
        operation='cadastro',
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
    raw_urls: str,
    requested_columns: list[str] | None,
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
    df_modelo: pd.DataFrame | None,
) -> None:
    if not isinstance(df_site, pd.DataFrame) or df_site.empty:
        return

    config = config_for_site_operation('cadastro')
    preview_df('Origem gerada', df_site)
    st.download_button(
        'Baixar origem',
        data=_source_csv_bytes(df_site),
        file_name=config.output_filename,
        mime='text/csv; charset=utf-8',
        use_container_width=True,
        key=f'download_origem_site_unica_{len(df_site)}_{len(df_site.columns)}',
    )

    if st.button('Usar origem', use_container_width=True, key='continuar_fluxo_planilha_site'):
        _save_site_source(
            df_site=df_site,
            raw_urls=raw_urls,
            requested_columns=requested_columns,
            df_modelo_cadastro=df_modelo_cadastro,
            df_modelo_estoque=df_modelo_estoque,
            df_modelo=df_modelo,
        )
        _go_to_main_flow()
        st.rerun()


def render_site_panel() -> None:
    st.markdown('### Scraper')

    config_for_site_operation('cadastro')
    upload = render_model_upload_box(
        title='Modelo',
        operation='cadastro',
        key='model_upload_site',
        required_model=False,
    )

    df_modelo_cadastro = _choose_site_cadastro_model_df(upload)
    df_modelo_estoque = _choose_site_estoque_model_df(upload)
    df_modelo = _choose_site_model_df(upload)

    requested_columns = _requested_columns_for_site_capture(
        df_modelo_cadastro=df_modelo_cadastro,
        df_modelo_estoque=df_modelo_estoque,
    )

    if requested_columns:
        show_contract(requested_columns)

    raw_urls = st.text_area(
        'Links',
        value=_query_urls_default(),
        height=120,
        key='urls_site',
        placeholder='https://site.com.br/categoria\nhttps://site.com.br/produto-1',
    )

    if st.button('Gerar origem', use_container_width=True):
        run_site_pipeline = load_site_pipeline()
        with st.spinner('Buscando ao vivo...'):
            df_site = run_site_engine(
                operation='cadastro',
                pipeline=run_site_pipeline,
                raw_urls=raw_urls,
                requested_columns=requested_columns,
                all_products=True,
                max_pages=ALL_PAGES_LIMIT,
                max_products=ALL_PRODUCTS_LIMIT,
            )
        _save_site_source(
            df_site=df_site,
            raw_urls=raw_urls,
            requested_columns=requested_columns,
            df_modelo_cadastro=df_modelo_cadastro,
            df_modelo_estoque=df_modelo_estoque,
            df_modelo=df_modelo,
        )
        st.session_state['df_site_bruto'] = df_site
        st.session_state['operation_site'] = 'cadastro'
        st.success('Origem gerada.')

    df_site_bruto = st.session_state.get('df_site_bruto')
    if isinstance(df_site_bruto, pd.DataFrame) and not df_site_bruto.empty:
        _render_generated_origin_actions(
            df_site=df_site_bruto,
            raw_urls=raw_urls,
            requested_columns=requested_columns,
            df_modelo_cadastro=df_modelo_cadastro,
            df_modelo_estoque=df_modelo_estoque,
            df_modelo=df_modelo,
        )
