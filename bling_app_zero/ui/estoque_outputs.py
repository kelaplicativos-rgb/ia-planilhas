from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.engines.estoque_engine import MissingEstoqueModelError
from bling_app_zero.ui.estoque_sources import file_name, safe_read_source, source_files_from_upload
from bling_app_zero.ui.home_shared import download_final, load_estoque_pipeline, preview_df, show_mapping
from bling_app_zero.ui.preview_ai_actions import render_preview_ai_actions


def _valid_model(df_modelo: pd.DataFrame | None) -> bool:
    return isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns) > 0


def _show_missing_model_warning() -> None:
    st.error('Envie o modelo de estoque do Bling antes de gerar o CSV. O sistema só preenche as colunas existentes nesse modelo.')


def _stock_results() -> list[dict[str, object]]:
    results = st.session_state.get('estoque_multi_outputs', [])
    return results if isinstance(results, list) else []


def _download_name(index: object, name: str, df_final: pd.DataFrame) -> str:
    safe_name = ''.join(ch if ch.isalnum() or ch in {'-', '_'} else '_' for ch in str(name or 'estoque'))[:60]
    return f'estoque_{index}_{safe_name}_{len(df_final)}_{len(df_final.columns)}'


def build_stock_outputs_from_dataframe(
    df_origem: pd.DataFrame,
    df_modelo: pd.DataFrame | None,
    deposito: str,
    name: str = 'Origem por site',
) -> None:
    if not _valid_model(df_modelo):
        _show_missing_model_warning()
        return

    run_estoque_pipeline = load_estoque_pipeline()
    try:
        df_final, mapping = run_estoque_pipeline(df_origem, df_modelo, deposito=deposito)
    except MissingEstoqueModelError:
        _show_missing_model_warning()
        return

    result = {'index': 1, 'name': name, 'df_final': df_final, 'mapping': mapping}
    st.session_state['estoque_multi_outputs'] = [result]
    st.session_state['df_final_estoque'] = df_final
    st.session_state['mapping_estoque'] = mapping


def build_stock_outputs(upload, df_modelo: pd.DataFrame | None, deposito: str) -> None:
    if not _valid_model(df_modelo):
        _show_missing_model_warning()
        return

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

        try:
            df_final, mapping = run_estoque_pipeline(df_origem, df_modelo, deposito=deposito)
        except MissingEstoqueModelError:
            _show_missing_model_warning()
            return

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


def render_stock_preview() -> None:
    results = _stock_results()
    if not results:
        st.warning('Nenhum preview de estoque foi gerado ainda.')
        return

    st.markdown('#### 📦 Preview final de ESTOQUE')
    st.caption('Confira os dados antes de baixar. O download fica na próxima etapa.')

    for result in results:
        index = result.get('index')
        name = str(result.get('name') or f'origem_{index}')
        df_final = result.get('df_final')
        mapping = result.get('mapping', {})

        with st.expander(f'📦 ESTOQUE · Preview {index}: {name}', expanded=index == 1):
            if isinstance(mapping, dict):
                show_mapping(mapping, operation='estoque')
            if isinstance(df_final, pd.DataFrame):
                preview_df('📦 ESTOQUE · Preview final', df_final)
                render_preview_ai_actions(df_final, 'estoque')
            else:
                st.warning('Não foi possível montar o preview desta origem.')


def render_stock_downloads() -> None:
    results = _stock_results()
    if not results:
        st.warning('Nenhum CSV de estoque foi gerado ainda.')
        return

    st.markdown('#### 📥 Download de ESTOQUE')
    st.caption('Baixe aqui somente o CSV final de atualização de estoque. Cada origem gera um CSV separado.')

    for result in results:
        index = result.get('index')
        name = str(result.get('name') or f'origem_{index}')
        df_final = result.get('df_final')
        if not isinstance(df_final, pd.DataFrame):
            st.warning(f'Não foi possível baixar a origem {index}: {name}.')
            continue
        st.markdown(f'**CSV {index}: {name}**')
        download_final(df_final, 'estoque', _download_name(index, name, df_final))


def render_stock_outputs() -> None:
    """Compatibilidade com telas antigas: preview + download juntos."""
    render_stock_preview()
    render_stock_downloads()
