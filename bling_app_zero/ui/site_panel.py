from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from bling_app_zero.flows.site_as_source import set_site_source_as_planilha
from bling_app_zero.flows.site_operation_router import (
    config_for_site_operation,
    run_site_engine,
)
from bling_app_zero.ui.home_models import get_home_cadastro_model, get_home_estoque_model, save_home_models
from bling_app_zero.ui.home_shared import (
    load_site_pipeline,
    preview_df,
    show_contract,
)
from bling_app_zero.ui.model_upload import render_model_upload_box

ALL_PAGES_LIMIT = 1_000_000
ALL_PRODUCTS_LIMIT = 1_000_000
PROGRESS_LOG_KEY = 'site_progress_log'
PROGRESS_LAST_KEY = 'site_progress_last'


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
    home_model = get_home_cadastro_model()
    if isinstance(home_model, pd.DataFrame):
        return home_model
    if isinstance(upload.cadastro_model_df, pd.DataFrame):
        return upload.cadastro_model_df
    if isinstance(upload.model_df, pd.DataFrame):
        return upload.model_df
    return None


def _choose_site_cadastro_model_df(upload) -> pd.DataFrame | None:
    home_model = get_home_cadastro_model()
    if isinstance(home_model, pd.DataFrame):
        return home_model
    if isinstance(upload.cadastro_model_df, pd.DataFrame):
        return upload.cadastro_model_df
    if isinstance(upload.model_df, pd.DataFrame):
        return upload.model_df
    return None


def _choose_site_estoque_model_df(upload) -> pd.DataFrame | None:
    home_model = get_home_estoque_model()
    if isinstance(home_model, pd.DataFrame):
        return home_model
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
    save_home_models(df_modelo_cadastro, df_modelo_estoque)
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


def _reset_progress() -> None:
    st.session_state[PROGRESS_LOG_KEY] = []
    st.session_state[PROGRESS_LAST_KEY] = {}


def _append_progress(payload: dict) -> None:
    log = list(st.session_state.get(PROGRESS_LOG_KEY, []))
    payload = dict(payload or {})
    payload['time'] = time.strftime('%H:%M:%S')
    log.append(payload)
    st.session_state[PROGRESS_LOG_KEY] = log[-80:]
    st.session_state[PROGRESS_LAST_KEY] = payload


