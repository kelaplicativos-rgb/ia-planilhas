from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.engines.estoque_engine import MissingEstoqueModelError
from bling_app_zero.ui.estoque_sources import file_name, safe_read_source, source_files_from_upload
from bling_app_zero.ui.estoque_wizard_state import ESTOQUE_MODELO_KEY, clear_estoque_outputs, set_stock_output
from bling_app_zero.ui.home_models import get_home_estoque_model
from bling_app_zero.ui.home_shared import download_final, load_estoque_pipeline, preview_df, show_mapping


def _valid_model(df_modelo: pd.DataFrame | None) -> bool:
    return isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns) > 0


def _model_from_user(df_modelo: pd.DataFrame | None = None) -> pd.DataFrame | None:
    for candidate in (df_modelo, st.session_state.get(ESTOQUE_MODELO_KEY), get_home_estoque_model()):
        if _valid_model(candidate):
            return candidate.copy().fillna('')
    return None


def _show_model_contract_notice(df_modelo: pd.DataFrame | None = None) -> None:
    model = _model_from_user(df_modelo)
    if isinstance(model, pd.DataFrame):
        st.caption(f'Modelo para mapear ativo: {len(model.columns)} coluna(s). O download usará o layout anexado.')
    else:
        st.caption('Modelo para mapear ainda não localizado. Anexe o modelo antes do download.')


def _stock_results() -> list[dict[str, object]]:
    results = st.session_state.get('estoque_multi_outputs', [])
    return results if isinstance(results, list) else []


def _download_key(index: object, name: str, df_final: pd.DataFrame) -> str:
    safe_name = ''.join(ch if ch.isalnum() or ch in {'-', '_'} else '_' for ch in str(name or 'origem'))[:60]
    return f'modelo_mapeado_{index}_{safe_name}_{len(df_final)}_{len(df_final.columns)}'


def _final_preview_df(df_final: pd.DataFrame, df_modelo: pd.DataFrame | None = None) -> pd.DataFrame:
    # BLINGFIX: não aplicar contrato interno, sanitização Bling ou modelo padrão.
    # O contrato real da saída é o modelo anexado e será aplicado no download final.
    return df_final.copy().fillna('') if isinstance(df_final, pd.DataFrame) else pd.DataFrame()


def _store_stock_results(results: list[dict[str, object]]) -> None:
    st.session_state['estoque_multi_outputs'] = results
    if not results:
        clear_estoque_outputs()
        return
    first = results[0]
    df_final = first.get('df_final')
    mapping = first.get('mapping')
    set_stock_output(df_final if isinstance(df_final, pd.DataFrame) else None, mapping if isinstance(mapping, dict) else {})


def build_stock_outputs_from_dataframe(df_origem: pd.DataFrame, df_modelo: pd.DataFrame | None, deposito: str, name: str = 'Origem por site') -> None:
    model = _model_from_user(df_modelo)
    if not isinstance(df_origem, pd.DataFrame) or df_origem.empty:
        clear_estoque_outputs()
        st.warning('Nenhuma origem válida foi encontrada para gerar o modelo mapeado.')
        return
    if not isinstance(model, pd.DataFrame):
        clear_estoque_outputs()
        st.warning('Anexe o modelo para mapear antes de gerar o arquivo final.')
        return
    run_estoque_pipeline = load_estoque_pipeline()
    try:
        df_final, mapping = run_estoque_pipeline(df_origem, model, deposito=deposito)
    except MissingEstoqueModelError as exc:
        clear_estoque_outputs()
        st.error(str(exc))
        return
    except Exception as exc:
        clear_estoque_outputs()
        st.error('Não foi possível gerar o modelo mapeado. Confira a origem e o modelo anexado.')
        st.caption(str(exc) or exc.__class__.__name__)
        return
    result = {'index': 1, 'name': name, 'df_final': _final_preview_df(df_final, model), 'mapping': mapping, 'df_modelo': model}
    _store_stock_results([result])


def build_stock_outputs(upload, df_modelo: pd.DataFrame | None, deposito: str) -> None:
    model = _model_from_user(df_modelo)
    source_files = source_files_from_upload(upload)
    if not source_files:
        clear_estoque_outputs()
        st.warning('Anexei os arquivos, mas ainda não consegui identificar uma origem válida.')
        return
    if not isinstance(model, pd.DataFrame):
        clear_estoque_outputs()
        st.warning('Anexe o modelo para mapear antes de gerar o arquivo final.')
        return
    run_estoque_pipeline = load_estoque_pipeline()
    results: list[dict[str, object]] = []
    for index, file in enumerate(source_files, start=1):
        df_origem = safe_read_source(file)
        if not isinstance(df_origem, pd.DataFrame) or df_origem.empty:
            continue
        try:
            df_final, mapping = run_estoque_pipeline(df_origem, model, deposito=deposito)
        except MissingEstoqueModelError as exc:
            clear_estoque_outputs()
            st.error(str(exc))
            return
        except Exception as exc:
            clear_estoque_outputs()
            st.error(f'Não foi possível gerar o modelo mapeado da origem {index}: {file_name(file)}.')
            st.caption(str(exc) or exc.__class__.__name__)
            return
        results.append({'index': index, 'name': file_name(file), 'df_final': _final_preview_df(df_final, model), 'mapping': mapping, 'df_modelo': model})
    _store_stock_results(results)


def render_stock_preview() -> None:
    results = _stock_results()
    if not results:
        st.warning('Nenhuma prévia foi gerada ainda.')
        return
    st.markdown('#### Conferência final')
    st.caption('Confira o modelo mapeado antes do download.')
    _show_model_contract_notice()
    preview_results: list[dict[str, object]] = []
    for result in results:
        index = result.get('index')
        df_final = result.get('df_final')
        mapping = result.get('mapping', {})
        with st.expander(f'Origem {index} · conferência', expanded=False):
            if isinstance(mapping, dict):
                show_mapping(mapping, operation='universal')
            if isinstance(df_final, pd.DataFrame):
                df_preview = _final_preview_df(df_final)
                preview_results.append({**result, 'df_final': df_preview})
                preview_df('Modelo mapeado', df_preview)
            else:
                st.warning('Não foi possível montar a prévia desta origem.')
    if preview_results:
        st.session_state['estoque_multi_outputs_preview_rules_applied'] = preview_results


def render_stock_downloads() -> None:
    results = _stock_results()
    if not results:
        st.warning('Nenhum modelo mapeado foi gerado ainda.')
        return
    st.caption('Baixe o modelo mapeado. Cada origem válida gera um arquivo separado.')
    _show_model_contract_notice()
    for result in results:
        index = result.get('index')
        name = str(result.get('name') or f'origem_{index}')
        df_final = result.get('df_final')
        if not isinstance(df_final, pd.DataFrame):
            st.warning(f'Não foi possível baixar a origem {index}: {name}.')
            continue
        df_safe = _final_preview_df(df_final)
        st.markdown(f'**Origem {index}**')
        download_final(df_safe, 'universal', _download_key(index, name, df_safe))
