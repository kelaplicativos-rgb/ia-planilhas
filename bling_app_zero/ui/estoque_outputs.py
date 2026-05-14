from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.engines.estoque_engine import MissingEstoqueModelError
from bling_app_zero.ui.estoque_sources import file_name, safe_read_source, source_files_from_upload
from bling_app_zero.ui.estoque_wizard_state import clear_estoque_outputs, set_stock_output
from bling_app_zero.ui.home_shared import download_final, load_estoque_pipeline, preview_df, show_mapping


def _valid_model(df_modelo: pd.DataFrame | None) -> bool:
    return isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns) > 0


def _show_missing_model_warning() -> None:
    clear_estoque_outputs()
    st.error('Envie o modelo de estoque do Bling antes de gerar o CSV. O sistema só preenche as colunas existentes nesse modelo.')


def _stock_results() -> list[dict[str, object]]:
    results = st.session_state.get('estoque_multi_outputs', [])
    return results if isinstance(results, list) else []


def _download_key(index: object, name: str, df_final: pd.DataFrame) -> str:
    safe_name = ''.join(ch if ch.isalnum() or ch in {'-', '_'} else '_' for ch in str(name or 'estoque'))[:60]
    return f'estoque_final_{index}_{safe_name}_{len(df_final)}_{len(df_final.columns)}'


def _final_preview_df(df_final: pd.DataFrame) -> pd.DataFrame:
    """Aplica no preview de estoque a mesma blindagem usada no CSV."""
    return sanitize_for_bling(df_final.copy().fillna(''), operation='estoque')


def _store_stock_results(results: list[dict[str, object]]) -> None:
    st.session_state['estoque_multi_outputs'] = results
    if not results:
        clear_estoque_outputs()
        return
    first = results[0]
    df_final = first.get('df_final')
    mapping = first.get('mapping')
    set_stock_output(
        df_final if isinstance(df_final, pd.DataFrame) else None,
        mapping if isinstance(mapping, dict) else {},
    )


def build_stock_outputs_from_dataframe(
    df_origem: pd.DataFrame,
    df_modelo: pd.DataFrame | None,
    deposito: str,
    name: str = 'Origem por site',
) -> None:
    if not _valid_model(df_modelo):
        _show_missing_model_warning()
        return
    if not isinstance(df_origem, pd.DataFrame) or df_origem.empty:
        clear_estoque_outputs()
        st.warning('Nenhuma origem válida de estoque foi encontrada para gerar o CSV.')
        return
    run_estoque_pipeline = load_estoque_pipeline()
    try:
        df_final, mapping = run_estoque_pipeline(df_origem, df_modelo, deposito=deposito)
    except MissingEstoqueModelError as exc:
        clear_estoque_outputs()
        st.error(str(exc))
        return
    except Exception as exc:
        clear_estoque_outputs()
        st.error('Não foi possível gerar o estoque. Confira a origem, o modelo e o depósito informado.')
        st.caption(str(exc) or exc.__class__.__name__)
        return
    result = {'index': 1, 'name': name, 'df_final': df_final, 'mapping': mapping}
    _store_stock_results([result])


def build_stock_outputs(upload, df_modelo: pd.DataFrame | None, deposito: str) -> None:
    if not _valid_model(df_modelo):
        _show_missing_model_warning()
        return
    source_files = source_files_from_upload(upload)
    if not source_files:
        clear_estoque_outputs()
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
        except MissingEstoqueModelError as exc:
            clear_estoque_outputs()
            st.error(str(exc))
            return
        except Exception as exc:
            clear_estoque_outputs()
            st.error(f'Não foi possível gerar o estoque da origem {index}: {file_name(file)}.')
            st.caption(str(exc) or exc.__class__.__name__)
            return
        results.append({'index': index, 'name': file_name(file), 'df_final': df_final, 'mapping': mapping})
    _store_stock_results(results)


def render_stock_preview() -> None:
    results = _stock_results()
    if not results:
        st.warning('Nenhum preview de estoque foi gerado ainda.')
        return
    st.markdown('#### Conferência final do estoque')
    st.caption('Confira o arquivo final antes do download. Esta tela já reflete as configurações do arquivo final.')
    preview_results: list[dict[str, object]] = []
    for result in results:
        index = result.get('index')
        df_final = result.get('df_final')
        mapping = result.get('mapping', {})
        with st.expander(f'Origem {index} · conferência do estoque', expanded=False):
            if isinstance(mapping, dict):
                show_mapping(mapping, operation='estoque')
            if isinstance(df_final, pd.DataFrame):
                df_preview = _final_preview_df(df_final)
                preview_results.append({**result, 'df_final': df_preview})
                preview_df('Arquivo final de estoque', df_preview)
            else:
                st.warning('Não foi possível montar o preview desta origem.')
    if preview_results:
        st.session_state['estoque_multi_outputs_preview_rules_applied'] = preview_results


def render_stock_downloads() -> None:
    results = _stock_results()
    if not results:
        st.warning('Nenhum CSV de estoque foi gerado ainda.')
        return
    st.caption('Baixe somente o CSV final de atualização de estoque. Cada origem válida gera um arquivo separado.')
    for result in results:
        index = result.get('index')
        name = str(result.get('name') or f'origem_{index}')
        df_final = result.get('df_final')
        if not isinstance(df_final, pd.DataFrame):
            st.warning(f'Não foi possível baixar a origem {index}: {name}.')
            continue
        st.markdown(f'**Origem {index}**')
        download_final(_final_preview_df(df_final), 'estoque', _download_key(index, name, df_final))