def _progress_rows(log: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for item in log:
        rows.append({
            'Hora': item.get('time', ''),
            'Etapa': item.get('stage', ''),
            'Mensagem': item.get('message', ''),
            'Links': item.get('urls_found', item.get('total', '')),
            'Processados': item.get('processed', ''),
            'Encontrados': item.get('found', ''),
            'Erros': item.get('errors', ''),
            'Tempo': item.get('total_seconds', item.get('discovery_seconds', '')),
        })
    return rows


def _render_sidebar_progress_details(payload: dict) -> None:
    log = st.session_state.get(PROGRESS_LOG_KEY) or []
    with st.sidebar:
        with st.expander('Detalhes da busca por site', expanded=False):
            st.caption(str(payload.get('stage') or 'Processando'))
            col_a, col_b = st.columns(2)
            col_a.metric('Links', int(payload.get('urls_found') or payload.get('total') or 0))
            col_b.metric('Processados', int(payload.get('processed') or 0))
            col_c, col_d = st.columns(2)
            col_c.metric('Encontrados', int(payload.get('found') or 0))
            col_d.metric('Erros', int(payload.get('errors') or 0))

            slow_links = payload.get('slow_links') or []
            if slow_links:
                st.markdown('##### Links lentos')
                for item in slow_links[-5:]:
                    st.caption(f"{item.get('seconds')}s · {item.get('url')}")

            if log:
                st.markdown('##### Relatório')
                st.dataframe(pd.DataFrame(_progress_rows(log)), use_container_width=True, height=260)


def _make_progress_callback(progress_bar, status_box):
    def callback(payload: dict) -> None:
        _append_progress(payload)
        progress = float(payload.get('progress') or 0.0)
        progress = max(0.0, min(1.0, progress))
        stage = str(payload.get('stage') or 'Processando')
        message = str(payload.get('message') or '')
        progress_bar.progress(progress, text=f'{stage} · {int(progress * 100)}%')
        status_box.info(message or stage)
        _render_sidebar_progress_details(payload)
    return callback


def _render_progress_history() -> None:
    log = st.session_state.get(PROGRESS_LOG_KEY) or []
    if not log:
        return
    with st.sidebar:
        with st.expander('Relatório da busca', expanded=False):
            st.dataframe(pd.DataFrame(_progress_rows(log)), use_container_width=True, height=280)


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
    st.success('Planilha criada e enviada para o fluxo de planilha.')
    _render_progress_history()
    with st.expander('Ver planilha criada', expanded=False):
        preview_df('Planilha criada', df_site)

    col_a, col_b = st.columns(2)
    with col_a:
        st.download_button(
            'Baixar planilha',
            data=_source_csv_bytes(df_site),
            file_name=config.output_filename,
            mime='text/csv; charset=utf-8',
            use_container_width=True,
            key=f'download_origem_site_unica_{len(df_site)}_{len(df_site.columns)}',
        )
    with col_b:
        if st.button('Continuar', use_container_width=True, key='continuar_fluxo_planilha_site'):
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


def _render_optional_model_upload() -> object:
    if get_home_cadastro_model() is not None or get_home_estoque_model() is not None:
        st.success('Modelos do Bling carregados na home.')
        st.caption('Para trocar os modelos, envie novos arquivos abaixo. O painel interno já mostra as colunas detectadas.')
        return render_model_upload_box(
            title='Trocar modelos',
            operation='cadastro',
            key='model_upload_site',
            required_model=False,
            caption='Use apenas se quiser trocar os modelos desta busca.',
        )
    return render_model_upload_box(
        title='Modelos para cadastro e estoque',
        operation='cadastro',
        key='model_upload_site',
        required_model=False,
        caption='Anexe os modelos do Bling para preencher as colunas certas.',
    )


def render_site_panel() -> None:
    st.markdown('### Criar planilha pelo site')
    st.caption('Informe os links. O sistema usa os modelos do Bling para buscar só as colunas necessárias.')

    config_for_site_operation('cadastro')

    st.markdown('#### 1. Modelos do Bling')
    upload = _render_optional_model_upload()

    df_modelo_cadastro = _choose_site_cadastro_model_df(upload)
    df_modelo_estoque = _choose_site_estoque_model_df(upload)
    df_modelo = _choose_site_model_df(upload)

    requested_columns = _requested_columns_for_site_capture(
        df_modelo_cadastro=df_modelo_cadastro,
        df_modelo_estoque=df_modelo_estoque,
    )

    if requested_columns:
        show_contract(requested_columns)

    st.markdown('#### 2. Links do fornecedor')
    raw_urls = st.text_area(
        'Cole site, categoria ou produtos',
        value=_query_urls_default(),
        height=120,
        key='urls_site',
        placeholder='https://site.com.br/categoria\nhttps://site.com.br/produto-1',
        label_visibility='collapsed',
    )

    st.markdown('#### 3. Criar planilha')
    if st.button('Criar planilha', use_container_width=True):
        _reset_progress()
        progress_bar = st.progress(0, text='Iniciando busca...')
        status_box = st.empty()
        callback = _make_progress_callback(progress_bar, status_box)

        run_site_pipeline = load_site_pipeline()
        df_site = run_site_engine(
            operation='cadastro',
            pipeline=run_site_pipeline,
            raw_urls=raw_urls,
            requested_columns=requested_columns,
            all_products=True,
            max_pages=ALL_PAGES_LIMIT,
            max_products=ALL_PRODUCTS_LIMIT,
            progress_callback=callback,
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
        st.rerun()

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
