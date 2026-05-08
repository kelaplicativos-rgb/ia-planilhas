from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.flows.site_as_source import get_site_source_for_operation
from bling_app_zero.ui.home_shared import (
    download_final,
    load_estoque_pipeline,
    preview_df,
    read_upload_fast,
    show_contract,
    show_mapping,
)
from bling_app_zero.ui.smart_upload import render_smart_upload_box


def _file_name(file: Any) -> str:
    return str(getattr(file, 'name', 'arquivo')).strip()


def _safe_read_source(file: Any) -> pd.DataFrame | None:
    try:
        return read_upload_fast(file)
    except Exception as exc:
        st.warning(f'Não consegui ler {_file_name(file)}: {exc}')
        return None


def _source_files_from_upload(upload) -> list[Any]:
    attachments = list(upload.attachments or [])
    if not attachments:
        return []

    sources: list[Any] = []
    for file in attachments:
        if upload.model_file is not None and file is upload.model_file:
            continue
        sources.append(file)

    if not sources and upload.source_file is not None:
        sources.append(upload.source_file)

    return sources


def _build_stock_outputs_from_dataframe(df_origem: pd.DataFrame, df_modelo: pd.DataFrame | None, deposito: str, name: str = 'Origem por site') -> None:
    run_estoque_pipeline = load_estoque_pipeline()
    df_final, mapping = run_estoque_pipeline(df_origem, df_modelo, deposito=deposito)
    result = {'index': 1, 'name': name, 'df_final': df_final, 'mapping': mapping}
    st.session_state['estoque_multi_outputs'] = [result]
    st.session_state['df_final_estoque'] = df_final
    st.session_state['mapping_estoque'] = mapping


def _build_stock_outputs(upload, df_modelo: pd.DataFrame | None, deposito: str) -> None:
    source_files = _source_files_from_upload(upload)
    if not source_files:
        st.warning('Anexei os arquivos, mas ainda não consegui identificar uma origem tabular válida para o estoque.')
        return

    run_estoque_pipeline = load_estoque_pipeline()
    results: list[dict[str, object]] = []

    for index, file in enumerate(source_files, start=1):
        df_origem = _safe_read_source(file)
        if not isinstance(df_origem, pd.DataFrame) or df_origem.empty:
            continue

        df_final, mapping = run_estoque_pipeline(df_origem, df_modelo, deposito=deposito)
        results.append(
            {
                'index': index,
                'name': _file_name(file),
                'df_final': df_final,
                'mapping': mapping,
            }
        )

    st.session_state['estoque_multi_outputs'] = results

    if results:
        st.session_state['df_final_estoque'] = results[0]['df_final']
        st.session_state['mapping_estoque'] = results[0]['mapping']


def _render_stock_outputs() -> None:
    results = st.session_state.get('estoque_multi_outputs', [])
    if not results:
        return

    st.markdown('#### Downloads finais de estoque')
    st.caption('Cada origem gera uma planilha final separada.')

    for result in results:
        index = result.get('index')
        name = str(result.get('name') or f'origem_{index}')
        df_final = result.get('df_final')
        mapping = result.get('mapping', {})

        with st.expander(f'Planilha final {index}: {name}', expanded=index == 1):
            if isinstance(mapping, dict):
                show_mapping(mapping)
            if isinstance(df_final, pd.DataFrame):
                preview_df('Preview final do estoque', df_final)
                download_final(df_final, 'estoque', f'estoque_{index}')


def render_estoque_panel() -> None:
    st.warning('Motor independente de ESTOQUE será carregado somente quando gerar.')
    st.caption('Este fluxo usa somente as colunas pedidas pelo modelo de estoque. Se não encontrar um campo, ele fica vazio.')

    upload = render_smart_upload_box(
        title='📎 Anexos do estoque',
        operation='estoque',
        key='smart_upload_estoque',
        allow_model=True,
        required_model=True,
        accepted_types=['xlsx', 'xls', 'csv'],
    )

    df_modelo = upload.model_df
    df_origem_site = get_site_source_for_operation('estoque')

    if isinstance(df_modelo, pd.DataFrame):
        show_contract([str(c) for c in df_modelo.columns])

    deposito = st.text_input('Nome do depósito', value='Não definido')

    if isinstance(df_origem_site, pd.DataFrame):
        st.success('Origem por site carregada como origem de dados. A partir daqui o fluxo é o mesmo da planilha.')
        preview_df('Origem por site para atualização de estoque', df_origem_site)
        if st.button('Gerar atualização de estoque', use_container_width=True):
            _build_stock_outputs_from_dataframe(df_origem_site, df_modelo, deposito, name='Origem por site')
    elif upload.attachments:
        source_files = _source_files_from_upload(upload)
        if len(source_files) > 1:
            st.info(f'{len(source_files)} origens de estoque detectadas. O sistema vai gerar um CSV final para cada uma.')

        if st.button('Gerar atualização de estoque', use_container_width=True):
            _build_stock_outputs(upload, df_modelo, deposito)
    else:
        st.info('Anexe a origem e o modelo de estoque para gerar o CSV final.')

    _render_stock_outputs()
