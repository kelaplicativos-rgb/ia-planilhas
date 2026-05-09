from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.estoque_sources import file_name, safe_read_source, source_files_from_upload
from bling_app_zero.ui.home_shared import download_final, load_estoque_pipeline, preview_df, show_mapping


def build_stock_outputs_from_dataframe(
    df_origem: pd.DataFrame,
    df_modelo: pd.DataFrame | None,
    deposito: str,
    name: str = 'Origem por site',
) -> None:
    run_estoque_pipeline = load_estoque_pipeline()
    df_final, mapping = run_estoque_pipeline(df_origem, df_modelo, deposito=deposito)
    result = {'index': 1, 'name': name, 'df_final': df_final, 'mapping': mapping}
    st.session_state['estoque_multi_outputs'] = [result]
    st.session_state['df_final_estoque'] = df_final
    st.session_state['mapping_estoque'] = mapping


def build_stock_outputs(upload, df_modelo: pd.DataFrame | None, deposito: str) -> None:
    source_files = source_files_from_upload(upload)
    if not source_files:
        st.warning('Anexei os arquivos, mas ainda não consegui identificar uma origem válida para o estoque.')
        return

    run_estoque_pipeline = load_estoque_pipeline()
    results: list[dict[str, object]] = []

    for index, file in enumerate(source_files, start=1):
        df_origem = safe_read_source(file)
        if not isinstance(df_origem, pd.DataFrame) or df_origem.empty:
            continue

        df_final, mapping = run_estoque_pipeline(df_origem, df_modelo, deposito=deposito)
        results.append(
            {
                'index': index,
                'name': file_name(file),
                'df_final': df_final,
                'mapping': mapping,
            }
        )

    st.session_state['estoque_multi_outputs'] = results

    if results:
        st.session_state['df_final_estoque'] = results[0]['df_final']
        st.session_state['mapping_estoque'] = results[0]['mapping']
    else:
        st.session_state.pop('df_final_estoque', None)
        st.session_state.pop('mapping_estoque', None)


def render_stock_outputs() -> None:
    results = st.session_state.get('estoque_multi_outputs', [])
    if not results:
        return

    st.markdown('#### CSV final de estoque')
    st.caption('Confira o resultado antes de baixar. Cada origem gera um CSV separado.')

    for result in results:
        index = result.get('index')
        name = str(result.get('name') or f'origem_{index}')
        df_final = result.get('df_final')
        mapping = result.get('mapping', {})

        with st.expander(f'CSV {index}: {name}', expanded=index == 1):
            if isinstance(mapping, dict):
                show_mapping(mapping)
            if isinstance(df_final, pd.DataFrame):
                preview_df('Preview final do estoque', df_final)
                download_final(df_final, 'estoque', f'estoque_{index}_{name}_{len(df_final)}_{len(df_final.columns)}')
            else:
                st.warning('Não foi possível montar o CSV desta origem.')
